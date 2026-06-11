"""
Neighborhood Scorecard — compute multi-dimension scores for any location.

Dimensions: transit, education, medical, shopping, leisure, dining
Each scored 0–100 based on POI count & proximity via Overpass API.

Overpass API 優勢：一次請求即可取得所有維度的 POI，取代舊版 Nominatim × 6 次查詢。
"""
import math
import time
import random
import logging
import urllib.parse
from typing import Optional, Dict, Any, List
from fastapi import APIRouter, Query

from app.services.cache import get_cache
from sqlalchemy import text

logger = logging.getLogger(__name__)

router = APIRouter()

cache = get_cache("scorecard", ttl=3600)  # Cache 1 hour

DB_URL = "postgresql://hermes@localhost:5432/housing_tracker"

OVERPASS_URL = "https://overpass-api.de/api/interpreter"

# ─── Rate limiting config ──────────────────────────────────────────────
BASE_DELAY = 1.5              # Overpass 建議 ≥1s
MAX_RETRIES = 3               # 單次請求最大重試次數
BACKOFF_MULTIPLIER = 2.0      # 指數退避倍率
JITTER_RANGE = (0.3, 1.0)     # 隨機抖動範圍
GLOBAL_REQUEST_COUNT = 0      # 全域請求計數器
LAST_REQUEST_TIME = 0         # 上次請求時間

# ─── Dimension definitions ────────────────────────────────────────────────
DIMENSIONS = {
    "transit": {
        "label": "交通",
        "icon": "🚇",
        "color": "#6366f1",
        "radius_m": 1000,
        "max_count": 8,
        # Overpass tags for transit
        "tags": [
            '"railway"="station"',
            '"public_transport"="stop_position"',
            '"highway"="bus_stop"',
        ],
    },
    "education": {
        "label": "教育",
        "icon": "🏫",
        "color": "#3b82f6",
        "radius_m": 1500,
        "max_count": 6,
        "tags": [
            '"amenity"~"school|kindergarten|university|college"',
        ],
    },
    "medical": {
        "label": "醫療",
        "icon": "🏥",
        "color": "#ef4444",
        "radius_m": 1200,
        "max_count": 5,
        "tags": [
            '"amenity"~"hospital|clinic|doctor|pharmacy"',
        ],
    },
    "shopping": {
        "label": "購物",
        "icon": "🛒",
        "color": "#f59e0b",
        "radius_m": 800,
        "max_count": 8,
        "tags": [
            '"shop"~"convenience|supermarket|mall|department_store"',
        ],
    },
    "leisure": {
        "label": "休閒",
        "icon": "🌳",
        "color": "#22c55e",
        "radius_m": 1000,
        "max_count": 5,
        "tags": [
            '"leisure"="park"',
            '"amenity"="library"',
            '"tourism"="museum"',
        ],
    },
    "dining": {
        "label": "餐飲",
        "icon": "🍽️",
        "color": "#ec4899",
        "radius_m": 600,
        "max_count": 10,
        "tags": [
            '"amenity"~"restaurant|cafe|fast_food|bar|food_court"',
        ],
    },
}

DEFAULT_WEIGHTS = {k: 1.0 for k in DIMENSIONS}


# ─── Helpers ──────────────────────────────────────────────────────────────
def _haversine(lat1, lon1, lat2, lon2):
    R = 6371000
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _enforce_rate_limit():
    """確保兩次請求之間的最小間隔，並加入隨機抖動。"""
    global LAST_REQUEST_TIME, GLOBAL_REQUEST_COUNT
    now = time.time()
    elapsed = now - LAST_REQUEST_TIME
    jitter = random.uniform(*JITTER_RANGE)
    sleep_time = max(0, BASE_DELAY + jitter - elapsed)
    if sleep_time > 0:
        time.sleep(sleep_time)
    LAST_REQUEST_TIME = time.time()
    GLOBAL_REQUEST_COUNT += 1


def _build_overpass_query(lat: float, lon: float, radius: int) -> str:
    """Build a single Overpass query that fetches ALL dimension POIs at once.
    
    Uses union syntax with per-dimension radius for accuracy.
    Only queries node type (ways/relations add timeout without meaningful data).
    """
    # Build individual queries per dimension with their own radius
    parts = []
    for dim_info in DIMENSIONS.values():
        r = dim_info["radius_m"]
        for tag_expr in dim_info["tags"]:
            # Wrap tag expression in square brackets for Overpass node() syntax
            # e.g., node(around:1000,lat,lon)["railway"="station"]
            parts.append(f'node(around:{r},{lat},{lon})[{tag_expr}]')
    
    union = "\n  ;".join(parts)
    
    query = f"""[out:json][timeout:30];
(
  {union};
);
out;"""
    return query


def _classify_poi(element: Dict[str, Any]) -> List[str]:
    """Classify an Overpass element into dimension categories."""
    tags = element.get("tags", {})
    dims = []
    
    amenity = tags.get("amenity", "")
    shop = tags.get("shop", "")
    railway = tags.get("railway", "")
    highway = tags.get("highway", "")
    leisure = tags.get("leisure", "")
    tourism = tags.get("tourism", "")
    public_transport = tags.get("public_transport", "")
    
    # Transit
    if railway == "station" or public_transport == "stop_position" or highway == "bus_stop":
        dims.append("transit")
    
    # Education
    if amenity in ("school", "kindergarten", "university", "college"):
        dims.append("education")
    
    # Medical
    if amenity in ("hospital", "clinic", "doctor", "pharmacy"):
        dims.append("medical")
    
    # Shopping — exclude bank, atm, post_office (not daily shopping)
    if shop in ("convenience", "supermarket", "mall", "department_store",
                "clothes", "shoes", "books", "electronics", "bakery",
                "variety_store", "grocery", "general", "beauty", "hairdresser"):
        dims.append("shopping")
    
    # Leisure — only park, playground, sports; exclude religion, hotel, attraction
    if leisure in ("park", "playground", "sports_centre", "swimming_pool",
                   "garden", "stadium", "theme_park", "zoo", "aquarium", "dog_park"):
        dims.append("leisure")
    elif amenity == "library":
        dims.append("leisure")
    elif tourism == "museum":
        dims.append("leisure")
    
    # Dining
    if amenity in ("restaurant", "cafe", "fast_food", "bar", "food_court"):
        dims.append("dining")
    
    return dims


def _filter_transit_junk(name: str) -> bool:
    """Return True if this transit POI name looks like junk (exit, mailbox, etc.)."""
    junk_patterns = ['出口', '郵箱', 'i郵箱', '轉接站']
    return not any(p in name for p in junk_patterns)


# Education name patterns to search across non-transit categories
EDU_NAME_PATTERNS = [
    '%國小%', '%國民小學%', '%小學%',
    '%國中%', '%國民中學%', '%初中%',
    '%高中%', '%高級中學%', '%高職%', '%職業學校%',
    '%大學%', '%研究所%',
    '%幼兒園%', '%托兒所%',
]
# Names that contain school-like words but are NOT schools (e.g. "衣美學院自助洗衣")
EDU_EXCLUDE_PATTERNS = [
    '%自助洗衣%', '%美容院%', '%髮廊%', '%健身%', '%咖啡%', '%餐廳%',
]

def _build_edu_query() -> str:
    """Build SQL WHERE clause that matches education POIs - only from education category or non-transit/name-matched entries."""
    patterns = " OR ".join([f"p.name LIKE :edu_{i}" for i in range(len(EDU_NAME_PATTERNS))])
    exclude_patterns = " AND ".join([f"p.name NOT LIKE :edu_excl_{i}" for i in range(len(EDU_EXCLUDE_PATTERNS))])
    # CRITICAL: Must wrap ALL name patterns in parens BEFORE AND to ensure correct precedence.
    return f"((p.category = 'education' OR (({patterns}) AND p.category NOT IN ('transit', 'education'))) AND {exclude_patterns})"

def _fetch_all_pois_from_db(lat: float, lon: float, radius: int = 1000) -> Dict[str, List[Dict[str, Any]]]:
    """Fetch ALL dimension POIs from local poi_master table (fast path using PostGIS spatial index)."""
    from app.main import engine
    
    # Per-dimension results
    dimension_pois: Dict[str, List[Dict[str, Any]]] = {k: [] for k in DIMENSIONS}
    
    try:
        with engine.connect() as conn:
            for dim_key, dim_info in DIMENSIONS.items():
                # Build query with education name pattern expansion
                if dim_key == "education":
                    where_clause = _build_edu_query()
                    params = {}
                    for i, pat in enumerate(EDU_NAME_PATTERNS):
                        params[f"edu_{i}"] = pat
                    for i, pat in enumerate(EDU_EXCLUDE_PATTERNS):
                        params[f"edu_excl_{i}"] = pat
                else:
                    # Exclude junk sub_types per category
                    exclude_map = {
                        "shopping": ["bank", "atm", "post_office"],
                        "leisure": ["place_of_worship", "information", "hotel", "hostel",
                                    "guest_house", "motel", "viewpoint", "attraction",
                                    "artwork", "gallery"],
                    }
                    if dim_key in exclude_map:
                        excludes = exclude_map[dim_key]
                        placeholders = ", ".join([":excl_" + str(i) for i in range(len(excludes))])
                        where_clause = f"p.category = :cat AND p.sub_type NOT IN ({placeholders})"
                        params = {"cat": dim_key}
                        for i, excl in enumerate(excludes):
                            params[f"excl_{i}"] = excl
                    else:
                        where_clause = "p.category = :cat"
                        params = {"cat": dim_key}
                
                # Use PostGIS ST_DWithin on geom column (uses GiST index) instead of Haversine full-scan
                result = conn.execute(text(f"""
                    SELECT 
                        p.name,
                        p.lat,
                        p.lon,
                        p.sub_type,
                        ST_Distance(
                            p.geom::geography,
                            ST_SetSRID(ST_MakePoint(:center_lon, :center_lat), 4326)::geography
                        ) AS distance_m
                    FROM poi_master p
                    WHERE {where_clause}
                      AND ST_DWithin(
                          p.geom::geography,
                          ST_SetSRID(ST_MakePoint(:center_lon2, :center_lat2), 4326)::geography,
                          :radius
                      )
                    ORDER BY distance_m
                """), {**params, "center_lon": lon, "center_lat": lat, "center_lon2": lon, "center_lat2": lat, "radius": radius}).fetchall()
                
                # Dedup by name + proximity (within 50m of existing entry)
                seen: List[tuple] = []
                for row in result:
                    dist = row[4]
                    if dist is not None and dist <= radius:
                        name = row[0] or "未知"
                        rlat = row[1]
                        rlon = row[2]
                        sub_type = row[3] or ""
                        
                        # Filter out junk transit entries
                        if dim_key == "transit" and not _filter_transit_junk(name):
                            continue
                        
                        # Skip duplicates: same name within threshold (100m for transit, 50m for others)
                        is_dup = False
                        dup_threshold = 100 if dim_key == "transit" else 50
                        for s_name, s_lat, s_lon in seen:
                            if s_name == name:
                                d = ((rlat - s_lat)**2 + (rlon - s_lon)**2) ** 0.5 * 111000
                                if d < dup_threshold:
                                    is_dup = True
                                    break
                        if is_dup:
                            continue
                        
                        seen.append((name, rlat, rlon))
                        poi_entry = {
                            "name": name,
                            "distance": round(dist),
                            "lat": rlat,
                            "lon": rlon,
                        }
                        # Add type info for transit and education
                        if dim_key == "transit":
                            poi_entry["type"] = sub_type
                        elif dim_key == "education":
                            poi_entry["type"] = sub_type
                        dimension_pois[dim_key].append(poi_entry)
    except Exception as e:
        logger.warning(f"DB POI lookup failed: {e}")
    
    return dimension_pois


def _fetch_all_pois_overpass(lat: float, lon: float) -> Dict[str, List[Dict[str, Any]]]:
    """Fallback: fetch ALL dimension POIs via Overpass API (slow, rate-limited).
    Only used when poi_cache is empty or unavailable."""
    import urllib.request
    import json
    
    max_radius = max(dim_info["radius_m"] for dim_info in DIMENSIONS.values())
    query = _build_overpass_query(lat, lon, max_radius)
    
    dimension_pois: Dict[str, List[Dict[str, Any]]] = {k: [] for k in DIMENSIONS}
    
    overpass_url = f"{OVERPASS_URL}?data={urllib.parse.quote(query)}"
    
    for attempt in range(MAX_RETRIES):
        _enforce_rate_limit()
        
        try:
            req = urllib.request.Request(
                overpass_url,
                headers={
                    "User-Agent": "HousingTracker/1.0",
                    "Accept": "application/json",
                },
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            
            elements = data.get("elements", [])
            for elem in elements:
                elem_lat = elem.get("lat")
                elem_lon = elem.get("lon")
                
                if elem_lat is None or elem_lon is None:
                    continue
                
                dist = _haversine(lat, lon, elem_lat, elem_lon)
                name = elem.get("tags", {}).get("name", elem.get("tags", {}).get("amenity", "未知"))
                
                poi = {
                    "name": name,
                    "distance": round(dist),
                    "lat": elem_lat,
                    "lon": elem_lon,
                }
                
                matched_dims = _classify_poi(elem)
                for dim in matched_dims:
                    dim_info = DIMENSIONS[dim]
                    if dist <= dim_info["radius_m"]:
                        dimension_pois[dim].append(poi)
            
            return dimension_pois
        
        except Exception as e:
            logger.warning(f"Overpass request failed (attempt {attempt+1}/{MAX_RETRIES}): {e}")
            if attempt < MAX_RETRIES - 1:
                backoff = (BACKOFF_MULTIPLIER ** attempt) + random.uniform(1, 3)
                time.sleep(backoff)
                continue
            return dimension_pois
    
    logger.error(f"Overpass exhausted all {MAX_RETRIES} retries at ({lat}, {lon})")
    return dimension_pois


def _geocode(address: str) -> Optional[tuple]:
    """Geocode address → (lat, lon)."""
    from app.services.geocode import geocode_address
    logger.info(f"_geocode called with: '{address}'")
    try:
        result = geocode_address(address)
        logger.info(f"_geocode('{address}') -> {result}")
        return result
    except Exception as e:
        logger.error(f"_geocode failed for '{address}': {e}", exc_info=True)
        return None


def _fetch_db_scorecard(lat: float, lon: float) -> Optional[Dict[str, Any]]:
    """Try to fetch pre-computed scorecard from trades table for nearby trade."""
    try:
        from app.main import engine
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT id, score_overall, score_transit, score_education,
                       score_medical, score_shopping, score_leisure, score_dining,
                       score_updated_at, lat, lon, address
                FROM trades
                WHERE score_overall IS NOT NULL
                  AND lat IS NOT NULL AND lon IS NOT NULL
                ORDER BY (
                    6371000 * acos(
                        cos(radians(:lat)) * cos(radians(lat)) *
                        cos(radians(lon) - radians(:lon)) +
                        sin(radians(:lat)) * sin(radians(lat))
                    )
                ) ASC
                LIMIT 1
            """), {"lat": lat, "lon": lon})
            row = result.fetchone()
            # row indices: 0=id, 1=overall, 2=transit, 3=edu, 4=med, 5=shop, 6=leisure, 7=dining, 8=updated_at, 9=lat, 10=lon, 11=address
            if row and row[9] is not None and row[10] is not None:
                d = _haversine(lat, lon, row[9], row[10])
                if d <= 200:
                    def safe_int(val):
                        return int(val) if val is not None else 0
                    return {
                        "source": "database",
                        "nearest_trade_id": row[0],
                        "nearest_trade_address": row[11] if len(row) > 11 else None,
                        "distance_to_trade": round(d),
                        "location": {"lat": lat, "lon": lon},
                        "radius": 1000,
                        "weights": dict(DEFAULT_WEIGHTS),
                        "overall_score": safe_int(row[1]),
                        "dimensions": {
                            "transit": {"score": safe_int(row[2]), "label": "交通", "icon": "🚇", "color": "#6366f1", "weight": 1.0, "count": 0, "nearest": None, "pois": []},
                            "education": {"score": safe_int(row[3]), "label": "教育", "icon": "🏫", "color": "#3b82f6", "weight": 1.0, "count": 0, "nearest": None, "pois": []},
                            "medical": {"score": safe_int(row[4]), "label": "醫療", "icon": "🏥", "color": "#ef4444", "weight": 1.0, "count": 0, "nearest": None, "pois": []},
                            "shopping": {"score": safe_int(row[5]), "label": "購物", "icon": "🛒", "color": "#f59e0b", "weight": 1.0, "count": 0, "nearest": None, "pois": []},
                            "leisure": {"score": safe_int(row[6]), "label": "休閒", "icon": "🌳", "color": "#22c55e", "weight": 1.0, "count": 0, "nearest": None, "pois": []},
                            "dining": {"score": safe_int(row[7]), "label": "餐飲", "icon": "🍽️", "color": "#ec4899", "weight": 1.0, "count": 0, "nearest": None, "pois": []},
                        },
                        "suggestion": _generate_suggestion_from_scores({
                            "transit": safe_int(row[2]), "education": safe_int(row[3]), "medical": safe_int(row[4]),
                            "shopping": safe_int(row[5]), "leisure": safe_int(row[6]), "dining": safe_int(row[7])
                        }),
                        "updated_at": str(row[8]) if row[8] else None,
                    }
    except Exception as e:
        logger.warning(f"DB scorecard lookup failed: {e}")
    return None


def _generate_suggestion_from_scores(scores: Dict[str, int]) -> str:
    """Generate suggestion from raw scores (no dimension objects)."""
    weak = [k for k, v in scores.items() if v < 40]
    strong = [k for k, v in scores.items() if v >= 70]
    
    dim_labels = {
        "transit": "🚇交通", "education": "🏫教育", "medical": "🏥醫療",
        "shopping": "🛒購物", "leisure": "🌳休閒", "dining": "🍽️餐飲"
    }
    
    parts = []
    if weak:
        labels = ", ".join(dim_labels.get(k, k) for k in weak)
        parts.append(f"此區域在「{labels}」方面較弱，建議考量生活便利性。")
    if strong:
        labels = ", ".join(dim_labels.get(k, k) for k in strong)
        parts.append(f"「{labels}」是此區域的優勢！")
    if not weak and not strong:
        parts.append("此區域各面向發展均衡，屬於中等生活圈。")
    return " ".join(parts)


# ─── Scoring algorithm ───────────────────────────────────────────────────
def _compute_dimension_score(pois: List[Dict], max_count: int, radius_m: int) -> Dict[str, Any]:
    """Score a single dimension 0–100 based on POI count & distance."""
    if not pois:
        return {"score": 0, "count": 0, "nearest": None, "pois": []}

    pois_sorted = sorted(pois, key=lambda p: p["distance"])
    count = len(pois_sorted)

    # Count score: logarithmic scaling
    count_ratio = min(count / max_count, 1.0)
    count_score = 100 * math.log2(1 + count_ratio * 7) / math.log2(8)

    # Distance score: exponential decay weighting
    dist_scores = [math.exp(-p["distance"] / (radius_m * 0.4)) for p in pois_sorted[:5]]
    avg_dist_score = (sum(dist_scores) / len(dist_scores)) * 100 if dist_scores else 0

    # Combined: 60% count, 40% proximity
    combined = round(0.6 * count_score + 0.4 * avg_dist_score)
    combined = max(0, min(100, combined))

    return {
        "score": combined,
        "count": count,
        "nearest": pois_sorted[0]["distance"] if pois_sorted else None,
        "pois": pois_sorted[:5],
    }


def _fetch_all_pois_nominatim(lat: float, lon: float) -> Dict[str, List[Dict[str, Any]]]:
    """Fallback: fetch POIs per-dimension via Nominatim (slower but reliable)."""
    from app.services.geocode import NOMINATIM_BASE, _enforce_rate_limit as nom_rate_limit, MAX_RETRIES as NOM_MAX_RETRIES, BACKOFF_MULTIPLIER as NOM_BACKOFF
    from app.utils import meters_to_degrees
    
    dimension_pois: Dict[str, List[Dict[str, Any]]] = {k: [] for k in DIMENSIONS}
    
    for dim_key, dim_info in DIMENSIONS.items():
        r_deg = meters_to_degrees(dim_info["radius_m"], lat)
        vb = f"{lon - r_deg:.4f},{lat + r_deg:.4f},{lon + r_deg:.4f},{lat - r_deg:.4f}"
        
        # Map Overpass-style tags to Nominatim search keywords
        keyword_map = {
            "transit": "捷運站 MRT 火車站 bus stop",
            "education": "學校 kindergarten university 國小 國中",
            "medical": "醫院 hospital 診所 clinic",
            "shopping": "7-11 全家 超市 supermarket mart",
            "leisure": "公園 park 圖書館 library",
            "dining": "餐廳 restaurant 咖啡廳 cafe",
        }
        keyword = keyword_map.get(dim_key, "")
        if not keyword:
            continue
        
        url = (
            f"{NOMINATIM_BASE}/search?format=json&q={urllib.parse.quote(keyword)}"
            f"&limit=10&viewbox={vb}&bounded=1&countrycodes=TW&addressdetails=0"
        )
        
        for attempt in range(NOM_MAX_RETRIES):
            try:
                nom_rate_limit()
                req = urllib.request.Request(url, headers={"User-Agent": "HousingTracker/1.0"})
                with urllib.request.urlopen(req, timeout=15) as resp:
                    results = json.loads(resp.read().decode("utf-8"))
                
                for r in results:
                    rlat = float(r.get("lat", lat))
                    rlon = float(r.get("lon", lon))
                    dist = _haversine(lat, lon, rlat, rlon)
                    if dist <= dim_info["radius_m"]:
                        name = r.get("display_name", "").split(",")[0].strip() or "未知"
                        dimension_pois[dim_key].append({
                            "name": name, "distance": round(dist), "lat": rlat, "lon": rlon
                        })
                break
            except Exception as e:
                logger.warning(f"Nominatim fallback failed for '{dim_key}' (attempt {attempt+1}): {e}")
                if attempt < NOM_MAX_RETRIES - 1:
                    time.sleep(NOM_BACKOFF ** attempt + random.uniform(1, 3))
    
    return dimension_pois


def compute_scorecard(lat: float, lon: float, radius: int, weights: Dict[str, float]) -> Dict[str, Any]:
    """Compute full scorecard — tries Overpass first, falls back to Nominatim."""
    import urllib.parse
    
    cache_key = f"sc_{round(lat, 4)}_{round(lon, 4)}_{radius}_{','.join(f'{k}:{v}' for k, v in sorted(weights.items()))}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    # Try local poi_cache first (fast, no rate limit)
    all_pois = _fetch_all_pois_from_db(lat, lon)
    
    # Check if DB returned any data at all
    total_pois = sum(len(v) for v in all_pois.values())
    if total_pois == 0:
        logger.info(f"poi_cache returned 0 POIs at ({lat}, {lon}) — falling back to Overpass")
        all_pois = _fetch_all_pois_overpass(lat, lon)
    
    dimension_results = {}
    total_weight = sum(weights.values()) or 1.0
    overall_score = 0

    for dim_key, dim_info in DIMENSIONS.items():
        pois = all_pois.get(dim_key, [])
        result = _compute_dimension_score(pois, dim_info["max_count"], dim_info["radius_m"])
        w = weights.get(dim_key, 1.0)
        overall_score += result["score"] * w
        dimension_results[dim_key] = {
            "label": dim_info["label"],
            "icon": dim_info["icon"],
            "color": dim_info["color"],
            "weight": w,
            **result,
        }

    overall_score = round(overall_score / total_weight)
    overall_score = max(0, min(100, overall_score))

    data = {
        "location": {"lat": lat, "lon": lon},
        "radius": radius,
        "weights": weights,
        "overall_score": overall_score,
        "dimensions": dimension_results,
        "suggestion": _generate_suggestion(dimension_results),
    }

    cache.set(cache_key, data)
    return data


def _generate_suggestion(dims: Dict) -> str:
    """Generate human-readable suggestion text."""
    weak = [(k, v) for k, v in dims.items() if v["score"] < 40]
    strong = [(k, v) for k, v in dims.items() if v["score"] >= 70]

    parts = []
    if weak:
        labels = ", ".join(f"{v['icon']}{v['label']}" for _, v in weak)
        parts.append(f"此區域在「{labels}」方面較弱，建議考量生活便利性。")
    if strong:
        labels = ", ".join(f"{v['icon']}{v['label']}" for _, v in strong)
        parts.append(f"「{labels}」是此區域的優勢！")
    if not weak and not strong:
        parts.append("此區域各面向發展均衡，屬於中等生活圈。")
    return " ".join(parts)


def compute_scorecard_for_location(lat: float, lon: float) -> Dict[str, Any]:
    """Compute simplified scorecard for batch processing. Returns dict with overall + dimension scores."""
    weights = {
        "transit": 0.25, "education": 0.15, "medical": 0.15,
        "shopping": 0.15, "leisure": 0.15, "dining": 0.15,
    }
    data = compute_scorecard(lat, lon, radius=1000, weights=weights)
    return {
        "overall": data["overall_score"],
        "transit": data["dimensions"]["transit"]["score"],
        "education": data["dimensions"]["education"]["score"],
        "medical": data["dimensions"]["medical"]["score"],
        "shopping": data["dimensions"]["shopping"]["score"],
        "leisure": data["dimensions"]["leisure"]["score"],
        "dining": data["dimensions"]["dining"]["score"],
    }


# ─── API Endpoint ─────────────────────────────────────────────────────────
@router.get("/scorecard")
def get_scorecard(
    lat: Optional[float] = Query(None, description="Latitude"),
    lon: Optional[float] = Query(None, description="Longitude"),
    address: Optional[str] = Query(None, description="Address (auto-geocoded)"),
    radius: int = Query(1000, ge=200, le=5000, description="Search radius in meters"),
    w_transit: float = Query(1.0, ge=0, le=5, description="Weight: Transit"),
    w_education: float = Query(1.0, ge=0, le=5, description="Weight: Education"),
    w_medical: float = Query(1.0, ge=0, le=5, description="Weight: Medical"),
    w_shopping: float = Query(1.0, ge=0, le=5, description="Weight: Shopping"),
    w_leisure: float = Query(1.0, ge=0, le=5, description="Weight: Leisure"),
    w_dining: float = Query(1.0, ge=0, le=5, description="Weight: Dining"),
):
    """Compute neighborhood scorecard for a location."""
    if lat is None or lon is None:
        if not address:
            return {"error": "請提供 lat/lon 或 address"}
        coords = _geocode(address)
        if not coords:
            return {"error": "無法解析地址，請確認地址格式"}
        lat, lon = coords

    weights = {
        "transit": w_transit,
        "education": w_education,
        "medical": w_medical,
        "shopping": w_shopping,
        "leisure": w_leisure,
        "dining": w_dining,
    }

    # ── Step 1: Try DB pre-computed scorecard first (fast path) ──
    db_result = _fetch_db_scorecard(lat, lon)
    if db_result:
        if any(v != 1.0 for v in weights.values()):
            total_w = sum(weights.values()) or 1.0
            weighted_total = sum(
                db_result["dimensions"][k]["score"] * weights[k]
                for k in DIMENSIONS
            )
            db_result["overall_score"] = round(weighted_total / total_w)
            db_result["weights"] = weights
        db_result["radius"] = radius
        
        # ── Populate POI data (DB fast path doesn't include POIs) ──
        all_pois = _fetch_all_pois_from_db(lat, lon, radius)
        if not all_pois or all(len(v) == 0 for v in all_pois.values()):
            # Fallback to Overpass if local cache is empty
            try:
                all_pois = _fetch_all_pois_overpass(lat, lon)
            except Exception as e:
                logger.warning(f"Overpass fallback failed: {e}")
        
        if all_pois:
            for dim_key in DIMENSIONS:
                pois = all_pois.get(dim_key, [])
                dim_info = DIMENSIONS[dim_key]
                # Use user-provided radius as the search boundary
                max_radius = radius
                filtered = [p for p in pois if p["distance"] <= max_radius]
                
                nearest = min(filtered, key=lambda p: p["distance"]) if filtered else None
                
                # Recompute score based on actual POIs (DB pre-computed scores may not match)
                dimension_score = _compute_dimension_score(
                    filtered, dim_info["max_count"], max_radius
                )
                
                db_result["dimensions"][dim_key].update({
                    "score": dimension_score["score"],
                    "count": dimension_score["count"],
                    "nearest": nearest,
                    "pois": filtered[:50],  # Return up to 50 POIs to match frontend display
                })
            
            # Recompute overall score from updated dimension scores
            if any(v != 1.0 for v in weights.values()):
                total_w = sum(weights.values()) or 1.0
                weighted_total = sum(
                    db_result["dimensions"][k]["score"] * weights[k]
                    for k in DIMENSIONS
                )
                db_result["overall_score"] = round(weighted_total / total_w)
            else:
                db_result["overall_score"] = round(
                    sum(db_result["dimensions"][k]["score"] for k in DIMENSIONS) / len(DIMENSIONS)
                )
        
        return db_result

    # ── Step 2: Fallback to dynamic computation via Overpass ──
    try:
        result = compute_scorecard(lat, lon, radius, weights)
        result["source"] = "dynamic"
        return result
    except Exception as e:
        logger.error(f"Scorecard computation failed: {e}")
        return {"error": f"評分計算失敗: {str(e)}"}
