"""
批次填充 trade_amenities — 直接呼叫 Nominatim
差異更新：跳過已有 POI 的交易
每筆交易只查 6 次 API，使用單一關鍵字 + radius 模式
"""
import sys
import os
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

# Rate limiting - Nominatim requires 1s between requests
REQUEST_INTERVAL = 1.2
last_request_time = 0

DIMENSIONS = [
    ("transit", "捷運站", 1000, 8),
    ("school", "學校", 1500, 6),
    ("hospital", "醫院", 1200, 5),
    ("shop", "7-11", 800, 8),
    ("park", "公園", 1000, 5),
    ("restaurant", "餐廳", 600, 10),
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
    """Search Nominatim with viewbox."""
    radius_deg = radius_m / 111320
    vb = f"{lon-radius_deg:.4f},{lat+radius_deg:.4f},{lon+radius_deg:.4f},{lat-radius_deg:.4f}"
    url = (
        f"{NOMINATIM_BASE}/search?format=json&q={urllib.parse.quote(keyword)}"
        f"&limit={limit}&viewbox={vb}&bounded=1&countrycodes=TW&addressdetails=0"
    )
    
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
                if dist <= radius_m:
                    name = r.get("display_name", "").split(",")[0].strip() or "未知"
                    items.append({"name": name, "distance": round(dist), "lat": rlat, "lon": rlon})
            return items
    except Exception as e:
        return []


def write_progress(done, total, success, failed, api_calls):
    """Write progress to file for monitoring."""
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

    # Ensure table exists
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
        # Cache by rounded coords (avoid duplicate API calls for same location)
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

        # Progress every 25 trades
        if (i + 1) % 25 == 0 or i == total - 1:
            write_progress(i + 1, total, success, failed, api_calls)
            # Also commit periodically
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
