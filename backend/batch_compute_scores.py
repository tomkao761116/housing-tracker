"""
批次計算所有交易的評分 — 從 trade_amenities DB 資料計算 (不需 API)
"""
import math
import time
from sqlalchemy import create_engine, text

DB_URL = "postgresql://hermes@localhost:5432/housing_tracker"

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
# Source: Real estate industry surveys (樂屋網, 房市氣象台, 21世紀不動產)
# Priority order: Transit > Education > Medical > Shopping > Leisure > Dining
WEIGHTS = {
    "transit": 0.28,    # #1 - Commute & property value driver
    "education": 0.20,   # #2 - School district premium
    "medical": 0.18,     # #3 - Health accessibility
    "shopping": 0.15,    # #4 - Daily convenience
    "leisure": 0.12,     # #5 - Parks & recreation
    "dining": 0.07,      # #6 - Nice-to-have
}
TOTAL_WEIGHT = sum(WEIGHTS.values())


def compute_dimension_score(pois, max_count, radius_m):
    if not pois:
        return None  # No POI data → NULL in DB, displayed as "-"
    count = len(pois)
    count_ratio = min(count / max_count, 1.0)
    count_score = 100 * math.log2(1 + count_ratio * 7) / math.log2(8)
    dist_scores = [math.exp(-p["distance"] / (radius_m * 0.4)) for p in pois[:5]]
    avg_dist_score = (sum(dist_scores) / len(dist_scores)) * 100 if dist_scores else 0
    combined = round(0.6 * count_score + 0.4 * avg_dist_score)
    return max(0, min(100, combined))


engine = create_engine(DB_URL)

# Find all trades with POIs but no score
with engine.connect() as conn:
    result = conn.execute(text("""
        SELECT t.id
        FROM trades t
        WHERE t.lat IS NOT NULL AND t.lon IS NOT NULL
          AND (t.score_overall IS NULL OR t.score_overall = 0)
          AND EXISTS (SELECT 1 FROM trade_amenities ta WHERE ta.trade_id = t.id)
    """))
    trade_ids = [row[0] for row in result.fetchall()]

print(f"需計算評分: {len(trade_ids)} 筆")

scored = 0
failed = 0

for i, tid in enumerate(trade_ids, 1):
    try:
        with engine.connect() as conn:
            # Fetch POIs
            rows = conn.execute(text("""
                SELECT category, amenity_name, distance
                FROM trade_amenities WHERE trade_id = :tid
            """), {"tid": tid}).fetchall()

        if not rows:
            failed += 1
            continue

        # Group by dimension
        dim_pois = {k: [] for k in DIMENSIONS}
        for cat, name, dist in rows:
            dim_key = CATEGORY_TO_DIMENSION.get(cat)
            if dim_key:
                dim_pois[dim_key].append({"name": name, "distance": dist})

        # Compute scores - NULL if no POI data, numeric score otherwise
        scores = {}
        for dim_key, dim_info in DIMENSIONS.items():
            s = compute_dimension_score(dim_pois[dim_key], dim_info["max_count"], dim_info["radius_m"])
            scores[dim_key] = s
        
        # Overall: weighted average of ALL dimensions (NULL treated as 0)
        total_weight = sum(WEIGHTS.values())
        overall = round(sum((scores[k] or 0) * WEIGHTS[k] for k in DIMENSIONS) / total_weight)
        overall = max(0, min(100, overall))

        # Write back to DB - NULL for dimensions without POI data
        with engine.connect() as conn:
            conn.execute(text("""
                UPDATE trades SET
                    score_overall = :so,
                    score_transit = :st,
                    score_education = :se,
                    score_medical = :sm,
                    score_shopping = :ss,
                    score_leisure = :sl,
                    score_dining = :sd,
                    score_updated_at = NOW()
                WHERE id = :tid
            """), {
                "so": overall, "st": scores["transit"], "se": scores["education"],
                "sm": scores["medical"], "ss": scores["shopping"],
                "sl": scores["leisure"], "sd": scores["dining"], "tid": tid
            })
            conn.commit()

        scored += 1
        if i % 100 == 0 or i == len(trade_ids):
            print(f"[{i}/{len(trade_ids)}] {i/len(trade_ids)*100:.1f}% | Scored:{scored} Failed:{failed}")

    except Exception as e:
        failed += 1
        if failed <= 3:
            print(f"  ✗ Trade {tid}: {e}")

print(f"\n完成! 成功 {scored} 筆, 失敗 {failed} 筆")
