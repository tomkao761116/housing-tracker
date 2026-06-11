"""
批次計算所有交易的評分 — 混合模式
- 有 trade_amenities 的交易：從 DB 計算（不需 API）
- 無 trade_amenities 但有座標：走 Overpass API 即時查詢
- 支援斷點續傳
"""
import sys
import math
import time
import json
import random
import urllib.request
import urllib.parse
from sqlalchemy import create_engine, text

sys.stdout.reconfigure(line_buffering=True)

DB_URL = "postgresql://hermes@localhost:5432/housing_tracker"
OVERPASS_URL = "https://overpass-api.de/api/interpreter"
PROGRESS_FILE = "/tmp/score_progress.json"

# Rate limiting for Overpass
BASE_DELAY = 1.5
MAX_RETRIES = 3
BACKOFF_MULTIPLIER = 2.0
last_request_time = 0

DIMENSIONS = {
    "transit": {"max_count": 8, "radius_m": 1000},
    "education": {"max_count": 6, "radius_m": 1500},
    "medical": {"max_count": 5, "radius_m": 1200},
    "shopping": {"max_count": 8, "radius_m": 800},
    "leisure": {"max_count": 5, "radius_m": 1000},
    "dining": {"max_count": 10, "radius_m": 600},
}

CATEGORY_TO_DIMENSION = {
    "transit": "transit", "school": "education", "hospital": "medical",
    "shop": "shopping", "park": "leisure", "restaurant": "dining",
}

# Weights based on Taiwan homebuyer priority surveys
WEIGHTS = {
    "transit": 0.28, "education": 0.20, "medical": 0.18,
    "shopping": 0.15, "leisure": 0.12, "dining": 0.07,
}
TOTAL_WEIGHT = sum(WEIGHTS.values())


def compute_dimension_score(pois, max_count, radius_m):
    """Score a single dimension 0–100 based on POI count & distance."""
    if not pois:
        return None
    count = len(pois)
    count_ratio = min(count / max_count, 1.0)
    count_score = 100 * math.log2(1 + count_ratio * 7) / math.log2(8)
    dist_scores = [math.exp(-p["distance"] / (radius_m * 0.4)) for p in pois[:5]]
    avg_dist_score = (sum(dist_scores) / len(dist_scores)) * 100 if dist_scores else 0
    combined = round(0.6 * count_score + 0.4 * avg_dist_score)
    return max(0, min(100, combined))


def rate_limit():
    global last_request_time
    elapsed = time.time() - last_request_time
    jitter = random.uniform(0.3, 1.0)
    sleep_time = max(0, BASE_DELAY + jitter - elapsed)
    if sleep_time > 0:
        time.sleep(sleep_time)
    last_request_time = time.time()


def haversine(lat1, lon1, lat2, lon2):
    R = 6371000
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


OVERPASS_TAGS = {
    "transit": ['"railway"="station"', '"public_transport"="stop_position"', '"highway"="bus_stop"'],
    "education": ['"amenity"~"school|kindergarten|university|college"'],
    "medical": ['"amenity"~"hospital|clinic|doctor|pharmacy"'],
    "shopping": ['"shop"~"convenience|supermarket|mall|department_store"'],
    "leisure": ['"leisure"="park"', '"amenity"="library"', '"tourism"="museum"'],
    "dining": ['"amenity"~"restaurant|cafe|fast_food|bar|food_court"'],
}


def build_overpass_query(lat, lon):
    parts = []
    for dim_key, tag_list in OVERPASS_TAGS.items():
        r = DIMENSIONS[dim_key]["radius_m"]
        for tag_expr in tag_list:
            parts.append(f'node(around:{r},{lat},{lon})[{tag_expr}]')
    union = "\n  ;".join(parts)
    return f"""[out:json][timeout:30];
(
  {union};
);
out;"""


def classify_poi(element):
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


def fetch_overpass_scores(lat, lon):
    """Fetch scores directly from Overpass (no DB write)."""
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

            for elem in data.get("elements", []):
                elem_lat = elem.get("lat")
                elem_lon = elem.get("lon")
                if elem_lat is None or elem_lon is None:
                    continue
                dist = haversine(lat, lon, elem_lat, elem_lon)
                poi = {"name": elem.get("tags", {}).get("name", "未知"), "distance": round(dist)}

                for dim in classify_poi(elem):
                    dim_info = DIMENSIONS[dim]
                    if dist <= dim_info["radius_m"]:
                        dimension_pois[dim].append(poi)
            break

        except Exception as e:
            if attempt < MAX_RETRIES - 1:
                backoff = (BACKOFF_MULTIPLIER ** attempt) + random.uniform(1, 3)
                time.sleep(backoff)
                continue
            break

    # Compute scores
    scores = {}
    for dim_key, dim_info in DIMENSIONS.items():
        s = compute_dimension_score(dimension_pois[dim_key], dim_info["max_count"], dim_info["radius_m"])
        scores[dim_key] = s

    overall = round(sum((scores[k] or 0) * WEIGHTS[k] for k in DIMENSIONS) / TOTAL_WEIGHT)
    overall = max(0, min(100, overall))
    scores["overall"] = overall
    return scores


def save_progress(done, total, db_scored, api_scored, failed):
    state = {
        "done": done, "total": total, "db_scored": db_scored,
        "api_scored": api_scored, "failed": failed, "timestamp": time.time(),
    }
    with open(PROGRESS_FILE, "w") as f:
        json.dump(state, f)
    pct = done / total * 100 if total > 0 else 0
    elapsed = time.time() - start_time
    eta = elapsed / done * (total - done) if done > 0 else 0
    print(f"[{done}/{total}] {pct:.1f}% | DB:{db_scored} API:{api_scored} FAIL:{failed} | ETA:{eta/60:.1f}min", flush=True)


def main():
    global start_time
    start_time = time.time()

    engine = create_engine(DB_URL)

    # Find all trades needing scores
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT t.id, t.lat, t.lon, t.city, t.district,
                   CASE WHEN EXISTS (SELECT 1 FROM trade_amenities ta WHERE ta.trade_id = t.id) THEN 1 ELSE 0 END as has_poi
            FROM trades t
            WHERE t.lat IS NOT NULL AND t.lon IS NOT NULL
              AND (t.score_overall IS NULL OR t.score_overall = 0)
            ORDER BY t.id
        """))
        trades = result.fetchall()

    total = len(trades)
    db_only_trades = [t for t in trades if t[5] == 1]  # Has POI in DB
    no_poi_trades = [t for t in trades if t[5] == 0]   # No POI → need Overpass

    print(f"需計算評分: {total} 筆")
    print(f"  有 POI (DB 計算): {len(db_only_trades)} 筆")
    print(f"  無 POI (Overpass): {len(no_poi_trades)} 筆\n", flush=True)

    # Load progress
    resume_from = 0
    db_scored = 0
    api_scored = 0
    failed = 0
    try:
        with open(PROGRESS_FILE) as f:
            state = json.load(f)
        resume_from = state.get("done", 0)
        db_scored = state.get("db_scored", 0)
        api_scored = state.get("api_scored", 0)
        failed = state.get("failed", 0)
        print(f"從進度恢復: 已處理 {resume_from} 筆\n", flush=True)
    except FileNotFoundError:
        pass

    # ── Phase 1: DB-only scoring (fast, no API) ──
    print("=== Phase 1: DB 評分 (不需 API) ===", flush=True)
    for i, t in enumerate(db_only_trades[resume_from:] if resume_from < len(db_only_trades) else []):
        tid = t[0]
        try:
            with engine.connect() as conn:
                rows = conn.execute(text("""
                    SELECT category, amenity_name, distance
                    FROM trade_amenities WHERE trade_id = :tid
                """), {"tid": tid}).fetchall()

            if not rows:
                failed += 1
                continue

            dim_pois = {k: [] for k in DIMENSIONS}
            for cat, name, dist in rows:
                dim_key = CATEGORY_TO_DIMENSION.get(cat)
                if dim_key:
                    dim_pois[dim_key].append({"name": name, "distance": dist})

            scores = {}
            for dim_key, dim_info in DIMENSIONS.items():
                s = compute_dimension_score(dim_pois[dim_key], dim_info["max_count"], dim_info["radius_m"])
                scores[dim_key] = s

            overall = round(sum((scores[k] or 0) * WEIGHTS[k] for k in DIMENSIONS) / TOTAL_WEIGHT)
            overall = max(0, min(100, overall))

            with engine.connect() as conn:
                conn.execute(text("""
                    UPDATE trades SET
                        score_overall = :so, score_transit = :st, score_education = :se,
                        score_medical = :sm, score_shopping = :ss,
                        score_leisure = :sl, score_dining = :sd,
                        score_updated_at = NOW()
                    WHERE id = :tid
                """), {
                    "so": overall, "st": scores["transit"], "se": scores["education"],
                    "sm": scores["medical"], "ss": scores["shopping"],
                    "sl": scores["leisure"], "sd": scores["dining"], "tid": tid
                })
                conn.commit()

            db_scored += 1
            done = resume_from + i + 1
            if i % 200 == 0 or i == len(db_only_trades) - 1:
                save_progress(done, total, db_scored, api_scored, failed)

        except Exception as e:
            failed += 1
            if failed <= 3:
                print(f"  ✗ Trade {tid}: {e}", flush=True)

    # ── Phase 2: Overpass API scoring (slower, needs API) ──
    print(f"\n=== Phase 2: Overpass API 評分 ({len(no_poi_trades)} 筆) ===", flush=True)

    # Coordinate cache to avoid duplicate API calls
    coord_cache = {}

    for i, t in enumerate(no_poi_trades):
        tid, lat, lon, city, district = t[0], t[1], t[2], t[3], t[4]
        cache_key = f"{round(lat, 3)}_{round(lon, 3)}"

        try:
            if cache_key in coord_cache:
                scores = coord_cache[cache_key]
            else:
                scores = fetch_overpass_scores(lat, lon)
                coord_cache[cache_key] = scores

            with engine.connect() as conn:
                conn.execute(text("""
                    UPDATE trades SET
                        score_overall = :so, score_transit = :st, score_education = :se,
                        score_medical = :sm, score_shopping = :ss,
                        score_leisure = :sl, score_dining = :sd,
                        score_updated_at = NOW()
                    WHERE id = :tid
                """), {
                    "so": scores["overall"], "st": scores["transit"], "se": scores["education"],
                    "sm": scores["medical"], "ss": scores["shopping"],
                    "sl": scores["leisure"], "sd": scores["dining"], "tid": tid
                })
                conn.commit()

            api_scored += 1
            done = len(db_only_trades) + i + 1
            if (i + 1) % 25 == 0 or i == len(no_poi_trades) - 1:
                save_progress(done, total, db_scored, api_scored, failed)

        except Exception as e:
            failed += 1
            if failed <= 5:
                print(f"  ✗ Trade {tid} ({city}{district}): {e}", flush=True)

    elapsed = time.time() - start_time
    print(f"\n{'='*60}", flush=True)
    print(f"完成! 耗時 {elapsed/60:.1f} 分鐘", flush=True)
    print(f"DB 評分: {db_scored} 筆, Overpass 評分: {api_scored} 筆, 失敗: {failed} 筆", flush=True)

    # Final stats
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT COUNT(*)::int,
                   COUNT(CASE WHEN score_overall IS NOT NULL THEN 1 END)::int
            FROM trades WHERE lat IS NOT NULL AND lon IS NOT NULL
        """))
        row = result.fetchone()
        print(f"\n總計: {row[1]}/{row[0]} 筆交易有評分 ({row[1]/row[0]*100:.1f}%)", flush=True)

        # Per-city breakdown
        result = conn.execute(text("""
            SELECT city, COUNT(*)::int as total,
                   COUNT(CASE WHEN score_overall IS NOT NULL THEN 1 END)::int as scored
            FROM trades WHERE lat IS NOT NULL AND lon IS NOT NULL
            GROUP BY city ORDER BY total DESC
        """))
        print("\n各縣市評分覆蓋率:")
        for r in result.fetchall():
            pct = r[2] / r[1] * 100 if r[1] > 0 else 0
            print(f"  {r[0]}: {r[2]}/{r[1]} ({pct:.0f}%)", flush=True)


if __name__ == "__main__":
    main()
