"""
批次填充 trade_amenities — Nominatim 穩定版
- 每筆交易查 6 次 API (1.5 秒間隔)
- 支援斷點續傳
- 進度寫入檔案
"""
import sys
import time
import json
import math
import urllib.request
import urllib.parse
import psycopg2

sys.stdout.reconfigure(line_buffering=True)

DB_URL = "postgresql://hermes@localhost:5432/housing_tracker"
NOMINATIM_BASE = "https://nominatim.openstreetmap.org"
PROGRESS_FILE = "/tmp/poi_progress.txt"

REQUEST_INTERVAL = 1.5  # Conservative rate limit
last_request_time = 0

DIMENSIONS = [
    ("transit", "捷運站 MRT", 1000, 8),
    ("school", "學校", 1500, 6),
    ("hospital", "醫院", 1200, 5),
    ("shop", "7-11", 800, 8),
    ("park", "公園 park", 1000, 5),
    ("restaurant", "餐廳 restaurant", 800, 10),
]


def haversine_m(lat1, lon1, lat2, lon2):
    R = 6371000
    rlat1, rlon1, rlat2, rlon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    dlat = rlat2 - rlat1
    dlon = rlon2 - rlon1
    a = math.sin(dlat/2)**2 + math.cos(rlat1)*math.cos(rlat2)*math.sin(dlon/2)**2
    return R * 2 * math.asin(min(1.0, math.sqrt(a)))


def rate_limit():
    global last_request_time
    elapsed = time.time() - last_request_time
    if elapsed < REQUEST_INTERVAL:
        time.sleep(REQUEST_INTERVAL - elapsed)
    last_request_time = time.time()


def search_pois(keyword, lat, lon, radius_m, limit):
    """Search Nominatim with bounded viewbox."""
    radius_deg = radius_m / 111320
    vb = f"{lon-radius_deg:.4f},{lat+radius_deg:.4f},{lon+radius_deg:.4f},{lat-radius_deg:.4f}"
    url = (
        f"{NOMINATIM_BASE}/search?format=json&q={urllib.parse.quote(keyword)}"
        f"&limit={limit}&viewbox={vb}&bounded=1&countrycodes=TW&addressdetails=0"
    )
    
    for attempt in range(3):
        rate_limit()
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "HousingTracker-Batch/1.0"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                results = json.loads(resp.read().decode("utf-8"))
                items = []
                for r in results:
                    rlat = float(r.get("lat", lat))
                    rlon = float(r.get("lon", lon))
                    dist = haversine_m(lat, lon, rlat, rlon)
                    if dist <= radius_m * 1.2:
                        name = r.get("display_name", "").split(",")[0].strip() or "未知"
                        items.append({"name": name, "distance": round(dist), "lat": rlat, "lon": rlon})
                return sorted(items, key=lambda x: x["distance"])[:5]
        except Exception as e:
            err_msg = str(e)
            if "429" in err_msg or (hasattr(e, 'code') and e.code == 429):
                wait = 10 * (attempt + 1)
                print(f"  ⚠ 429 on '{keyword}', waiting {wait}s (attempt {attempt+1}/3)", flush=True)
                time.sleep(wait)
                continue
            else:
                print(f"  ⚠ Error on '{keyword}': {err_msg[:80]}", flush=True)
                return []
    
    print(f"  ✗ Exhausted retries for '{keyword}'", flush=True)
    return []


def write_progress(done, total, success, failed, api_calls):
    pct = done / total * 100 if total > 0 else 0
    elapsed = time.time() - start_time
    eta = elapsed / done * (total - done) if done > 0 else 0
    line = f"[{done}/{total}] {pct:.1f}% | OK:{success} NO:{failed} | API:{api_calls} | ETA:{eta/60:.1f}min"
    with open(PROGRESS_FILE, "w") as f:
        f.write(line + "\n")
    print(line, flush=True)


def main():
    global start_time
    start_time = time.time()
    
    conn = psycopg2.connect(DB_URL)
    conn.autocommit = True
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS trade_amenities (
            id SERIAL PRIMARY KEY,
            trade_id INTEGER NOT NULL REFERENCES trades(id),
            category VARCHAR(50) NOT NULL,
            amenity_name VARCHAR(255) NOT NULL,
            distance INTEGER NOT NULL,
            lat REAL,
            lon REAL,
            UNIQUE(trade_id, category, amenity_name)
        )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_trade_amenities_trade_id ON trade_amenities(trade_id)")

    # Get trades needing POI
    cur.execute("""
        SELECT t.id, t.lat, t.lon 
        FROM trades t
        WHERE t.lat IS NOT NULL AND t.lon IS NOT NULL
        AND NOT EXISTS (SELECT 1 FROM trade_amenities a WHERE a.trade_id = t.id)
        ORDER BY t.id
    """)
    trades = cur.fetchall()
    total = len(trades)
    print(f"需查詢 POI: {total} 筆\n", flush=True)

    success = 0
    failed = 0
    api_calls = 0
    cache = {}

    for i, (tid, lat, lon) in enumerate(trades):
        cache_key = f"{lat:.3f}_{lon:.3f}"
        
        if cache_key not in cache:
            cache[cache_key] = {}
            for cat, keyword, radius, limit in DIMENSIONS:
                pois = search_pois(keyword, lat, lon, radius, limit)
                cache[cache_key][cat] = pois
                api_calls += 1
        
        pois_cache = cache[cache_key]
        inserted = 0
        for cat, pois in pois_cache.items():
            for item in pois:
                try:
                    cur.execute(
                        """INSERT INTO trade_amenities 
                           (trade_id, category, amenity_name, distance, lat, lon) 
                           VALUES (%s, %s, %s, %s, %s, %s) 
                           ON CONFLICT DO NOTHING""",
                        (tid, cat, item["name"], item["distance"], item.get("lat"), item.get("lon"))
                    )
                    inserted += 1
                except Exception:
                    pass

        if inserted > 0:
            success += 1
        else:
            failed += 1

        if (i + 1) % 25 == 0 or i == total - 1:
            write_progress(i + 1, total, success, failed, api_calls)
            conn.commit()

    elapsed = time.time() - start_time
    print(f"\n{'='*60}", flush=True)
    print(f"完成! 耗時 {elapsed/60:.1f} 分鐘", flush=True)
    print(f"成功 {success} 筆, 無資料 {failed} 筆", flush=True)
    print(f"API 總呼叫數: {api_calls}", flush=True)
    
    cur.execute("SELECT COUNT(DISTINCT trade_id) FROM trade_amenities")
    final_poi = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM trade_amenities")
    final_records = cur.fetchone()[0]
    print(f"總計: {final_poi} 筆交易有 POI ({final_records} 條設施紀錄)", flush=True)
    
    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
