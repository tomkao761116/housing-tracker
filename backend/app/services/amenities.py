"""
Amenities service — POI search, geocoding, and neighborhood scoring.
"""
import math
import time
import random
import logging
from typing import Optional, Dict, Any, List

import urllib.request
import urllib.parse
import json

from app.services.cache import get_cache
from app.services.geocode import (
    geocode_address, NOMINATIM_BASE, _enforce_rate_limit,
    MAX_RETRIES, BACKOFF_MULTIPLIER, JITTER_RANGE, GLOBAL_REQUEST_COUNT,
)
from app.utils import haversine_m, meters_to_degrees

logger = logging.getLogger(__name__)

cache = get_cache("amenities", ttl=3600)

# ─── Dimension definitions ──────────────────────────────
DIMENSIONS = {
    "transit": {
        "label": "交通", "icon": "🚇", "color": "#6366f1",
        "query": "捷運站 MRT 火車站 bus stop 公車站",
        "radius_m": 1000, "max_count": 8,
    },
    "education": {
        "label": "教育", "icon": "🏫", "color": "#3b82f6",
        "query": "學校 kindergarten university 國小 國中 高中 大學",
        "radius_m": 1500, "max_count": 6,
    },
    "medical": {
        "label": "醫療", "icon": "🏥", "color": "#ef4444",
        "query": "醫院 hospital 診所 clinic",
        "radius_m": 1200, "max_count": 5,
    },
    "shopping": {
        "label": "購物", "icon": "🛒", "color": "#f59e0b",
        "query": "7-11 全家 萊爾富 OK超商 全聯 超市 supermarket mart",
        "radius_m": 800, "max_count": 8,
    },
    "leisure": {
        "label": "休閒", "icon": "🌳", "color": "#22c55e",
        "query": "公園 park 圖書館 library 博物館",
        "radius_m": 1000, "max_count": 5,
    },
    "dining": {
        "label": "餐飲", "icon": "🍽️", "color": "#ec4899",
        "query": "餐廳 restaurant 咖啡廳 cafe 美食",
        "radius_m": 600, "max_count": 10,
    },
}

DEFAULT_WEIGHTS = {k: 1.0 for k in DIMENSIONS}


# ─── Helpers ─────────────────────────────────────────────

def _search_pois(keyword: str, lat: float, lon: float, radius_deg: float, limit: int = 5) -> List[Dict[str, Any]]:
    """Search Nominatim within a viewbox."""
    vb = f"{lon - radius_deg:.4f},{lat + radius_deg:.4f},{lon + radius_deg:.4f},{lat - radius_deg:.4f}"
    url = (
        f"{NOMINATIM_BASE}/search?format=json&q={urllib.parse.quote(keyword)}"
        f"&limit={limit}&viewbox={vb}&bounded=1&countrycodes=TW&addressdetails=0"
    )

    for attempt in range(MAX_RETRIES):
        _enforce_rate_limit()
        req = urllib.request.Request(url, headers={"User-Agent": "HousingTracker/1.0"})
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                results = json.loads(resp.read().decode("utf-8"))
                items = []
                for r in results:
                    rlat = float(r.get("lat", lat))
                    rlon = float(r.get("lon", lon))
                    dist = haversine_m(lat, lon, rlat, rlon)
                    if dist <= radius_deg * 111320:
                        name = r.get("display_name", "").split(",")[0].strip() or "未知"
                        items.append({"name": name, "distance": round(dist), "lat": rlat, "lon": rlon})
                return items
        except urllib.error.HTTPError as e:
            if e.code == 429:
                backoff = BACKOFF_MULTIPLIER ** attempt + random.uniform(1, 3)
                logger.warning(f"Nominatim 429 (attempt {attempt+1}/{MAX_RETRIES}) for '{keyword}' — waiting {backoff:.1f}s")
                time.sleep(backoff)
                continue
            logger.warning(f"Nominatim HTTP {e.code} for '{keyword}': {e.reason}")
            return []
        except Exception as e:
            logger.warning(f"Nominatim request failed ({attempt+1}/{MAX_RETRIES}) for '{keyword}': {e}")
            if attempt < MAX_RETRIES - 1:
                time.sleep(BACKOFF_MULTIPLIER ** attempt + random.uniform(1, 3))
            return []

    logger.error(f"Nominatim exhausted all {MAX_RETRIES} retries for '{keyword}' at ({lat}, {lon})")
    return []


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


# ─── Public API ──────────────────────────────────────────

def compute_scorecard(lat: float, lon: float, radius: int = 1000, weights: Optional[Dict[str, float]] = None) -> Dict[str, Any]:
    """Compute full neighborhood scorecard for a location."""
    if weights is None:
        weights = dict(DEFAULT_WEIGHTS)

    cache_key = f"sc_{round(lat, 4)}_{round(lon, 4)}_{radius}_{','.join(f'{k}:{v}' for k, v in sorted(weights.items()))}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    dimension_results = {}
    total_weight = sum(weights.values()) or 1.0
    overall_score = 0

    for dim_key, dim_info in DIMENSIONS.items():
        r_deg = meters_to_degrees(dim_info["radius_m"], lat)
        pois = _search_pois(dim_info["query"], lat, lon, r_deg, limit=10)

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


CATEGORY_TO_DIMENSION = {
    "transit": "transit",
    "school": "education",
    "hospital": "medical",
    "shop": "shopping",
    "park": "leisure",
    "restaurant": "dining",
}


def compute_scores_from_db(trade_id: int) -> Optional[Dict[str, Any]]:
    """Compute scorecard from existing trade_amenities DB records (no API call needed)."""
    from sqlalchemy import text
    
    from app.main import engine
    with engine.connect() as conn:
        # Fetch all POIs for this trade
        result = conn.execute(text("""
            SELECT category, amenity_name, distance
            FROM trade_amenities
            WHERE trade_id = :tid
        """), {"tid": trade_id})
        rows = result.fetchall()
    
    if not rows:
        return None
    
    # Group POIs by dimension
    dim_pois: Dict[str, List[Dict]] = {k: [] for k in DIMENSIONS}
    for cat, name, dist in rows:
        dim_key = CATEGORY_TO_DIMENSION.get(cat)
        if dim_key and dim_key in dim_pois:
            dim_pois[dim_key].append({"name": name, "distance": dist, "lat": 0, "lon": 0})
    
    # Compute scores per dimension
    weights = {"transit": 0.25, "education": 0.15, "medical": 0.15, "shopping": 0.15, "leisure": 0.15, "dining": 0.15}
    total_weight = sum(weights.values())
    overall = 0
    
    scores = {}
    for dim_key, dim_info in DIMENSIONS.items():
        result = _compute_dimension_score(dim_pois[dim_key], dim_info["max_count"], dim_info["radius_m"])
        w = weights.get(dim_key, 1.0)
        overall += result["score"] * w
        scores[dim_key] = result["score"]
    
    overall = round(overall / total_weight)
    overall = max(0, min(100, overall))
    
    return {
        "overall": overall,
        **scores,
    }


def query_amenities(lat: Optional[float], lon: Optional[float], address: Optional[str] = None) -> Dict[str, Any]:
    """Query nearby amenities for a given location. Pass lat/lon or address."""
    if lat is None or lon is None:
        if not address:
            return {"error": "請提供 lat/lon 或 address"}
        coords = geocode_address(address)
        if not coords:
            return {"error": "無法解析地址，請確認地址格式"}
        lat, lon = coords

    all_pois: Dict[str, List[Dict[str, Any]]] = {}
    
    for dim_key, dim_info in DIMENSIONS.items():
        r_deg = meters_to_degrees(dim_info["radius_m"], lat)
        pois = _search_pois(dim_info["query"], lat, lon, r_deg, limit=10)
        all_pois[dim_key] = {
            "label": dim_info["label"],
            "icon": dim_info["icon"],
            "color": dim_info["color"],
            "pois": pois,
        }
    
    return {
        "location": {"lat": lat, "lon": lon},
        "amenities": all_pois,
    }
