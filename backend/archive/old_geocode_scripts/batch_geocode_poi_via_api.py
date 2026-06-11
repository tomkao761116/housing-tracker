"""
批次填充 trade_amenities — 使用後端 /api/amenities API (Nominatim)
差異更新：跳過已有 POI 的交易
"""
import time
import json
import urllib.request
import urllib.parse
import psycopg2

DB_URL = "postgresql://hermes@localhost:5432/housing_tracker"
API_URL = "http://localhost:8000/api/amenities"

# Map backend API category names to our table categories
CATEGORY_MAP = {
    "school": "school",
    "transit": "transit", 
    "hospital": "hospital",
    "shop": "shop",
    "park": "park",
    "mall": "shopping",
    "restaurant": "restaurant",
}


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
        AND NOT EXISTS (
            SELECT 1 FROM trade_amenities a WHERE a.trade_id = t.id
        )
        ORDER BY t.id
    """)
    trades = cur.fetchall()
    total = len(trades)
    print(f"需查詢 POI: {total} 筆\n")

    success = 0
    failed = 0
    cache = {}

    for i, (tid, lat, lon) in enumerate(trades):
        # Cache by rounded coords (avoid duplicate API calls for same location)
        cache_key = f"{lat:.3f}_{lon:.3f}"
        
        if cache_key in cache:
            pois_data = cache[cache_key]
        else:
            url = f"{API_URL}?lat={lat}&lon={lon}"
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "HousingTracker/1.0"})
                with urllib.request.urlopen(req, timeout=15) as resp:
                    pois_data = json.loads(resp.read().decode("utf-8"))
                    cache[cache_key] = pois_data
            except Exception as e:
                pois_data = {}
                print(f"[{i+1}/{total}] Trade #{tid} → ✗ API error: {e}")

        inserted = 0
        for api_cat, cat_info in pois_data.items():
            db_cat = CATEGORY_MAP.get(api_cat)
            if not db_cat:
                continue
            items = cat_info.get("items", [])
            for item in items:
                try:
                    cur.execute(
                        """INSERT INTO trade_amenities 
                           (trade_id, category, amenity_name, distance, lat, lon) 
                           VALUES (%s, %s, %s, %s, %s, %s) 
                           ON CONFLICT DO NOTHING""",
                        (tid, db_cat, item["name"], item["distance"], item.get("lat"), item.get("lon"))
                    )
                    inserted += 1
                except Exception as e:
                    pass  # Skip conflicts silently

        if inserted > 0:
            success += 1
        else:
            failed += 1

        if (i + 1) % 100 == 0:
            print(f"[{i+1}/{total}] 進度: 成功 {success}, 失敗 {failed}")

        # Rate limit - be polite to Nominatim
        time.sleep(0.3)

    print(f"\n{'='*60}")
    print(f"完成! 成功 {success} 筆, 無資料 {failed} 筆")
    
    cur.execute("SELECT COUNT(DISTINCT trade_id) FROM trade_amenities")
    final_poi = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM trade_amenities")
    final_records = cur.fetchone()[0]
    print(f"總計: {final_poi} 筆交易有 POI ({final_records} 條設施紀錄)")
    
    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
