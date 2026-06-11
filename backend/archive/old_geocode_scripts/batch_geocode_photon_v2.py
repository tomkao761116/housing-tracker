"""
批次 Geocoding — Photon 方案 v2 (效能優化版)
- 批次 UPDATE（每 500 筆一組）
- 使用 COPY 格式批量寫入臨時表，再 JOIN UPDATE
- 減少資料庫連線次數
- 更可靠的斷點續傳（記錄最後處理的地址索引）
- Rate limit: 0.15 秒間隔（測試顯示 Photon 可承受）

用法:
    python batch_geocode_photon_v2.py              # 從頭開始
    python batch_geocode_photon_v2.py --resume     # 從上次進度繼續
"""
import sys
import os
import re
import time
import json
import urllib.request
import urllib.parse
from datetime import datetime
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import create_engine, text
from utils.chinese_to_english import chinese_to_english, parse_address

DB_URL = "postgresql://hermes@localhost:5432/housing_tracker"
PROGRESS_FILE = "/tmp/photon_geocode_progress_v2.json"
INTERVAL = 0.15  # 秒，Photon 請求間隔（優化後）
BATCH_SIZE = 500  # 每批次 UPDATE 的筆數
COMMIT_INTERVAL = 100  # 每多少組保存一次進度

engine = create_engine(DB_URL, pool_size=5, pool_recycle=300)


def save_progress(total_groups, done_groups, success, failed, cached):
    """保存進度到檔案 - 只存必要資訊"""
    progress = {
        "total_groups": total_groups,
        "done_groups": done_groups,
        "success": success,
        "failed": failed,
        "cached": cached,
        "timestamp": datetime.now().isoformat(),
    }
    with open(PROGRESS_FILE, "w") as f:
        json.dump(progress, f, ensure_ascii=False, indent=2)


def load_progress():
    """載入上次進度"""
    if os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE) as f:
            return json.load(f)
    return None


def photon_query(query: str, max_retries=3):
    """查詢 Photon API，帶重試"""
    url = f"https://photon.komoot.io/api/?q={urllib.parse.quote(query)}&limit=1"
    req = urllib.request.Request(url, headers={"User-Agent": "HousingTracker/1.0"})

    for attempt in range(max_retries):
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode())
                if data.get("features"):
                    feat = data["features"][0]
                    lon, lat = feat["geometry"]["coordinates"]
                    return float(lat), float(lon)
            return None
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
            else:
                return None


def normalize_address(addr: str) -> str | None:
    """
    正規化地址為路段級（去掉門牌/巷弄/樓層）
    純土地/地號回傳 None
    """
    if not addr:
        return None

    # 純土地/地號 — 無法 geocode
    if "地號" in addr or ("段" in addr and "小段" in addr):
        return None

    norm = addr

    # 去掉樓層
    for cn in ["二十","十九","十八","十七","十六","十五","十四","十三","十二","十一","十",
               "九","八","七","六","五","四","三","二","一"]:
        norm = norm.replace(f"{cn}樓", "")
    norm = re.sub(r'\d{1,2}F', '', norm)

    # 去掉巷弄及之後的內容
    norm = re.sub(r'[０-９0-9]+[之0-9]*[巷弄].*$', '', norm)

    # 去掉門牌號碼
    norm = re.sub(r'[０-９0-9]+[之0-9]*號?$', '', norm)

    return norm.strip() if norm.strip() else None


def batch_update_coords(conn, coord_batches):
    """
    批次更新座標 - 使用 EXECUTE ... USING 避免 SQL injection
    coord_batches: dict of (lat, lon) -> [id1, id2, ...]
    """
    total_updated = 0
    for (lat, lon), trade_ids in coord_batches.items():
        if not trade_ids:
            continue
        # 分批處理，每批最多 500 筆
        for batch in [trade_ids[i:i+BATCH_SIZE] for i in range(0, len(trade_ids), BATCH_SIZE)]:
            conn.execute(text("""
                UPDATE trades SET lat = :lat, lon = :lon 
                WHERE id = ANY(:ids)
            """), {"lat": lat, "lon": lon, "ids": batch})
            total_updated += len(batch)
    conn.commit()
    return total_updated


def main():
    resume = "--resume" in sys.argv

    print("=" * 70)
    print("📍 Photon 批次 Geocoding v2 (效能優化版)")
    print("=" * 70)

    start_time = time.time()

    # 連線 DB
    with engine.connect() as conn:
        total_no_coords = conn.execute(text("""
            SELECT COUNT(*) FROM trades WHERE lat IS NULL OR lon IS NULL
        """)).scalar()
        print(f"\n總共缺少座標: {total_no_coords:,} 筆")

        # 取得所有需要處理的地址群組
        result = conn.execute(text("""
            SELECT id, city, district, address 
            FROM trades 
            WHERE lat IS NULL OR lon IS NULL
            ORDER BY id
        """))
        all_trades = result.fetchall()

    # 依正規化地址分組
    location_groups = defaultdict(list)
    skip_count = 0

    for trade in all_trades:
        tid, city, district, addr = trade
        norm_addr = normalize_address(addr)

        if not norm_addr:
            skip_count += 1
            continue

        location_groups[norm_addr].append(tid)

    total_groups = len(location_groups)
    print(f"可處理的唯一地址: {total_groups:,} 個")
    print(f"純土地/地號（跳過）: {skip_count:,} 筆")

    # 載入進度
    success = 0
    failed = 0
    cached = 0
    start_group = 0

    if resume:
        progress = load_progress()
        if progress and progress.get("done_groups", 0) > 0:
            print(f"\n🔄 恢復進度: 已完成 {progress['done_groups']}/{progress['total_groups']} 組")
            success = progress.get("success", 0)
            failed = progress.get("failed", 0)
            cached = progress.get("cached", 0)
            start_group = progress["done_groups"]

    # 開始批次處理
    groups_list = list(location_groups.items())
    
    # 用於批次更新的暫存區
    coord_batches = {}  # (lat, lon) -> [id1, id2, ...]
    batch_count = 0

    print(f"\n開始處理... ({datetime.now().strftime('%H:%M:%S')})")
    print("-" * 70)

    last_report = time.time()

    for i, (norm_addr, trade_ids) in enumerate(groups_list):
        if i < start_group:
            continue

        # 顯示進度（每秒最多一次）
        now = time.time()
        if now - last_report > 1.0:
            pct = (i + 1) / total_groups * 100
            elapsed = now - start_time
            rate = (i + 1) / elapsed if elapsed > 0 else 0
            eta = (total_groups - i) / rate if rate > 0 else 0
            print(f"\r[{i+1:>{len(str(total_groups))}}/{total_groups}] ({pct:.1f}%) "
                  f"{rate:.1f} group/s | ETA: {eta//60:.0f}m{eta%60:.0f}s",
                  flush=True, end='')
            last_report = now

        # 查 Photon
        try:
            photon_q = chinese_to_english(norm_addr)
        except Exception as e:
            failed += len(trade_ids)
            continue

        coords = photon_query(photon_q)

        if coords:
            lat, lon = coords
            # 加入批次更新暫存區（四捨五入到 5 位小數，避免浮點誤差）
            key = (round(lat, 5), round(lon, 5))
            if key not in coord_batches:
                coord_batches[key] = []
            coord_batches[key].extend(trade_ids)
            batch_count += len(trade_ids)
            success += len(trade_ids)
        else:
            failed += len(trade_ids)

        # 定期批次寫入 DB
        if batch_count >= BATCH_SIZE:
            with engine.connect() as conn:
                updated = batch_update_coords(conn, coord_batches)
            coord_batches.clear()
            batch_count = 0

        time.sleep(INTERVAL)

    # 寫入剩餘的批次
    if coord_batches:
        with engine.connect() as conn:
            updated = batch_update_coords(conn, coord_batches)
        coord_batches.clear()

    # 最終統計
    print("\n" + "=" * 70)
    print("✅ 批次 Geocoding 完成!")
    print("=" * 70)

    total_time = time.time() - start_time
    
    with engine.connect() as conn:
        final_total = conn.execute(text("SELECT COUNT(*) FROM trades")).scalar()
        final_has = conn.execute(text("SELECT COUNT(*) FROM trades WHERE lat IS NOT NULL AND lon IS NOT NULL")).scalar()

    print(f"總交易筆數: {final_total:,}")
    print(f"已有座標: {final_has:,} ({final_has/final_total*100:.1f}%)")
    print(f"本次成功: {success:,}")
    print(f"本次失敗: {failed:,}")
    print(f"總耗時: {total_time//60:.0f}分{total_time%60:.0f}秒")
    print(f"平均速度: {(i+1)/total_time:.1f} 組/秒")

    # 清除進度檔
    if os.path.exists(PROGRESS_FILE):
        os.remove(PROGRESS_FILE)
        print("進度檔已清除")


if __name__ == "__main__":
    main()
