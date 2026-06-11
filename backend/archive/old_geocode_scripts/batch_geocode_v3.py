#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
批次 Geocoding v3 — 平行請求版（Photon API + donma 對照表 + 流式處理）

核心改進：
- ThreadPoolExecutor 平行 geocode（CONCURRENCY=5）
- 每個 Worker 間隔 2.5 秒，總吞吐 ~2 筆/秒（12x 加速）
- 雙連線設計：read_conn (server-side cursor) / write_conn (batch UPDATE)
- Server-side cursor 流式讀取，不一次性載入記憶體
- synchronous_commit OFF + commit 間隔，控制 WAL/Checkpoint 壓力

I/O 安全設計：
- 雙連線：read_conn (server-side cursor, autocommit=False) / write_conn (batch UPDATE + commit)
- 小批次 commit（500 筆）：控制 WAL 產生速率
- commit 後 sleep 0.5s：避免 checkpoint 集中觸發

Usage:
    python batch_geocode_v3.py              # 正式執行
    python batch_geocode_v3.py --dry-run    # 只預覽前 20 筆，不寫入 DB
    python batch_geocode_v3.py --test N     # 測試前 N 個唯一地址
    python batch_geocode_v3.py --concurrency N  # 調整並行度（預設 5）
"""
import sys
import time
import json
import threading
import urllib.request
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
import psycopg2

# 強制 stdout 不 buffer（方便背景執行時看 log）
sys.stdout.reconfigure(line_buffering=True)

# 匯入地址轉換模組（donma 對照表 + Regex 解析）
from utils.chinese_to_english import chinese_to_english, is_low_quality_address, normalize_address

DB_URL = "postgresql://hermes@localhost:5432/housing_tracker"

DRY_RUN = '--dry-run' in sys.argv
TEST_LIMIT = None
for i, arg in enumerate(sys.argv):
    if arg == '--test' and i + 1 < len(sys.argv):
        TEST_LIMIT = int(sys.argv[i + 1])

# ── 平行請求設定 ────────────────────────────────
CONCURRENCY = 8           # 平行 Worker 數量
REQUEST_DELAY = 1.5       # 每個 Worker 請求間隔（秒）
BATCH_SIZE = 200          # 每 N 筆 geocode 完就寫入 DB
COMMIT_PAUSE = 0.5        # commit 後暫停（秒）

# 從 command line 覆蓋 concurrency
for i, arg in enumerate(sys.argv):
    if arg == '--concurrency' and i + 1 < len(sys.argv):
        CONCURRENCY = int(sys.argv[i + 1])

print(f"⚡ 平行模式: {CONCURRENCY} workers, 每 worker 間隔 {REQUEST_DELAY}s")
print(f"   預估吞吐: ~{CONCURRENCY / REQUEST_DELAY:.1f} 筆/秒")


def query_photon(query: str) -> tuple | None:
    """查詢 Photon API，回傳 (lat, lon) 或 None"""
    url = f"https://photon.komoot.io/api/?q={urllib.parse.quote(query)}&limit=1"
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            features = data.get('features', [])
            if features:
                coords = features[0]['geometry']['coordinates']  # [lon, lat]
                return (float(coords[1]), float(coords[0]))
    except Exception:
        pass
    return None


def geocode_address(address: str, city: str = "", district: str = "") -> tuple | None:
    """
    Geocode 一個地址，回傳 (lat, lon) 或 None
    
    策略：
    1. 先做舊稱映射（桃園縣→桃園市等）
    2. 去除樓層資訊（ Photon 不需要樓層）
    3. 若地址無縣市，用 DB 的 city/district 補齊
    4. donma 轉換後的英文地址查詢
    5. 若失敗，再用原始中文地址嘗試
    """
    import re
    
    # 去除樓層資訊（F、樓、之X 等）
    clean_addr = address
    # 去除 "XX樓"、"XXF"（含阿拉伯數字和中文數字）
    clean_addr = re.sub(r'(?:\d+|一|二|三|四|五|六|七|八|九|十|十一|十二|十三|十四|十五|十六|十七|十八|十九|二十[一二三四五六七八九]?)(?:F|樓)', '', clean_addr)
    # 去除 "之X"（分戶編號）
    clean_addr = re.sub(r'之\d+', '', clean_addr)
    # 去除地下室相關
    clean_addr = re.sub(r'地下[一二三四五六七八九十室層樓]+(?:[一二三四五六七八九十]+)?(?:樓|層)?', '', clean_addr)
    clean_addr = re.sub(r'\s+', ' ', clean_addr).strip()
    
    # 若地址無縣市，用 DB 的 city/district 補齊
    if not re.search(r'(市|縣)', clean_addr) and city:
        normalized_city = normalize_address(city)
        clean_addr = f"{normalized_city}{district if district else ''}{clean_addr}"
    
    # 先做舊稱映射
    normalized = normalize_address(clean_addr)
    
    # 策略 1: donma 轉換後的英文地址
    english_addr = chinese_to_english(normalized)
    if english_addr and english_addr != "Taiwan":
        result = query_photon(english_addr)
        if result:
            return result
    
    # 策略 2: 映射後的中文地址
    result = query_photon(f"{normalized}, Taiwan")
    if result:
        return result
    
    # 策略 3: 原始中文地址
    result = query_photon(f"{address}, Taiwan")
    if result:
        return result
    
    return None


def worker_geocode(batch_items: list, results: dict, lock: threading.Lock, counter: dict, print_lock: threading.Lock):
    """
    Worker 函式：逐一處理分配到的地址，每個請求間隔 REQUEST_DELAY 秒。
    
    結果寫入共享 dict（透過 lock 保護）。
    """
    for item in batch_items:
        idx, city, district, address, trade_count = item
        
        display_addr = address[:40].replace('\n', ' ')
        
        result = geocode_address(address, city, district)
        
        with lock:
            counter['total'] += 1
            if result:
                counter['success'] += 1
                results[idx] = (city, district, address, result[0], result[1])
            else:
                counter['failed'] += 1
        
        with print_lock:
            if result:
                print(f"[{idx}] {trade_count}x | {display_addr}... → ✓ ({result[0]:.4f}, {result[1]:.4f})")
            else:
                print(f"[{idx}] {trade_count}x | {display_addr}... → ✗ 找不到")
        
        time.sleep(REQUEST_DELAY)


def main():
    print("=" * 60)
    print("批次 Geocoding v3 — 平行請求版（Photon + donma）")
    print("=" * 60)
    if DRY_RUN:
        print("⚠️  DRY-RUN 模式：只預覽前 20 筆，不寫入 DB")
    if TEST_LIMIT:
        print(f"🧪 TEST 模式：只測試前 {TEST_LIMIT} 個唯一地址")
    print()

    # ============================================
    # 雙連線設計：讀取與寫入分離
    # ============================================
    read_conn = psycopg2.connect(DB_URL)
    read_conn.autocommit = False
    
    write_conn = psycopg2.connect(DB_URL)
    write_conn.autocommit = False
    write_cur = write_conn.cursor()
    write_cur.execute("SET synchronous_commit = OFF")
    write_conn.commit()
    
    stats_cur = read_conn.cursor()

    # ============================================
    # Step 1: 統計目前狀態
    # ============================================
    stats_cur.execute("SELECT COUNT(*) FROM trades")
    total = stats_cur.fetchone()[0]

    stats_cur.execute("SELECT COUNT(*) FROM trades WHERE lat IS NOT NULL AND lon IS NOT NULL")
    has_coords = stats_cur.fetchone()[0]

    needs_geo = total - has_coords
    print(f"Step 1: 統計")
    print(f"  總筆數: {total:,}")
    print(f"  已有座標: {has_coords:,}")
    print(f"  需 Geocoding: {needs_geo:,}")
    print()

    if needs_geo == 0:
        print("✅ 全部已完成！")
        stats_cur.close()
        read_conn.close()
        write_cur.close()
        write_conn.close()
        return

    # ============================================
    # Step 2: Server-side cursor 流式讀取唯一地址
    # ============================================
    print("Step 2: 建立 Server-side cursor（流式讀取）...")
    
    server_cursor_name = 'geocode_stream'
    unique_query = """
        SELECT t.city, t.district, t.address, COUNT(*) as trade_count
        FROM trades t
        WHERE (t.lat IS NULL OR t.lon IS NULL)
        AND t.address IS NOT NULL
        AND LENGTH(t.address) >= 5
        -- 排除地號/建號
        AND t.address NOT LIKE '%%地號%%'
        AND t.address NOT LIKE '%%建號%%'
        -- 排除純地下室（沒有地面層地址）— 開頭或結尾含「地下」
        AND TRIM(t.address) NOT LIKE '地下%%'
        AND TRIM(t.address) NOT LIKE '%%地下[室層樓]'
        AND TRIM(t.address) NOT LIKE '%%地下一%'
        -- 排除公共設施/共有部分
        AND t.address NOT LIKE '%%公共設施%%'
        AND t.address NOT LIKE '%%共同使用%%'
        -- 排除範圍地址（如 X號至Y號）
        AND t.address NOT LIKE '%%號至%%'
        -- 排除工業區無門牌
        AND t.address NOT LIKE '%%工業區'
        -- 排除村里名結尾（無路名）
        AND t.address NOT LIKE '%%里 '
        GROUP BY t.city, t.district, t.address
        ORDER BY trade_count DESC
    """
    
    if TEST_LIMIT:
        unique_query += f" LIMIT {TEST_LIMIT}"

    server_cur = read_conn.cursor(server_cursor_name)
    server_cur.itersize = BATCH_SIZE
    server_cur.execute(unique_query)
    
    print(f"  ✓ Server-side cursor '{server_cursor_name}' 已建立")
    print()

    if DRY_RUN and not TEST_LIMIT:
        print("DRY-RUN: 只測試前 20 筆\n")

    # ============================================
    # Step 3: 流式 geocode + 批次寫入（平行請求）
    # ============================================
    print("Step 3: 開始 Geocoding（平行請求，每批立即寫入 DB）...")
    print()

    geo_success = 0
    geo_failed = 0
    total_updated = 0
    batch_num = 0
    global_idx = 0
    start_time = time.time()

    dry_run_count = 0
    dry_run_limit = 20 if DRY_RUN else 0

    while True:
        batch = server_cur.fetchmany(BATCH_SIZE)
        if not batch:
            break
        
        if DRY_RUN and not TEST_LIMIT and dry_run_count >= dry_run_limit:
            break

        # 準備批次項目
        batch_items = []
        for city, district, address, trade_count in batch:
            global_idx += 1
            batch_items.append((global_idx, city, district, address, trade_count))
        
        if not batch_items:
            continue

        # 共享結果容器
        results = {}
        lock = threading.Lock()
        print_lock = threading.Lock()
        counter = {'success': 0, 'failed': 0, 'total': 0}
        
        # 將批次分為 CONCURRENCY 個子批次，分配給各 Worker
        sub_batches = [[] for _ in range(CONCURRENCY)]
        for i, item in enumerate(batch_items):
            sub_batches[i % CONCURRENCY].append(item)
        
        # 啟動平行 Workers
        threads = []
        for i in range(CONCURRENCY):
            if sub_batches[i]:
                t = threading.Thread(target=worker_geocode, args=(sub_batches[i], results, lock, counter, print_lock))
                t.start()
                threads.append(t)
        
        # 等待所有 Workers 完成
        for t in threads:
            t.join()
        
        # 更新統計
        geo_success += counter['success']
        geo_failed += counter['failed']
        
        if DRY_RUN:
            dry_run_count += counter['total']

        # ── 批次寫入 DB（使用獨立 write_conn）──
        if results and not DRY_RUN:
            for idx in sorted(results.keys()):
                u_city, u_district, u_addr, u_lat, u_lon = results[idx]
                write_cur.execute("""
                    UPDATE trades SET lat = %s, lon = %s
                    WHERE address = %s
                    AND city = %s
                    AND district = %s
                    AND (lat IS NULL OR lon IS NULL)
                """, (u_lat, u_lon, u_addr, u_city, u_district))
                total_updated += write_cur.rowcount
            
            write_conn.commit()
            batch_num += 1
            elapsed = time.time() - start_time
            
            print(f"  💾 Batch #{batch_num}: {len(results)} 組成功, "
                  f"累計更新 {total_updated:,} 筆 | "
                  f"成功 {geo_success} / 失敗 {geo_failed} | "
                  f"耗時 {elapsed/60:.1f}min")
            
            time.sleep(COMMIT_PAUSE)
        elif results and DRY_RUN:
            print(f"  ⚠️  DRY-RUN: 跳過寫入 {len(results)} 筆")

    server_cur.close()

    total_time = time.time() - start_time

    print()
    print("=" * 60)
    print(f"Geocoding 完成:")
    print(f"  成功: {geo_success}")
    print(f"  失敗: {geo_failed}")
    print(f"  DB 更新: {total_updated:,} 筆交易")
    print(f"  耗時: {total_time/60:.1f} 分鐘")
    if total_time > 0:
        print(f"  平均速度: {(geo_success + geo_failed) / total_time:.2f} 筆/秒")
    print("=" * 60)
    print()

    # ============================================
    # Step 4: 最終統計
    # ============================================
    stats_cur.execute("SELECT COUNT(*) FROM trades WHERE lat IS NOT NULL AND lon IS NOT NULL")
    final_coords = stats_cur.fetchone()[0]
    
    print("最終結果:")
    print(f"  已有座標: {final_coords:,}/{total:,} ({final_coords/total*100:.1f}%)")
    print(f"  本次新增: {final_coords - has_coords:,} 筆")
    print("=" * 60)

    # 清理
    stats_cur.close()
    read_conn.close()
    write_cur.close()
    write_conn.close()
    print("\n✅ 批次處理完成！")


if __name__ == "__main__":
    main()
