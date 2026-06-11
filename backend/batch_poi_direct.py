"""
批次填充 trade_amenities — 直接呼叫 Nominatim (繞過後端 API)
差異更新：跳過已有 POI 的交易
"""
import sys
import time
import json
import math
import urllib.request
import urllib.parse
import psycopg2

# Force unbuffered output
sys.stdout.reconfigure(line_buffering=True)

DB_URL = "postgresql://hermes@localhost:5432/housing_tracker"
NOMINATIM_BASE = "https://nominatim.openstreetmap.org"

# Rate limiting
REQUEST_INTERVAL = 1.0  # seconds between requests (Nominatim policy)
last_request_time = 0

DIMENSIONS = {
    "transit": {"query": "捷運站 MRT 火車站 bus stop 公車站", "limit": 8},
    "education": {"query": "學校 kindergarten university 國小 國中 高中 大學", "limit": 6},
    "medical": {"query": "醫院 hospital 診所 clinic", "limit": 5},
    "shopping": {"query": "7-11 全家 萊爾富 OK超商 全聯 超市 supermarket mart", "limit": 8},
    "leisure": {"query": "公園 park 圖書館 library 博物館", "limit": 5},
    "dining": {"query": "餐廳 restaurant 咖啡廳 cafe 美食", "limit": 10},
}

CATEGORY_MAP = {
    "transit": "transit",
    "education": "school",
    "medical": "hospital",
    "shopping": "shop",
    "leisure": "park",
    "dining": "restaurant",
}


def haversine_m(lat1, lon1, lat2, lon2):
    R = 6371000
    rlat1, rlon1, rlat2, rlon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    dlat = rlat2 - rlat1
    dlon = rlon2 - rlon1
    a = math.sin(dlat/2)**2 + math.cos(rlat1)*math.cos(rlat2)*math.sin(dlon/2)**2
    return R * 2 * math.asin(math.sqrt(a))


def rate_limit():
    global last_request_time
    elapsed = time.time() - last_request_time
    if elapsed < REQUEST_INTERVAL:
        time.sleep(REQUEST_INTERVAL - elapsed)
    last_request_time = time.time()


def search_pois(keyword, lat, lon, radius_m, limit):
    """Search Nominatim for POIs."""
    radius_deg = radius_m / 111320
    vb = f"{lon-radius_deg:.4f},{lat+radius_deg:.4f},{lon+radius_deg:.4f},{lat-radius_deg:.4f}"
    url = (
        f"{NOMINATIM_BASE}/search?format=json&q={urllib.parse.quote(keyword)}"
        f"&limit={limit}&viewbox={vb}&bounded=1&countrycodes=TW&addressdetails=0"
    )
    
    rate_limit()
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "HousingTracker-Batch/1.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            results = json.loads(resp.read().decode("utf-8"))
            items = []
            for r in results:
                rlat = float(r.get("lat", lat))
                rlon = float(r.get("lon", lon))
                dist = haversine_m(lat, lon, rlat, rlon)
                if dist <= radius_m * 1.2:  # slight buffer
                    name = r.get("display_name", "").split(",")[0].strip() or "未知"
                    items.append({"name": name, "distance": round(dist), "lat": rlat, "lon": rlon})
            return items
    except Exception as e:
        print(f"  ⚠ API error: {e}")
        return []


def main():
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
    print(f"需查詢 POI: {total} 筆\n")

    success = 0
    failed = 0
    api_calls = 0
    cache = {}

    for i, (tid, lat, lon) in enumerate(trades):
        # Cache by rounded coords
        cache_key = f"{lat:.3f}_{lon:.3f}"
        
        if cache_key not in cache:
            cache[cache_key] = {}
            for dim_key, dim_info in DIMENSIONS.items():
                pois = search_pois(dim_info["query"], lat, lon, 1000, dim_info["limit"])
                cache[cache_key][dim_key] = pois
                api_calls += 1
        
        pois_cache = cache[cache_key]
        inserted = 0
        for dim_key, pois in pois_cache.items():
            db_cat = CATEGORY_MAP.get(dim_key)
            if not db_cat:
                continue
            for item in pois:
                try:
                    cur.execute(
                        """INSERT INTO trade_amenities 
                           (trade_id, category, amenity_name, distance, lat, lon) 
                           VALUES (%s, %s, %s, %s, %s, %s) 
                           ON CONFLICT DO NOTHING""",
                        (tid, db_cat, item["name"], item["distance"], item.get("lat"), item.get("lon"))
                    )
                    inserted += 1
                except Exception:
                    pass

        if inserted > 0:
            success += 1
        else:
            failed += 1

        if (i + 1) % 50 == 0 or i == total - 1:
            pct = (i + 1) / total * 100
            elapsed = time.time() - start_time
            eta = elapsed / (i + 1) * (total - i - 1) if i < total - 1 else 0
            print(f"[{i+1}/{total}] {pct:.1f}% | 成功 {success}, 失敗 {failed} | API呼叫 {api_calls} | ETA {eta/60:.1f}分")

    elapsed = time.time() - start_time
    print(f"\n{'='*60}")
    print(f"完成! 耗時 {elapsed/60:.1f} 分鐘")
    print(f"成功 {success} 筆, 無資料 {failed} 筆")
    print(f"API 總呼叫數: {api_calls}")
    
    cur.execute("SELECT COUNT(DISTINCT trade_id) FROM trade_amenities")
    final_poi = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM trade_amenities")
    final_records = cur.fetchone()[0]
    print(f"總計: {final_poi} 筆交易有 POI ({final_records} 條設施紀錄)")
    
    cur.close()
    conn.close()


if __name__ == "__main__":
    start_time = time.time()
    main()
