"""
批次 Geocoding — Photon 方案
- 對所有缺少座標的交易，查 Photon API 取得路段級座標
- 同一地址共用座標（快取）
- 純土地/地號自動跳過
- 支援斷點續傳（每 1000 筆 commit 一次）
- Rate limit: 0.3 秒間隔（Photon 無官方限制）

用法:
    python batch_geocode_photon.py              # 從頭開始
    python batch_geocode_photon.py --resume     # 從上次進度繼續
"""
import sys
import os
import re
import time
import json
import math
import urllib.request
import urllib.parse
from datetime import datetime
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import create_engine, text
from utils.chinese_to_english import chinese_to_english, parse_address

DB_URL = "postgresql://hermes@localhost:5432/housing_tracker"
PROGRESS_FILE = "/tmp/photon_geocode_progress.json"
INTERVAL = 0.3  # 秒，Photon 請求間隔

engine = create_engine(DB_URL)


def save_progress(total_groups, done_groups, success, failed, cached, processed_ids):
    """保存進度到檔案"""
    progress = {
        "total_groups": total_groups,
        "done_groups": done_groups,
        "success": success,
        "failed": failed,
        "cached": cached,
        "processed_ids": processed_ids,
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
                time.sleep(2 ** attempt)  # 指數退避
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

    # 去掉樓層（中文 + 數字+F）— 從後往前處理避免殘留
    for cn in ["二十","十九","十八","十七","十六","十五","十四","十三","十二","十一","十",
               "九","八","七","六","五","四","三","二","一"]:
        norm = norm.replace(f"{cn}樓", "")
    norm = re.sub(r'\d{1,2}F', '', norm)

    # 去掉巷弄及之後的內容（如 53巷16號 → 截斷）
    norm = re.sub(r'[０-９0-9]+[之0-9]*[巷弄].*$', '', norm)

    # 去掉門牌號碼（如 23號、100號、372之1號）
    norm = re.sub(r'[０-９0-9]+[之0-9]*號?$', '', norm)

    return norm.strip() if norm.strip() else None


def main():
    resume = "--resume" in sys.argv

    print("=" * 70)
    print("📍 Photon 批次 Geocoding")
    print("=" * 70)

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

        key = norm_addr
        location_groups[key].append(tid)

    total_groups = len(location_groups)
    print(f"可處理的唯一地址: {total_groups:,} 個")
    print(f"純土地/地號（跳過）: {skip_count:,} 筆")

    # 載入進度
    addr_coords_cache = {}  # 地址 → (lat, lon)
    processed_ids_set = set()
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
            processed_ids_set = set(progress.get("processed_ids", []))
            start_group = progress["done_groups"]

    # 開始批次處理
    groups_list = list(location_groups.items())
    updated_ids = []

    print(f"\n開始處理... ({datetime.now().strftime('%H:%M:%S')})")
    print("-" * 70)

    for i, (norm_addr, trade_ids) in enumerate(groups_list):
        if i < start_group:
            continue

        # 過濾已處理的
        remaining_ids = [tid for tid in trade_ids if tid not in processed_ids_set]
        if not remaining_ids:
            continue

        # 顯示進度
        pct = (i + 1) / total_groups * 100
        elapsed = time.time() - start_time if 'start_time' in dir() else 0
        eta = (elapsed / (i + 1)) * (total_groups - i) if i > 0 else 0

        print(f"[{i+1:>{len(str(total_groups))}}/{total_groups}] ({pct:.1f}%) "
              f"{norm_addr[:40]} "
              f"({len(trade_ids)} 筆) → ", end="", flush=True)

        # 查 Photon
        try:
            photon_q = chinese_to_english(norm_addr)
        except Exception as e:
            print(f"✗ 轉換失敗: {e}")
            failed += len(remaining_ids)
            for tid in remaining_ids:
                processed_ids_set.add(tid)
            continue

        coords = photon_query(photon_q)

        if coords:
            lat, lon = coords
            # 寫入 DB
            with engine.connect() as conn:
                placeholders = ",".join(["?"] * len(remaining_ids))
                # PostgreSQL 用 %s
                placeholders_pg = ",".join(["%s"] * len(remaining_ids))
                conn.execute(text(f"""
                    UPDATE trades SET lat = :lat, lon = :lon 
                    WHERE id IN :ids
                """), {"lat": lat, "lon": lon, "ids": tuple(remaining_ids)})
                conn.commit()

            updated_ids.extend(remaining_ids)
            success += len(remaining_ids)
            print(f"✓ ({lat:.6f}, {lon:.6f})")

            # 快取相同地址
            addr_coords_cache[norm_addr] = coords
        else:
            failed += len(remaining_ids)
            print(f"✗ 無結果")

        for tid in remaining_ids:
            processed_ids_set.add(tid)

        # 定期存進度
        if (i + 1) % 100 == 0 or (i + 1) == total_groups:
            save_progress(total_groups, i + 1, success, failed, cached, 
                        list(processed_ids_set)[-10000:])  # 只存最近 ID 避免檔案太大
            print(f"  💾 進度已保存")

        time.sleep(INTERVAL)

    # 最終統計
    print("\n" + "=" * 70)
    print("✅ 批次 Geocoding 完成!")
    print("=" * 70)

    with engine.connect() as conn:
        final_total = conn.execute(text("SELECT COUNT(*) FROM trades")).scalar()
        final_has = conn.execute(text("SELECT COUNT(*) FROM trades WHERE lat IS NOT NULL AND lon IS NOT NULL")).scalar()

    print(f"總交易筆數: {final_total:,}")
    print(f"已有座標: {final_has:,} ({final_has/final_total*100:.1f}%)")
    print(f"本次成功: {success:,}")
    print(f"本次失敗: {failed:,}")
    print(f"使用快取: {cached:,}")

    # 清除進度檔
    if os.path.exists(PROGRESS_FILE):
        os.remove(PROGRESS_FILE)
        print("進度檔已清除")


if __name__ == "__main__":
    start_time = time.time()
    main()
