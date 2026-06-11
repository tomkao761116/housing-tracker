"""
批次填充 trade_amenities — Overpass API 版
- 一次請求取得所有 6 維度 POI（取代舊版 Nominatim × 6 次）
- 支援斷點續傳、進度持久化
- 只處理尚未有 POI 的交易
"""
import sys
import time
import json
import math
import random
import urllib.request
import urllib.parse
import psycopg2

sys.stdout.reconfigure(line_buffering=True)

DB_URL = "postgresql://hermes@localhost:5432/housing_tracker"
OVERPASS_URL = "https://overpass-api.de/api/interpreter"
PROGRESS_FILE = "/tmp/poi_overpass_progress.json"

# Rate limiting
BASE_DELAY = 1.5
MAX_RETRIES = 3
BACKOFF_MULTIPLIER = 2.0
last_request_time = 0

DIMENSIONS = {
    "transit": {
        "label": "交通", "radius_m": 1000, "max_count": 8,
        "tags": ['"railway"="station"', '"public_transport"="stop_position"', '"highway"="bus_stop"'],
    },
    "education": {
        "label": "教育", "radius_m": 1500, "max_count": 6,
        "tags": ['"amenity"~"school|kindergarten|university|college"'],
    },
    "medical": {
        "label": "醫療", "radius_m": 1200, "max_count": 5,
        "tags": ['"amenity"~"hospital|clinic|doctor|pharmacy"'],
    },
    "shopping": {
        "label": "購物", "radius_m": 800, "max_count": 8,
        "tags": ['"shop"~"convenience|supermarket|mall|department_store"'],
    },
    "leisure": {
        "label": "休閒", "radius_m": 1000, "max_count": 5,
        "tags": ['"leisure"="park"', '"amenity"="library"', '"tourism"="museum"'],
    },
    "dining": {
        "label": "餐飲", "radius_m": 600, "max_count": 10,
        "tags": ['"amenity"~"restaurant|cafe|fast_food|bar|food_court"'],
    },
}

CATEGORY_MAP = {
    "transit": "transit",
    "education": "school",
    "medical": "hospital",
    "shopping": "shop",
    "leisure": "park",
    "dining": "restaurant",
}


def haversine(lat1, lon1, lat2, lon2):
    R = 6371000
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def rate_limit():
    global last_request_time
    elapsed = time.time() - last_request_time
    jitter = random.uniform(0.3, 1.0)
    sleep_time = max(0, BASE_DELAY + jitter - elapsed)
    if sleep_time > 0:
        time.sleep(sleep_time)
    last_request_time = time.time()


def build_overpass_query(lat, lon):
    """Build single Overpass query for ALL dimensions."""
    parts = []
    for dim_info in DIMENSIONS.values():
        r = dim_info["radius_m"]
        for tag_expr in dim_info["tags"]:
            parts.append(f'node(around:{r},{lat},{lon})[{tag_expr}]')
    union = "\n  ;".join(parts)
    return f"""[out:json][timeout:30];
(
  {union};
);
out;"""


def classify_poi(element):
    """Classify an Overpass element into dimension categories."""
    tags = element.get("tags", {})
    dims = []
    amenity = tags.get("amenity", "")
    shop = tags.get("shop", "")
    railway = tags.get("railway", "")
    highway = tags.get("highway", "")
    leisure_tag = tags.get("leisure", "")
    tourism = tags.get("tourism", "")
    public_transport = tags.get("public_transport", "")

    if railway == "station" or public_transport == "stop_position" or highway == "bus_stop":
        dims.append("transit")
    if amenity in ("school", "kindergarten", "university", "college"):
        dims.append("education")
    if amenity in ("hospital", "clinic", "doctor", "pharmacy"):
        dims.append("medical")
    if shop in ("convenience", "supermarket", "mall", "department_store"):
        dims.append("shopping")
    if leisure_tag == "park" or amenity == "library" or tourism == "museum":
        dims.append("leisure")
    if amenity in ("restaurant", "cafe", "fast_food", "bar", "food_court"):
        dims.append("dining")
    return dims


def fetch_all_pois(lat, lon):
    """Fetch ALL dimension POIs in a SINGLE Overpass API call."""
    query = build_overpass_query(lat, lon)
    overpass_url = f"{OVERPASS_URL}?data={urllib.parse.quote(query)}"

    dimension_pois = {k: [] for k in DIMENSIONS}

    for attempt in range(MAX_RETRIES):
        rate_limit()
        try:
            req = urllib.request.Request(
                overpass_url,
                headers={"User-Agent": "HousingTracker-Batch/1.0", "Accept": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))

            elements = data.get("elements", [])
            for elem in elements:
                elem_lat = elem.get("lat")
                elem_lon = elem.get("lon")
                if elem_lat is None or elem_lon is None:
                    continue

                dist = haversine(lat, lon, elem_lat, elem_lon)
                name = elem.get("tags", {}).get("name", elem.get("tags", {}).get("amenity", "未知"))

                poi = {"name": name, "distance": round(dist), "lat": elem_lat, "lon": elem_lon}

                matched_dims = classify_poi(elem)
                for dim in matched_dims:
                    dim_info = DIMENSIONS[dim]
                    if dist <= dim_info["radius_m"]:
                        dimension_pois[dim].append(poi)

            return dimension_pois

        except Exception as e:
            err_msg = str(e)
            if attempt < MAX_RETRIES - 1:
                backoff = (BACKOFF_MULTIPLIER ** attempt) + random.uniform(1, 3)
                print(f"  ⚠ Retry {attempt+1}/{MAX_RETRIES}, waiting {backoff:.1f}s: {err_msg[:80]}", flush=True)
                time.sleep(backoff)
                continue
            print(f"  ✗ Failed at ({lat}, {lon}): {err_msg[:80]}", flush=True)
            return dimension_pois

    return dimension_pois


def save_progress(done, total, success, failed, api_calls):
    state = {
        "done": done, "total": total, "success": success,
        "failed": failed, "api_calls": api_calls,
        "timestamp": time.time(),
    }
    with open(PROGRESS_FILE, "w") as f:
        json.dump(state, f)
    pct = done / total * 100 if total > 0 else 0
    elapsed = time.time() - start_time
    eta = elapsed / done * (total - done) if done > 0 else 0
    print(f"[{done}/{total}] {pct:.1f}% | OK:{success} NO:{failed} | API:{api_calls} | ETA:{eta/60:.1f}min", flush=True)


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

    # Get trades needing POI (have coords but no amenities)
    cur.execute("""
        SELECT t.id, t.lat, t.lon, t.city, t.district
        FROM trades t
        WHERE t.lat IS NOT NULL AND t.lon IS NOT NULL
        AND NOT EXISTS (SELECT 1 FROM trade_amenities a WHERE a.trade_id = t.id)
        ORDER BY t.id
    """)
    trades = cur.fetchall()
    total = len(trades)
    print(f"需查詢 POI: {total} 筆\n", flush=True)

    # Load progress for resume
    resume_from = 0
    success = 0
    failed = 0
    api_calls = 0
    try:
        with open(PROGRESS_FILE) as f:
            state = json.load(f)
        resume_from = state.get("done", 0)
        success = state.get("success", 0)
        failed = state.get("failed", 0)
        api_calls = state.get("api_calls", 0)
        print(f"從進度恢復: 已處理 {resume_from} 筆\n", flush=True)
    except FileNotFoundError:
        pass

    # Coordinate cache: same coords → reuse POI results
    coord_cache = {}

    for i in range(resume_from, total):
        tid, lat, lon, city, district = trades[i]
        cache_key = f"{round(lat, 3)}_{round(lon, 3)}"

        if cache_key not in coord_cache:
            coord_cache[cache_key] = fetch_all_pois(lat, lon)
            api_calls += 1

        pois_by_dim = coord_cache[cache_key]

        # Insert into DB
        inserted = 0
        for dim_key, pois in pois_by_dim.items():
            db_category = CATEGORY_MAP.get(dim_key, dim_key)
            for item in pois[:5]:  # Top 5 per dimension
                try:
                    cur.execute(
                        """INSERT INTO trade_amenities
                           (trade_id, category, amenity_name, distance, lat, lon)
                           VALUES (%s, %s, %s, %s, %s, %s)
                           ON CONFLICT DO NOTHING""",
                        (tid, db_category, item["name"], item["distance"], item.get("lat"), item.get("lon")),
                    )
                    inserted += 1
                except Exception:
                    pass

        if inserted > 0:
            success += 1
        else:
            failed += 1

        if (i + 1) % 50 == 0 or i == total - 1:
            save_progress(i + 1, total, success, failed, api_calls)
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

    # Category breakdown
    cur.execute("""
        SELECT category, COUNT(*)::int as cnt, COUNT(DISTINCT trade_id)::int as unique_trades
        FROM trade_amenities GROUP BY category ORDER BY cnt DESC
    """)
    print("\nPOI 類別分佈:")
    for row in cur.fetchall():
        print(f"  {row[0]}: {row[1]:,} 筆 ({row[2]} 個交易)", flush=True)

    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
