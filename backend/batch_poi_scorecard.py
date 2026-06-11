"""
批次填充 POI + 生活圈評分 — Nominatim API (慢速版)
策略：
1. 每筆請求間隔 2 秒（避免 429 rate limit）
2. 遇到 429 自動退避重試（最多 3 次）
3. 每個交易查 6 個維度 × 最多 4 個關鍵字 = 最多 24 次 API call
4. 結果直接寫入 trades 表的 scorecard 欄位

預估時間：3336 筆 × 24 calls × 2s ≈ 5.3 小時
優化：只查每個維度的主要關鍵字（減少到 ~12 calls/trade）→ ~2.7 小時
"""
import time
import json
import math
import urllib.request
import urllib.parse
import sys
import logging

sys.path.insert(0, '.')

from sqlalchemy import create_engine, text

DB_URL = "postgresql://hermes@localhost:5432/housing_tracker"

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s')
logger = logging.getLogger(__name__)

# ─── Dimension definitions (optimized for fewer API calls) ──────────────
DIMENSIONS = {
    "transit": {
        "label": "交通",
        "keywords": ["捷運站", "火車站", "bus stop"],
        "radius_m": 1000,
        "max_count": 8,
    },
    "education": {
        "label": "教育",
        "keywords": ["學校", "kindergarten", "university"],
        "radius_m": 1500,
        "max_count": 6,
    },
    "medical": {
        "label": "醫療",
        "keywords": ["醫院", "hospital", "診所", "clinic"],
        "radius_m": 1200,
        "max_count": 5,
    },
    "shopping": {
        "label": "購物",
        "keywords": ["7-11", "全家", "超市", "supermarket"],
        "radius_m": 800,
        "max_count": 8,
    },
    "leisure": {
        "label": "休閒",
        "keywords": ["公園", "park", "圖書館", "library"],
        "radius_m": 1000,
        "max_count": 5,
    },
    "dining": {
        "label": "餐飲",
        "keywords": ["餐廳", "restaurant", "咖啡廳", "cafe"],
        "radius_m": 600,
        "max_count": 10,
    },
}

DEFAULT_WEIGHTS = {
    "transit": 0.20,
    "education": 0.15,
    "medical": 0.15,
    "shopping": 0.20,
    "leisure": 0.15,
    "dining": 0.15,
}

RATE_LIMIT_DELAY = 2.0  # seconds between requests
MAX_RETRIES = 3
BACKOFF_FACTOR = 5  # multiply delay on each retry


def _haversine(lat1, lon1, lat2, lon2):
    R = 6371000
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _meters_to_deg(meters, lat):
    lat_d = meters / 111320
    lon_d = meters / (111320 * math.cos(math.radians(lat)))
    return max(lat_d, lon_d)


def _search_pois(keyword, lat, lon, radius_deg, limit=5):
    """Search Nominatim with retry and backoff."""
    vb = f"{lon - radius_deg:.4f},{lat + radius_deg:.4f},{lon + radius_deg:.4f},{lat - radius_deg:.4f}"
    url = f"https://nominatim.openstreetmap.org/search?format=json&q={urllib.parse.quote(keyword)}&limit={limit}&viewbox={vb}&bounded=1&countrycodes=TW&addressdetails=0"
    
    results = []
    delay = RATE_LIMIT_DELAY
    
    for attempt in range(MAX_RETRIES):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "HousingTracker/1.0"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                for r in data:
                    rlat = float(r.get("lat", lat))
                    rlon = float(r.get("lon", lon))
                    dist = _haversine(lat, lon, rlat, rlon)
                    if dist <= radius_deg * 111320:
                        name = r.get("display_name", "").split(",")[0].strip() or "未知"
                        results.append({"name": name, "distance": round(dist)})
                return results
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < MAX_RETRIES - 1:
                wait = delay * BACKOFF_FACTOR ** attempt
                logger.warning(f"  ⚠️  429 Rate limited, waiting {wait}s...")
                time.sleep(wait)
                continue
            elif e.code == 429:
                logger.warning(f"  ✗ Still 429 after {MAX_RETRIES} retries")
                return []
            else:
                logger.warning(f"  ✗ HTTP {e.code}")
                return []
        except Exception as e:
            if attempt < MAX_RETRIES - 1:
                wait = delay * BACKOFF_FACTOR ** attempt
                logger.warning(f"  ⚠️  Error: {e}, retrying in {wait}s...")
                time.sleep(wait)
                continue
            else:
                logger.warning(f"  ✗ Failed after {MAX_RETRIES} retries: {e}")
                return []
        
        time.sleep(delay)
    
    return results


def _compute_dimension_score(pois, max_count, radius_m):
    """Score a single dimension 0–100 based on POI count & distance."""
    if not pois:
        return {"score": 0, "count": 0, "nearest": None}
    
    pois_sorted = sorted(pois, key=lambda p: p["distance"])
    count = len(pois_sorted)
    
    count_ratio = min(count / max_count, 1.0)
    count_score = 100 * math.log2(1 + count_ratio * 7) / math.log2(8)
    
    dist_scores = [math.exp(-p["distance"] / (radius_m * 0.4)) for p in pois_sorted[:5]]
    avg_dist_score = (sum(dist_scores) / len(dist_scores)) * 100 if dist_scores else 0
    
    combined = round(0.6 * count_score + 0.4 * avg_dist_score)
    combined = max(0, min(100, combined))
    
    return {"score": combined, "count": count, "nearest": pois_sorted[0]["distance"]}


def compute_scorecard_for_location(lat, lon):
    """Compute full scorecard for a location via Nominatim."""
    all_pois = {}
    scores = {}
    
    for dim_key, dim_info in DIMENSIONS.items():
        dim_pois = []
        r_deg = _meters_to_deg(dim_info["radius_m"], lat)
        
        for kw in dim_info["keywords"]:
            pois = _search_pois(kw, lat, lon, r_deg, limit=5)
            dim_pois.extend(pois)
            time.sleep(RATE_LIMIT_DELAY)
        
        # Deduplicate by name
        seen = set()
        unique = []
        for p in dim_pois:
            if p["name"] not in seen:
                seen.add(p["name"])
                unique.append(p)
        
        result = _compute_dimension_score(unique, dim_info["max_count"], dim_info["radius_m"])
        scores[dim_key] = result
        all_pois[dim_key] = unique
    
    # Overall weighted score - only average dimensions that have data
    valid_scores = {k: v for k, v in scores.items() if v["score"] is not None}
    if valid_scores:
        total_weight = sum(DEFAULT_WEIGHTS[k] for k in valid_scores)
        overall = round(sum(scores[k]["score"] * DEFAULT_WEIGHTS[k] for k in valid_scores) / total_weight)
        overall = max(0, min(100, overall))
    else:
        overall = None
    
    return {
        "overall": overall,
        **scores,
    }


def main():
    engine = create_engine(DB_URL)
    
    with engine.connect() as conn:
        # ─── Step 1: Ensure columns exist ──────────────────────────────
        print("=== Step 1: 建立 scorecard 欄位 ===")
        conn.execute(text("""
            DO $$
            BEGIN
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='trades' AND column_name='score_overall') THEN
                    ALTER TABLE trades ADD COLUMN score_overall INTEGER DEFAULT NULL;
                    ALTER TABLE trades ADD COLUMN score_transit INTEGER DEFAULT NULL;
                    ALTER TABLE trades ADD COLUMN score_education INTEGER DEFAULT NULL;
                    ALTER TABLE trades ADD COLUMN score_medical INTEGER DEFAULT NULL;
                    ALTER TABLE trades ADD COLUMN score_shopping INTEGER DEFAULT NULL;
                    ALTER TABLE trades ADD COLUMN score_leisure INTEGER DEFAULT NULL;
                    ALTER TABLE trades ADD COLUMN score_dining INTEGER DEFAULT NULL;
                    ALTER TABLE trades ADD COLUMN score_updated_at TIMESTAMP DEFAULT NULL;
                END IF;
            END $$;
        """))
        conn.commit()
        print("✓ Scorecard 欄位就緒\n")
        
        # ─── Step 2: Get trades without scores ─────────────────────────
        result = conn.execute(text("""
            SELECT id, lat, lon, city, district
            FROM trades
            WHERE lat IS NOT NULL AND lon IS NOT NULL
              AND (score_overall IS NULL OR score_updated_at IS NULL)
            ORDER BY id
        """))
        trades = result.fetchall()
        total = len(trades)
        print(f"=== Step 2: 需查詢 {total} 筆交易 ===")
        print(f"預估時間: ~{total * 12 * RATE_LIMIT_DELAY / 3600:.1f} 小時\n")
        
        # ─── Step 3: Query & score each trade ──────────────────────────
        success = 0
        failed = 0
        
        for i, (tid, lat, lon, city, district) in enumerate(trades):
            label = f"{city}{district}" if city and district else f"#{tid}"
            
            try:
                scores = compute_scorecard_for_location(lat, lon)
                
                # Write to DB
                conn.execute(text("""
                    UPDATE trades SET
                        score_overall = :overall,
                        score_transit = :transit,
                        score_education = :education,
                        score_medical = :medical,
                        score_shopping = :shopping,
                        score_leisure = :leisure,
                        score_dining = :dining,
                        score_updated_at = NOW()
                    WHERE id = :tid
                """), {
                    "overall": scores["overall"],
                    "transit": scores["transit"]["score"],
                    "education": scores["education"]["score"],
                    "medical": scores["medical"]["score"],
                    "shopping": scores["shopping"]["score"],
                    "leisure": scores["leisure"]["score"],
                    "dining": scores["dining"]["score"],
                    "tid": tid,
                })
                
                success += 1
                if (i + 1) % 5 == 0 or i == total - 1:
                    conn.commit()
                    elapsed = (i + 1) * 12 * RATE_LIMIT_DELAY
                    remaining = (total - i - 1) * 12 * RATE_LIMIT_DELAY
                    print(f"[{i+1}/{total}] ✓ {label} → Overall: {scores['overall']} | 成功:{success} 失敗:{failed} | 剩餘~{remaining/60:.0f}分")
            
            except Exception as e:
                failed += 1
                logger.warning(f"[{i+1}/{total}] ✗ {label} → {e}")
                if (i + 1) % 5 == 0:
                    conn.commit()
        
        conn.commit()
        
        # ─── Final stats ──────────────────────────────────────────────
        r = conn.execute(text("SELECT COUNT(*) FROM trades WHERE score_overall IS NOT NULL"))
        scored = r.scalar()
        r = conn.execute(text("SELECT MIN(score_overall), MAX(score_overall), AVG(score_overall) FROM trades WHERE score_overall IS NOT NULL"))
        row = r.fetchone()
        
        print(f"\n{'='*60}")
        print(f"完成! 總計 {scored} 筆交易有生活圈評分")
        print(f"分數範圍: {row[0]} - {row[1]}, 平均: {row[2]:.1f}")
        print(f"本次成功: {success}, 失敗: {failed}")


if __name__ == "__main__":
    main()
