"""Amenities API Router — prefer DB cache, fallback to live query."""
from fastapi import APIRouter, Query, Depends
from sqlalchemy.orm import Session
from app.main import get_db
from app.models.database import Trade, TradeAmenity
from app.services.amenities import query_amenities

router = APIRouter()


CATEGORY_LABELS = {
    "transit": {"label": "交通", "icon": "train-front", "color": "#6366f1"},
    "education": {"label": "教育", "icon": "graduation-cap", "color": "#3b82f6"},
    "medical": {"label": "醫療", "icon": "heart-pulse", "color": "#ef4444"},
    "hospital": {"label": "醫療", "icon": "heart-pulse", "color": "#ef4444"},
    "pharmacy": {"label": "醫療", "icon": "heart-pulse", "color": "#ef4444"},
    "shopping": {"label": "購物", "icon": "shopping-cart", "color": "#f59e0b"},
    "shop": {"label": "購物", "icon": "shopping-cart", "color": "#f59e0b"},
    "mall": {"label": "購物", "icon": "shopping-cart", "color": "#f59e0b"},
    "leisure": {"label": "休閒", "icon": "trees", "color": "#22c55e"},
    "park": {"label": "休閒", "icon": "trees", "color": "#22c55e"},
    "dining": {"label": "餐飲", "icon": "utensils-crossed", "color": "#ec4899"},
    "restaurant": {"label": "餐飲", "icon": "utensils-crossed", "color": "#ec4899"},
    "school": {"label": "教育", "icon": "graduation-cap", "color": "#3b82f6"},
}

# Canonical order for displaying dimensions (score + amenities must match)
DIMENSION_ORDER = ["transit", "education", "medical", "shopping", "leisure", "dining"]

# Map raw category keys to canonical dimension keys
CATEGORY_TO_DIMENSION = {
    "transit": "transit",
    "school": "education", "education": "education",
    "hospital": "medical", "pharmacy": "medical", "medical": "medical",
    "shop": "shopping", "mall": "shopping", "shopping": "shopping",
    "park": "leisure", "leisure": "leisure",
    "restaurant": "dining", "dining": "dining",
}


def _format_db_amenities(rows):
    """Group raw trade_amenities rows into canonical dimensions, ordered consistently."""
    # Group by raw category first
    groups: dict[str, list[dict]] = {}
    for row in rows:
        cat = row.category
        groups.setdefault(cat, []).append({
            "name": row.amenity_name,
            "distance": row.distance,
            "lat": row.lat,
            "lon": row.lon,
        })
    
    # Merge raw categories into canonical dimensions
    dim_groups: dict[str, list[dict]] = {}
    for cat, items in groups.items():
        dim_key = CATEGORY_TO_DIMENSION.get(cat, cat)
        dim_groups.setdefault(dim_key, []).extend(items)
    
    # Build result in canonical order
    result = {}
    for dim_key in DIMENSION_ORDER:
        if dim_key not in dim_groups:
            continue
        items = sorted(dim_groups[dim_key], key=lambda p: p["distance"])[:5]
        info = CATEGORY_LABELS.get(dim_key, {"label": dim_key, "icon": "📍", "color": "#6b7280"})
        result[dim_key] = {
            "label": info["label"],
            "icon": info["icon"],
            "color": info["color"],
            "items": items,
        }
    return result


@router.get("/amenities")
def get_amenities(
    lat: float = Query(None, description="Latitude"),
    lon: float = Query(None, description="Longitude"),
    address: str = Query(None, description="Address (auto-geocoded if no coords)"),
    trade_id: int = Query(None, description="Trade ID (prefer DB cache)"),
    db: Session = Depends(get_db),
):
    """Query nearby amenities. Prefer DB cache via trade_id; fallback to live Nominatim."""

    # ── Fast path: look up from trade_amenities table ──
    if trade_id:
        rows = db.query(TradeAmenity).filter(
            TradeAmenity.trade_id == trade_id
        ).order_by(TradeAmenity.distance).all()
        if rows:
            amenities = _format_db_amenities(rows)
            # Get trade location for context
            trade = db.query(Trade).filter(Trade.id == trade_id).first()
            location = None
            if trade:
                location = {"lat": trade.lat, "lon": trade.lon}
            return {
                "location": location,
                "amenities": amenities,
                "source": "db_cache",
            }

    # ── Fallback: live Nominatim query ──
    result = query_amenities(lat, lon, address=address)
    if result is None:
        return {"error": "Failed to query amenities", "items": []}
    result["source"] = "live"
    return result
