#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
批次 Geocoding v6 — Producer/Consumer 架構

核心改進 (v5 → v6):
- 24 個 geocoding workers（Photon 查詢極限）
- 單一 writer thread 批次寫入 DB（避免連線爆掉）
- Queue 隔離查詢與寫入，互不阻塞
- httpx connection pooling + diskcache 持久化快取

Usage:
    python batch_geocode_v4.py              # 正式執行
    python batch_geocode_v4.py --dry-run    # 只預覽前 20 筆，不寫入 DB
    python batch_geocode_v4.py --test N     # 測試前 N 個唯一地址
"""
import sys
import re
import time
import threading
import queue
from concurrent.futures import ThreadPoolExecutor
import psycopg2
import httpx

# 強制 stdout 不 buffer（方便背景執行時看 log）
sys.stdout.reconfigure(line_buffering=True)

# 匯入地址轉換模組
from utils.chinese_to_english import normalize_address

DB_URL = "postgresql://hermes@localhost:5432/housing_tracker"

DRY_RUN = '--dry-run' in sys.argv
TEST_LIMIT = None
for i, arg in enumerate(sys.argv):
    if arg == '--test' and i + 1 < len(sys.argv):
        TEST_LIMIT = int(sys.argv[i + 1])

# ── 平行請求設定 ────────────────────────────────
GEO_WORKERS = 24          # Photon 查詢 worker 數量（本地端極限）
WRITE_BATCH_SIZE = 500    # 每 N 筆結果寫入一次 DB
WRITE_FLUSH_INTERVAL = 2  # 最多等待 N 秒後強制 flush

print(f"⚡ Producer/Consumer 模式: {GEO_WORKERS} geocoding workers + 1 writer")
print(f"   預估吞吐: ~130 筆/秒 (Photon 極限)")

# ── Photon API 設定 ─────────────────────────────
PHOTON_BASE = "http://localhost:2322/api"

# ── httpx Client with connection pooling ─────────
# 每個 worker 有自己的 client（thread-safe 但避免競爭）
def make_httpx_client():
    return httpx.Client(
        timeout=httpx.Timeout(10.0),
        limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
        follow_redirects=True,
    )

# ── twaddr 街道映射表 + BBOX 限制 ────────────────
import json
from pathlib import Path

BBOX_MAP = {
    '北投': ('121.48,25.12,121.54,25.17'), '士林': ('121.51,25.07,121.56,121.59'),
    '大同': ('121.50,25.05,121.53,25.08'), '中山': ('121.51,25.05,121.53,25.08'),
    '松山': ('121.53,25.04,121.57,25.07'), '信義': ('121.54,25.02,121.59,25.06'),
    '大安': ('121.52,25.01,121.56,25.05'), '萬華': ('121.49,25.02,121.52,25.05'),
    '中正': ('121.50,25.02,121.53,25.05'), '南港': ('121.57,25.04,121.62,25.08'),
    '內湖': ('121.56,25.05,121.62,25.11'), '文山': ('121.54,24.98,121.60,25.04'),
    '永和': ('121.48,24.98,121.54,25.03'), '中和': ('121.48,24.97,121.53,25.02'),
    '板橋': ('121.44,24.97,121.50,25.03'), '新莊': ('121.43,25.03,121.48,25.08'),
    '三重': ('121.44,25.03,121.48,25.08'), '樹林': ('121.38,24.93,121.43,24.98'),
    '土城': ('121.42,24.93,121.47,24.98'), '鶯歌': ('121.35,24.93,121.40,24.97'),
    '三峽': ('121.30,24.90,121.36,24.95'), '淡水': ('121.40,25.15,121.45,25.20'),
    '蘆洲': ('121.40,25.08,121.45,25.13'), '汐止': ('121.57,25.02,121.63,25.08'),
    '新店': ('121.50,24.93,121.57,24.98'), '桃園': ('121.20,24.95,121.30,25.02'),
    '中壢': ('121.20,24.92,121.28,24.97'), '竹北': ('121.00,24.78,121.08,24.87'),
    '新竹': ('120.95,24.78,121.02,24.85'), '香山': ('120.95,24.82,121.02,24.88'),
}

def _load_road_map() -> dict:
    """載入 twaddr 街道映射表"""
    dataset_path = Path(__file__).parent / "utils" / "twaddr_dataset.json"
    try:
        with open(dataset_path) as f:
            dataset = json.load(f)
        return dataset.get('roadTrie', {})
    except FileNotFoundError:
        print(f"⚠️ 找不到 {dataset_path}，將直接用中文查詢")
        return {}

ROAD_MAP = _load_road_map()


def _extract_region(addr: str) -> str | None:
    """從地址提取行政區"""
    for region in BBOX_MAP:
        if region in addr:
            return region
    return None


def _extract_street_core(addr: str) -> str:
    """從地址提取街道核心名稱"""
    street = re.sub(r'.*[縣市區鄉鎮]', '', addr)
    street = re.sub(r'\d+[號棟層樓室間弄巷段]', '', street)
    street = re.sub(r'[一二三四五六七八九十百千]+[段巷弄號]', '', street)
    return street.strip()


def query_photon(client: httpx.Client, query: str, bbox: str | None = None) -> tuple | None:
    """查詢本地 Photon API，回傳 (lat, lon) 或 None"""
    params = {'q': query, 'limit': '5'}
    if bbox:
        params['bbox'] = bbox
    try:
        resp = client.get(PHOTON_BASE, params=params)
        data = resp.json()
        features = data.get('features', [])
        
        # 過濾：只保留 name 包含查詢關鍵字的結果
        for f in features:
            props = f['properties']
            name = props.get('name', '')
            if any(c in name for c in query):
                coords = f['geometry']['coordinates']
                return (float(coords[1]), float(coords[0]))
        
        # 有 bbox 限制時回傳第一個結果
        if features and bbox:
            coords = features[0]['geometry']['coordinates']
            return (float(coords[1]), float(coords[0]))
    except Exception:
        pass
    return None


# ── diskcache 持久化快取 ─────────────────────────
import diskcache as dc

geo_cache_dir = "/opt/data/home/housing-tracker/backend/.geocode_cache"
geo_cache_store = dc.Cache(geo_cache_dir, size_limit=1024**3)

class GeoCache:
    """Thread-safe wrapper around diskcache"""
    def __init__(self):
        self.lock = threading.Lock()
        self.hits = 0
        self.misses = 0
    
    def get(self, key):
        with self.lock:
            val = geo_cache_store.get(key, default=None)
            if val is not None:
                self.hits += 1
                return val
            self.misses += 1
            return None
    
    def put(self, key, value):
        with self.lock:
            geo_cache_store[key] = value
    
    def stats(self):
        with self.lock:
            total = self.hits + self.misses
            rate = self.hits / total * 100 if total > 0 else 0
            store_size = len(geo_cache_store)
            return f"DiskCache: {store_size} entries, Hit: {self.hits}, Miss: {self.misses}, Rate: {rate:.1f}%"

geo_cache = GeoCache()


def geocode_address(address: str, city: str = "", district: str = "") -> tuple | None:
    """
    Geocode 一個地址，回傳 (lat, lon) 或 None
    
    策略：
    1. 查 diskcache 持久化快取
    2. 正規化地址（全形→半形、中文數字→阿拉伯數字）
    3. 去除樓層資訊
    4. 若地址無縣市，用 DB 的 city/district 補齊
    5. 提取行政區 → BBOX 限制
    6. 提取街道核心名稱 → twaddr 映射英文
    7. 查詢本地 Photon API（twaddr 英文優先，再試中文）
    """
    # 建立 cache key
    cache_key = f"{address}|{city}|{district}"
    
    # 先查快取
    cached = geo_cache.get(cache_key)
    if cached is not None:
        return cached
    
    # 正規化
    normalized = normalize_address(address)
    
    # 去除樓層資訊
    clean_addr = normalized
    clean_addr = re.sub(r'\d+(?:[.-]\d+)?(?:F|樓)', '', clean_addr)
    clean_addr = re.sub(r'之\d+', '', clean_addr)
    clean_addr = re.sub(r'地下[\d室層樓]+', '', clean_addr)
    clean_addr = re.sub(r'\s+', ' ', clean_addr).strip()
    
    # 若地址無縣市，用 DB 的 city/district 補齊
    if not re.search(r'(市|縣)', clean_addr) and city:
        normalized_city = normalize_address(city)
        clean_addr = f"{normalized_city}{district if district else ''}{clean_addr}"
    
    # 重新正規化
    normalized = normalize_address(clean_addr)
    
    # 提取行政區 → BBOX
    region = _extract_region(normalized)
    bbox = BBOX_MAP.get(region)
    
    # 提取街道核心名稱
    street_core = _extract_street_core(normalized)
    
    # twaddr 映射英文街道名
    eng_street = ROAD_MAP.get(street_core, None)
    
    # 取得 thread-local httpx client
    client = getattr(threading.current_thread(), '_httpx_client', None)
    if client is None:
        client = make_httpx_client()
        threading.current_thread()._httpx_client = client
    
    result = None
    
    # 策略 1: twaddr 英文街道名 + bbox
    if eng_street:
        result = query_photon(client, eng_street, bbox=bbox)
        if result:
            geo_cache.put(cache_key, result)
            return result
    
    # 策略 2: 中文街道名 + bbox
    if street_core:
        result = query_photon(client, street_core, bbox=bbox)
        if result:
            geo_cache.put(cache_key, result)
            return result
    
    # 策略 3: 完整中文地址（fallback）
    result = query_photon(client, normalized)
    if result:
        geo_cache.put(cache_key, result)
        return result
    
    # 全部失敗
    geo_cache.put(cache_key, None)
    return None


# ── Sentinel 物件（用來通知 writer 結束）────────
_SENTINEL = object()


def geocode_worker(task_queue: queue.Queue, result_queue: queue.Queue, stats: dict, stats_lock: threading.Lock, print_lock: threading.Lock):
    """
    Geocoding worker：從 task_queue 取值，geocode 後丟到 result_queue。
    收到 _SENTINEL 就結束。
    """
    local_client = make_httpx_client()
    threading.current_thread()._httpx_client = local_client
    
    while True:
        item = task_queue.get()
        if item is _SENTINEL:
            break
        
        idx, city, district, address, trade_count = item
        
        result = geocode_address(address, city, district)
        
        with stats_lock:
            stats['total'] += 1
            if result:
                stats['success'] += 1
            else:
                stats['failed'] += 1
        
        # 印出結果
        display_addr = address[:40].replace('\n', ' ')
        with print_lock:
            if result:
                print(f"[{idx:>5}] {trade_count:>4}x | {display_addr}... → ✓ ({result[0]:.4f}, {result[1]:.4f})")
            else:
                print(f"[{idx:>5}] {trade_count:>4}x | {display_addr}... → ✗ 找不到")
        
        # 丟到 result queue（成功才送）
        if result:
            result_queue.put((city, district, address, result[0], result[1]))
        
        task_queue.task_done()
    
    local_client.close()


def writer_thread(result_queue, write_conn, stats, stats_lock, start_time):
    """
    Writer thread：從 result_queue 收集結果，批次寫入 DB。
    收到 _SENTINEL 就 flush 剩餘資料並結束。
    """
    cur = write_conn.cursor()
    cur.execute("SET synchronous_commit = OFF")
    write_conn.commit()
    
    batch = []
    total_updated = 0
    batch_num = 0
    last_flush = time.time()
    
    while True:
        item = result_queue.get()
        if item is _SENTINEL:
            # Flush 剩餘
            if batch:
                _flush_batch(cur, write_conn, batch, stats, stats_lock, start_time)
                total_updated += stats['updated']
                batch_num += 1
                stats['updated'] = 0
            break
        
        batch.append(item)
        
        # 批次大小達標或超過時間間隔 → flush
        now = time.time()
        if len(batch) >= WRITE_BATCH_SIZE or (now - last_flush > WRITE_FLUSH_INTERVAL and batch):
            rows = _flush_batch(cur, write_conn, batch, stats, stats_lock, start_time)
            total_updated += rows
            batch_num += 1
            last_flush = now
            batch = []
        
        result_queue.task_done()
    
    cur.close()
    
    print(f"\n💾 Writer 完成: 共 {batch_num} 批次, 累計更新 {total_updated:,} 筆交易")
    return total_updated


def _flush_batch(cur, conn, batch, stats, stats_lock, start_time):
    """執行一筆批次寫入，回傳更新的 rowcount"""
    if not batch:
        return 0
    
    placeholders = ", ".join(["(%s, %s, %s, %s, %s)"] * len(batch))
    flat_data = []
    for u_city, u_district, u_addr, u_lat, u_lon in batch:
        flat_data.extend([u_lat, u_lon, u_addr, u_city, u_district])
    
    sql = f"""
        WITH new_coords AS (
            SELECT * FROM (VALUES {placeholders}) 
            AS t(lat, lon, address, city, district)
        )
        UPDATE trades t SET lat = nc.lat, lon = nc.lon
        FROM new_coords nc
        WHERE t.address = nc.address
        AND t.city = nc.city
        AND t.district = nc.district
        AND (t.lat IS NULL OR t.lon IS NULL)
    """
    
    cur.execute(sql, flat_data)
    rows = cur.rowcount
    conn.commit()
    
    elapsed = time.time() - start_time
    with stats_lock:
        prev_total = stats['total']
        prev_success = stats['success']
        prev_failed = stats['failed']
    
    print(f"  💾 Batch #{stats.get('batch_num', 0) + 1}: {rows} 筆寫入 | "
          f"累計 {prev_success} 成功 / {prev_failed} 失敗 / {prev_total} 總計 | "
          f"{geo_cache.stats()} | "
          f"耗時 {elapsed/60:.1f}min")
    
    with stats_lock:
        stats['batch_num'] = stats.get('batch_num', 0) + 1
    
    return rows


def main():
    print("=" * 60)
    print("批次 Geocoding v6 — Producer/Consumer 架構")
    print(f"  {GEO_WORKERS} geocoding workers + 1 writer thread")
    print("=" * 60)
    if DRY_RUN:
        print("⚠️  DRY-RUN 模式：只預覽前 20 筆，不寫入 DB")
    if TEST_LIMIT:
        print(f"🧪 TEST 模式：只測試前 {TEST_LIMIT} 個唯一地址")
    print()

    # ============================================
    # DB 連線
    # ============================================
    read_conn = psycopg2.connect(DB_URL)
    read_conn.autocommit = False
    
    write_conn = psycopg2.connect(DB_URL)
    write_conn.autocommit = False
    
    stats_cur = read_conn.cursor()

    # ============================================
    # Step 1: 統計目前狀態（用 pg_stat 避免全表掃描）
    # ============================================
    stats_cur.execute("""
        SELECT reltuples::bigint AS est_rows 
        FROM pg_class WHERE relname = 'trades'
    """)
    total = stats_cur.fetchone()[0]

    # 用 sample 估算有座標的比例
    stats_cur.execute("""
        SELECT 
            SUM(CASE WHEN lat IS NOT NULL AND lon IS NOT NULL THEN 1 ELSE 0 END)::float / COUNT(*) AS ratio
        FROM trades TABLESAMPLE SYSTEM(1)
    """)
    row = stats_cur.fetchone()
    ratio = row[0] if row and row[0] else 0
    has_coords = int(total * ratio)

    needs_geo = total - has_coords
    print(f"Step 1: 統計（預估）")
    print(f"  總筆數: {total:,}")
    print(f"  已有座標: ~{has_coords:,} ({ratio*100:.1f}%)")
    print(f"  需 Geocoding: ~{needs_geo:,}")
    print()

    if needs_geo == 0:
        print("✅ 全部已完成！")
        stats_cur.close()
        read_conn.close()
        write_conn.close()
        return

    # ============================================
    # Step 2: 流式讀取唯一地址（優化查詢避免全表排序）
    # ============================================
    print("Step 2: 建立 Server-side cursor（流式讀取）...")
    
    server_cursor_name = 'geocode_stream'
    # 移除 ORDER BY — 400 萬筆 GROUP BY + 排序需要全表聚合，太慢
    # 反正最終會跑完所有地址，順序不重要
    unique_query = """
        SELECT t.city, t.district, t.address, 1 as trade_count
        FROM trades t
        WHERE (t.lat IS NULL OR t.lon IS NULL)
        AND t.address IS NOT NULL
        AND LENGTH(t.address) >= 5
        AND t.address NOT LIKE '%%地號%%'
        AND t.address NOT LIKE '%%建號%%'
        AND TRIM(t.address) NOT LIKE '地下%%'
        AND TRIM(t.address) NOT LIKE '%%地下[室層樓]'
        AND TRIM(t.address) NOT LIKE '%%地下一%'
        AND t.address NOT LIKE '%%公共設施%%'
        AND t.address NOT LIKE '%%共同使用%%'
        AND t.address NOT LIKE '%%號至%%'
        AND t.address NOT LIKE '%%工業區'
        AND t.address NOT LIKE '%%里 '
        GROUP BY t.city, t.district, t.address
    """
    
    if TEST_LIMIT:
        unique_query += f" LIMIT {TEST_LIMIT}"

    server_cur = read_conn.cursor(server_cursor_name)
    server_cur.itersize = 500
    server_cur.execute(unique_query)
    
    print(f"  ✓ Server-side cursor '{server_cursor_name}' 已建立")
    print()

    if DRY_RUN and not TEST_LIMIT:
        print("DRY-RUN: 只測試前 20 筆\n")

    # ============================================
    # Step 3: Producer/Consumer 管道
    # ============================================
    print("Step 3: 開始 Geocoding...\n")

    # Queues
    task_queue = queue.Queue(maxsize=500)       # 任務佇列（有限制以控制記憶體）
    result_queue = queue.Queue(maxsize=1000)    # 結果佇列
    
    # Shared stats
    stats_lock = threading.Lock()
    print_lock = threading.Lock()
    stats = {'total': 0, 'success': 0, 'failed': 0, 'batch_num': 0, 'updated': 0}
    start_time = time.time()

    # ── 啟動 Writer Thread ──
    if DRY_RUN:
        # DRY-RUN 模式下 writer 只計數不寫入
        def dry_writer():
            count = 0
            while True:
                item = result_queue.get()
                if item is _SENTINEL:
                    break
                count += 1
                result_queue.task_done()
            print(f"\n⚠️  DRY-RUN: 跳過寫入 {count} 筆")
        
        writer_t = threading.Thread(target=dry_writer, daemon=True)
    else:
        writer_t = threading.Thread(
            target=writer_thread,
            args=(result_queue, write_conn, stats, stats_lock, start_time),
            daemon=True
        )
    writer_t.start()

    # ── 啟動 Geocoding Workers ──
    workers = []
    for i in range(GEO_WORKERS):
        t = threading.Thread(
            target=geocode_worker,
            args=(task_queue, result_queue, stats, stats_lock, print_lock),
            daemon=True
        )
        t.start()
        workers.append(t)

    # ── Producer: 從 DB 讀取並餵給 task_queue ──
    dry_run_count = 0
    dry_run_limit = 20 if DRY_RUN else 0
    global_idx = 0
    
    while True:
        batch = server_cur.fetchmany(500)
        if not batch:
            break
        
        for city, district, address, trade_count in batch:
            if DRY_RUN and not TEST_LIMIT and dry_run_count >= dry_run_limit:
                break
            
            global_idx += 1
            task_queue.put((global_idx, city, district, address, trade_count))
            dry_run_count += 1
        
        if DRY_RUN and not TEST_LIMIT and dry_run_count >= dry_run_limit:
            break
    
    server_cur.close()
    
    # 等所有任務被處理完
    task_queue.join()
    
    # 通知 workers 結束（送 sentinel）
    for _ in range(GEO_WORKERS):
        task_queue.put(_SENTINEL)
    
    # 等 workers 結束
    for t in workers:
        t.join()
    
    # 通知 writer 結束
    result_queue.put(_SENTINEL)
    
    # 等 writer 結束
    writer_t.join()

    total_time = time.time() - start_time

    print()
    print("=" * 60)
    print(f"Geocoding 完成:")
    print(f"  成功: {stats['success']}")
    print(f"  失敗: {stats['failed']}")
    print(f"  耗時: {total_time/60:.1f} 分鐘")
    print(f"  平均速度: {(stats['total']) / total_time:.2f} 筆/秒")
    print(f"  {geo_cache.stats()}")
    print("=" * 60)
    print()

    # ============================================
    # Step 4: 最終統計（用 sample 避免全表掃描）
    # ============================================
    stats_cur.execute("""
        SELECT 
            SUM(CASE WHEN lat IS NOT NULL AND lon IS NOT NULL THEN 1 ELSE 0 END)::float / COUNT(*) AS ratio
        FROM trades TABLESAMPLE SYSTEM(1)
    """)
    row = stats_cur.fetchone()
    final_ratio = row[0] if row and row[0] else 0
    final_coords = int(total * final_ratio)
    
    print("最終結果:")
    print(f"  已有座標: ~{final_coords:,}/{total:,} (~{final_ratio*100:.1f}%)")
    print(f"  本次新增: ~{final_coords - has_coords:,} 筆")
    print("=" * 60)

    # 清理
    stats_cur.close()
    read_conn.close()
    write_conn.close()
    print("\n✅ 批次處理完成！")


if __name__ == "__main__":
    main()
