"""資料同步 API - 從 MCP 拉取資料到本地資料庫（含差異更新）"""
from fastapi import APIRouter, Depends, BackgroundTasks, Query
from sqlalchemy.orm import Session
from datetime import datetime, date
from typing import Optional
import os
import time

from app.main import get_db, engine
from app.models.database import Trade, SyncLog, SyncState, Base
from app.services.mcp_client import MCPClient
from app.services.geocode import batch_geocode_trades, batch_score_trades

router = APIRouter()

MCP_ENDPOINT = os.getenv("MCP_ENDPOINT", "https://api.twinkleai.tw/mcp/")
MCP_API_KEY = os.getenv("MCP_API_KEY", "")

# 批次參數
BATCH_SIZE = 1000          # 每次 API 查詢筆數
COMMIT_INTERVAL = 200      # 每 N 筆 commit 一次
MAX_RETRIES = 3            # API 呼叫重試次數
RETRY_DELAY = 2            # 重試間隔（秒）


def parse_roc_date(roc_str: str) -> date | None:
    """民國年月日 (如 '1140518') → date object
    
    格式為 7 位數字: ROC_YEAR(3) + MM(2) + DD(2)
    西元年 = 民國年 + 1911
    """
    try:
        roc_str = str(roc_str).strip()
        if len(roc_str) < 7:
            return None
        y = int(roc_str[:3]) + 1911
        m = int(roc_str[3:5])
        d = int(roc_str[5:7])
        # 過濾異常日期：民國年不應該 > 120（西元2131）或 < 80（西元1991）
        # 避免把腐敗資料（如 "1901017"）誤解析為有效日期
        if y > 2030 or y < 1990:
            return None
        return date(y, m, d)
    except (ValueError, IndexError):
        return None


def parse_bool(val: str) -> bool | None:
    if not val:
        return None
    return val.strip() == "有"


def parse_int(val: str) -> int | None:
    if not val or val.strip() == "":
        return None
    try:
        return int(float(val))
    except (ValueError, TypeError):
        return None


def parse_float(val: str) -> float | None:
    if not val or val.strip() == "":
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def get_sync_state(db: Session, dataset: str) -> SyncState | None:
    """取得資料集同步狀態"""
    return db.query(SyncState).filter(SyncState.dataset == dataset).first()


def upsert_sync_state(db: Session, dataset: str, last_date: date | None = None, total_rows: int = 0):
    """建立或更新同步狀態"""
    state = get_sync_state(db, dataset)
    if state:
        state.last_synced_at = datetime.utcnow()
        state.last_synced_date = last_date
        state.total_rows = total_rows
        state.updated_at = datetime.utcnow()
    else:
        state = SyncState(
            dataset=dataset,
            last_synced_at=datetime.utcnow(),
            last_synced_date=last_date,
            total_rows=total_rows,
        )
        db.add(state)
    db.commit()


def mcp_query_with_retry(client: MCPClient, **kwargs) -> dict:
    """帶重試機制的 MCP API 呼叫"""
    for attempt in range(MAX_RETRIES):
        try:
            result = client.query_rows(**kwargs)
            return result
        except Exception as e:
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY * (attempt + 1))
            else:
                raise RuntimeError(f"MCP query failed after {MAX_RETRIES} retries: {e}")


def sync_trades_incremental(db: Session, city: str = None, season: str = None,
                             full: bool = False, limit: int = 0):
    """
    差異更新同步買賣交易資料
    
    Args:
        db: SQLAlchemy session
        city: 限定縣市（可選）
        season: 限定季別（可選）
        full: 強制全量同步（忽略增量狀態）
        limit: 限制總筆數（0=不限制，預設拉到全部）
    
    Strategy:
        1. 查 SyncState 取得 last_synced_date
        2. 若有上次記錄且非全量模式 → 只拉 iso_trade_date > last_synced_date 的新資料
        3. 批量收集 raw_id，一次 SQL 查詢已存在記錄（避免 N+1）
        4. 每 COMMIT_INTERVAL 筆 commit 一次
        5. 更新 SyncState 追蹤最新進度
    """
    if not MCP_API_KEY:
        return {"error": "MCP_API_KEY not configured"}

    client = MCPClient(MCP_ENDPOINT, MCP_API_KEY)
    client.init()

    # 決定是否走增量模式
    state = get_sync_state(db, "trades")
    since_date = None
    if not full and state and state.last_synced_date:
        since_date = state.last_synced_date
        print(f"[Sync] Incremental mode: since {since_date}")
    else:
        print(f"[Sync] Full sync mode (state={state is not None}, date={state.last_synced_date if state else None})")

    # 建構 WHERE 條件
    where_parts = []
    if city:
        where_parts.append(f"city='{city}'")
    if season:
        where_parts.append(f"season='{season}'")
    if since_date:
        # 增量：只拉比上次更新的日期更晚的資料（改用民國格式 YYYYMMDD）
        since_roc_year = since_date.year - 1911
        since_roc_str = f"{since_roc_year:03d}{since_date.month:02d}{since_date.day:02d}"
        where_parts.append(f"交易年月日 > '{since_roc_str}'")
    where = " AND ".join(where_parts) if where_parts else None

    # 批次輪詢
    offset = 0
    imported = 0
    updated = 0
    total_fetched = 0
    commit_count = 0

    while True:
        batch_limit = BATCH_SIZE
        if limit > 0:
            remaining = limit - total_fetched
            if remaining <= 0:
                break
            batch_limit = min(BATCH_SIZE, remaining)

        result = mcp_query_with_retry(
            client,
            dataset_id="lvr-trades",
            where=where,
            columns=None,  # MCP API bug: do NOT specify columns
            limit=batch_limit,
            order_by="交易年月日 ASC",  # 按民國日期升序方便增量追蹤
        )

        if not result.get("rows"):
            break

        # 收集本批所有 raw_id
        batch_raw_ids = []
        batch_records = []

        for row_vals in result["rows"]:
            row_dict = dict(zip(result["columns"], row_vals))
            raw_id = row_dict.get("編號", "")
            if not raw_id:
                continue

            trade_date = None
            # 優先使用「交易年月日」(民國格式)，棄用 iso_trade_date（已知回傳錯誤日期）
            roc_date_str = row_dict.get("交易年月日", "")
            if roc_date_str:
                trade_date = parse_roc_date(roc_date_str)
            if trade_date is None:
                iso_date = row_dict.get("iso_trade_date", "")
                if iso_date and len(iso_date) >= 10:
                    try:
                        trade_date = date.fromisoformat(iso_date[:10])
                    except ValueError:
                        pass

            unit_price = parse_float(row_dict.get("單價元平方公尺"))
            unit_price_tping = round(unit_price * 3.3058, 0) if unit_price else None

            trade_data = {
                "city": row_dict.get("city", ""),
                "district": row_dict.get("鄉鎮市區", ""),
                "address": row_dict.get("土地位置建物門牌_半形", ""),
                "address_raw": row_dict.get("土地位置建物門牌", ""),
                "trade_date": trade_date,
                "trade_date_roc": row_dict.get("交易年月日", ""),
                "season": row_dict.get("season", ""),
                "total_price": parse_int(row_dict.get("總價元")),
                "unit_price": unit_price,
                "unit_price_tping": unit_price_tping,
                "land_area": parse_float(row_dict.get("土地移轉總面積平方公尺")),
                "building_area": parse_float(row_dict.get("建物移轉總面積平方公尺")),
                "main_building_area": parse_float(row_dict.get("主建物面積")),
                "attached_building_area": parse_float(row_dict.get("附屬建物面積")),
                "balcony_area": parse_float(row_dict.get("陽台面積")),
                "parking_area": parse_float(row_dict.get("車位移轉總面積平方公尺")),
                "parking_price": parse_int(row_dict.get("車位總價元")),
                "building_type": row_dict.get("建物型態", ""),
                "floor": row_dict.get("移轉層次", ""),
                "total_floors": row_dict.get("總樓層數", ""),
                "rooms": parse_int(row_dict.get("建物現況格局-房")),
                "living_rooms": parse_int(row_dict.get("建物現況格局-廳")),
                "bathrooms": parse_int(row_dict.get("建物現況格局-衛")),
                "has_elevator": parse_bool(row_dict.get("電梯")),
                "has_mgmt_org": parse_bool(row_dict.get("有無管理組織")),
                "main_use": row_dict.get("主要用途", ""),
                "main_material": row_dict.get("主要建材", ""),
                "land_use_zone": row_dict.get("都市土地使用分區", ""),
                "build_complete_date": row_dict.get("建築完成年月", ""),
                "parking_type": row_dict.get("車位類別", ""),
                "raw_id": raw_id,
                "trade_target": row_dict.get("交易標的", ""),
                "notes": row_dict.get("備註", ""),
            }
            batch_raw_ids.append(raw_id)
            batch_records.append(trade_data)

        # 批量查詢已存在的 raw_id（一次 SQL 代替 N 次）
        existing_map = {}
        if batch_raw_ids:
            existing_rows = db.query(Trade.raw_id).filter(
                Trade.raw_id.in_(batch_raw_ids)
            ).all()
            existing_map = {row.raw_id for row in existing_rows}

        # 寫入 DB
        for rec in batch_records:
            if rec["raw_id"] in existing_map:
                # 更新現有記錄
                existing = db.query(Trade).filter(Trade.raw_id == rec["raw_id"]).first()
                if existing:
                    for key, val in rec.items():
                        setattr(existing, key, val)
                    updated += 1
            else:
                new_trade = Trade(**rec)
                db.add(new_trade)
                imported += 1

        total_fetched += len(batch_records)
        offset += len(result["rows"])

        # 定期 commit
        if (imported + updated) % COMMIT_INTERVAL == 0:
            db.commit()
            commit_count += 1
            print(f"[Sync] Committed batch #{commit_count}: imported={imported}, updated={updated}, total={total_fetched}")

        # 如果回傳少於請求數量，表示已到最後一頁
        if len(result["rows"]) < batch_limit:
            break

    # 最終 commit
    db.commit()

    # 找出最新的交易日期（用於下次增量同步）
    latest_date_result = db.query(Trade.trade_date).filter(
        Trade.trade_date.isnot(None)
    ).order_by(Trade.trade_date.desc()).first()
    latest_date = latest_date_result.trade_date if latest_date_result else None

    # 更新總筆數
    total_in_db = db.query(Trade).count()

    print(f"[Sync] Done: imported={imported}, updated={updated}, total_fetched={total_fetched}, total_in_db={total_in_db}")

    return {
        "imported": imported,
        "updated": updated,
        "total": imported + updated,
        "latest_date": latest_date.isoformat() if latest_date else None,
        "total_in_db": total_in_db,
    }


@router.post("/trades")
def trigger_sync(
    background_tasks: BackgroundTasks,
    city: Optional[str] = Query(None, description="限定縣市"),
    season: Optional[str] = Query(None, description="限定季別"),
    full: bool = Query(False, description="強制全量同步"),
    limit: int = Query(0, description="限制筆數（0=全部）"),
    db: Session = Depends(get_db),
):
    """觸發買賣資料同步（背景執行，支援差異更新）"""
    log = SyncLog(dataset="trades", season=season, status="running")
    db.add(log)
    db.commit()
    log_id = log.id

    def do_sync():
        # 背景任務需要自己的 DB session（原 session 已在請求結束後關閉）
        from app.main import SessionLocal
        bg_db = SessionLocal()
        try:
            if not MCP_API_KEY:
                log = bg_db.query(SyncLog).filter(SyncLog.id == log_id).first()
                log.status = "failed"
                log.error = "MCP_API_KEY not configured"
                bg_db.commit()
                return

            result = sync_trades_incremental(bg_db, city=city, season=season, full=full, limit=limit)

            # 更新 SyncState
            latest_date = None
            if result.get("latest_date"):
                latest_date = date.fromisoformat(result["latest_date"])
            upsert_sync_state(
                bg_db, "trades",
                last_date=latest_date,
                total_rows=result.get("total_in_db", 0),
            )

            # 【修正】只在有新交易紀錄時才觸發 POI 查詢與生活圈評分
            new_count = result.get("imported", 0)
            if new_count > 0:
                print(f"[Sync] {new_count} new trade(s) detected — triggering geocode + score pipeline...")
                geo_result = batch_geocode_trades(bg_db, limit=new_count)
                print(f"[Geocode] Post-sync done: {geo_result}")

                if geo_result["success"] > 0:
                    score_result = batch_score_trades(bg_db, limit=geo_result["success"])
                    print(f"[Score] Post-sync done: {score_result}")
            else:
                print(f"[Sync] No new trades (imported={new_count}, updated={result.get('updated', 0)}) — skipping POI/score.")

            log = bg_db.query(SyncLog).filter(SyncLog.id == log_id).first()
            log.status = "success"
            log.synced_at = datetime.utcnow()
            log.rows_imported = result.get("imported", 0)
            log.rows_updated = result.get("updated", 0)
        except Exception as e:
            print(f"[Sync ERROR] {e}")
            import traceback
            traceback.print_exc()
            log = bg_db.query(SyncLog).filter(SyncLog.id == log_id).first()
            log.status = "failed"
            log.error = str(e)[:2000]
        finally:
            bg_db.commit()
            bg_db.close()

    background_tasks.add_task(do_sync)
    return {"message": "同步任務已啟動", "log_id": log_id}


@router.get("/logs")
def get_sync_logs(db: Session = Depends(get_db)):
    """查詢同步紀錄"""
    logs = db.query(SyncLog).order_by(SyncLog.synced_at.desc()).limit(20).all()
    return [
        {
            "id": l.id,
            "dataset": l.dataset,
            "season": l.season,
            "synced_at": l.synced_at.isoformat() if l.synced_at else None,
            "rows_imported": l.rows_imported,
            "rows_updated": l.rows_updated,
            "status": l.status,
            "error": l.error,
        }
        for l in logs
    ]


@router.get("/state/{dataset}")
def get_dataset_sync_state(dataset: str, db: Session = Depends(get_db)):
    """查詢特定資料集的同步狀態"""
    state = get_sync_state(db, dataset)
    if not state:
        return {"dataset": dataset, "message": "尚未同步過"}
    return {
        "dataset": state.dataset,
        "last_synced_at": state.last_synced_at.isoformat() if state.last_synced_at else None,
        "last_synced_date": state.last_synced_date.isoformat() if state.last_synced_date else None,
        "total_rows": state.total_rows,
        "updated_at": state.updated_at.isoformat() if state.updated_at else None,
    }


@router.post("/geocode")
def trigger_geocode(
    limit: int = Query(500, description="Max trades to geocode"),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db: Session = Depends(get_db),
):
    """觸發地理編碼 — 為沒有座標的交易記錄補上 lat/lon，完成後自動評分"""
    def do_geocode_then_score():
        bg_db = next(get_db())
        try:
            geo_result = batch_geocode_trades(bg_db, limit=limit)
            print(f"[Geocode] Done: {geo_result}")
            
            # 地理編碼完成後，自動對有座標但無評分的記錄執行評分
            if geo_result["success"] > 0:
                print(f"[Sync] Triggering score computation for newly geocoded trades...")
                score_result = batch_score_trades(bg_db)
                print(f"[Score] Done: {score_result}")
        finally:
            bg_db.close()

    background_tasks.add_task(do_geocode_then_score)
    return {
        "status": "geocoding started",
        "limit": limit,
        "message": "地理編碼已在背景執行中，完成後將自動計算生活機能評分",
    }


@router.get("/geocode/status")
def geocode_status(db: Session = Depends(get_db)):
    """查詢地理編碼狀態"""
    total = db.query(Trade).count()
    with_coords = db.query(Trade).filter(
        Trade.lat.isnot(None),
        Trade.lon.isnot(None)
    ).count()
    without_coords = total - with_coords
    return {
        "total_trades": total,
        "with_coordinates": with_coords,
        "without_coordinates": without_coords,
        "coverage_pct": round(with_coords / total * 100, 1) if total > 0 else 0,
    }


@router.post("/score")
def trigger_score(
    limit: int = Query(0, description="Max trades to score (0=all)"),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db: Session = Depends(get_db),
):
    """觸發生活機能評分 — 為有座標但無評分的交易記錄計算評分"""
    def do_score():
        bg_db = next(get_db())
        try:
            result = batch_score_trades(bg_db, limit=limit)
            print(f"[Score] Done: {result}")
        finally:
            bg_db.close()

    background_tasks.add_task(do_score)
    return {
        "status": "scoring started",
        "limit": limit,
        "message": "生活機能評分已在背景執行中",
    }


@router.get("/score/status")
def score_status(db: Session = Depends(get_db)):
    """查詢評分狀態"""
    total = db.query(Trade).count()
    scored = db.query(Trade).filter(
        Trade.score_overall.isnot(None)
    ).count()
    unscored = total - scored
    # 有座標但沒分數的（待評分）
    pending = db.query(Trade).filter(
        Trade.lat.isnot(None),
        Trade.lon.isnot(None),
        Trade.score_overall == None
    ).filter(Trade.score_overall.is_(None)).count()
    return {
        "total_trades": total,
        "scored": scored,
        "unscored": unscored,
        "pending_score": pending,
        "coverage_pct": round(scored / total * 100, 1) if total > 0 else 0,
    }
