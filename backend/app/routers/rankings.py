"""房屋排行與交易列表 API"""
from typing import Optional
import time

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, Integer, text, case as sql_case
from app.main import get_db
from app.models.database import Trade, TradeAmenity
from app.utils import compute_building_age
from app.services.api_cache import rankings_cache, districts_cache
from pydantic import BaseModel
router = APIRouter()

_TRADES_TOTAL_CACHE = None
_TRADES_TOTAL_CACHE_TIME = 0


def normalize_unit_price(val):
    """Convert raw unit_price_tping to 萬/坪 (old data may be in 元/坪)"""
    if val is None:
        return None
    return round(val / 10000, 1) if val > 10000 else round(val, 1)


# ---------------------------------------------------------------------------
# 1. City Rankings
# ---------------------------------------------------------------------------

@router.get("/api/rankings/cities")
def rank_cities(db: Session = Depends(get_db)):
    """Rank all cities by avg unit_price_tping, median price, and transaction count."""
    # Cache check
    cached = rankings_cache.get("cities_ranking")
    if cached is not None:
        return cached
    
    results = (
        db.query(Trade)
        .with_entities(
            Trade.city,
            func.count(Trade.id).label("transaction_count"),
            func.avg(Trade.unit_price_tping).label("avg_unit_price_tping"),
            func.avg(Trade.total_price).label("avg_total_price"),
        )
        .group_by(Trade.city)
        .order_by(func.avg(Trade.unit_price_tping).desc())
        .all()
    )

    # Compute medians, min, avg_building_age per city using raw SQL
    city_names = [r[0] for r in results]
    if not city_names:
        return {"cities": [], "total": 0}

    placeholders = ",".join(f"'{c}'" for c in city_names)
    detail_sql = f"""
        SELECT city, 
               percentile_cont(0.5) WITHIN GROUP (ORDER BY total_price) AS median_price,
               MIN(total_price) AS min_total_price,
               AVG(CASE WHEN build_complete_date IS NOT NULL 
                        AND build_complete_date !~ '[^0-9]' 
                        AND LENGTH(build_complete_date) >= 2 THEN
                   GREATEST(0, EXTRACT(YEAR FROM NOW()) - (1911 + CASE 
                       WHEN LENGTH(build_complete_date) = 7 THEN CAST(SUBSTRING(build_complete_date, 1, 3) AS INTEGER)
                       WHEN LENGTH(build_complete_date) >= 5 THEN CAST(SUBSTRING(build_complete_date, 1, 2) AS INTEGER) + 100
                       ELSE CAST(SUBSTRING(build_complete_date, 1, 3) AS INTEGER)
                   END))
               END) AS avg_building_age
        FROM trades 
        WHERE city IN ({placeholders})
        GROUP BY city
    """
    detail_rows = db.execute(text(detail_sql)).fetchall()
    detail_map = {row[0]: {"median": row[1], "min_total": row[2], "avg_age": row[3]} for row in detail_rows}

    ranking = []
    for idx, r in enumerate(results, start=1):
        city = r[0]
        detail = detail_map.get(city, {})
        median = detail.get("median")
        min_total = detail.get("min_total")
        avg_age = detail.get("avg_age")
        ranking.append({
            "rank": idx,
            "city": city,
            "transaction_count": r[1],
            "avg_unit_price_tping": normalize_unit_price(r[2]),
            "avg_total_price": round(r[3] / 10000, 0) if r[3] else None,
            "median_total_price": round(median / 10000, 0) if median else None,
            "min_total_price": round(min_total / 10000, 0) if min_total else None,
            "avg_building_age": round(avg_age, 1) if avg_age else None,
        })

    return rankings_cache.set("cities_ranking", {"cities": ranking, "total": len(ranking)}) or {"cities": ranking, "total": len(ranking)}


# ---------------------------------------------------------------------------
# 2. District Rankings within a City
# ---------------------------------------------------------------------------

@router.get("/api/rankings/districts")
def rank_districts(
    city: str = Query(..., description="City name, e.g. 臺北市"),
    db: Session = Depends(get_db),
):
    """Rank districts within a city by avg unit_price_tping, median price, and transaction count."""
    # Cache check
    cache_key = f"districts_{city}"
    cached = rankings_cache.get(cache_key)
    if cached is not None:
        return cached
    
    results = (
        db.query(Trade)
        .filter(Trade.city == city)
        .with_entities(
            Trade.district,
            func.count(Trade.id).label("transaction_count"),
            func.avg(Trade.unit_price_tping).label("avg_unit_price_tping"),
            func.avg(Trade.total_price).label("avg_total_price"),
        )
        .group_by(Trade.district)
        .order_by(func.avg(Trade.unit_price_tping).desc())
        .all()
    )

    district_names = [r[0] for r in results]
    if not district_names:
        return {"city": city, "districts": [], "total": 0}

    placeholders = ",".join(f"'{d}'" for d in district_names)
    detail_sql = f"""
        SELECT district, 
               percentile_cont(0.5) WITHIN GROUP (ORDER BY total_price) AS median_price,
               MIN(total_price) AS min_total_price,
               AVG(CASE WHEN build_complete_date IS NOT NULL THEN
                   GREATEST(0, EXTRACT(YEAR FROM NOW()) - (1911 + CASE 
                       WHEN LENGTH(build_complete_date) = 7 THEN CAST(SUBSTRING(build_complete_date, 1, 3) AS INTEGER)
                       WHEN LENGTH(build_complete_date) >= 5 THEN CAST(SUBSTRING(build_complete_date, 1, 2) AS INTEGER) + 100
                       ELSE CAST(SUBSTRING(build_complete_date, 1, 3) AS INTEGER)
                   END))
               END) AS avg_building_age
        FROM trades 
        WHERE city = '{city}' AND district IN ({placeholders})
        GROUP BY district
    """
    detail_rows = db.execute(text(detail_sql)).fetchall()
    detail_map = {row[0]: {"median": row[1], "min_total": row[2], "avg_age": row[3]} for row in detail_rows}

    ranking = []
    for idx, r in enumerate(results, start=1):
        district = r[0]
        detail = detail_map.get(district, {})
        median = detail.get("median")
        min_total = detail.get("min_total")
        avg_age = detail.get("avg_age")
        ranking.append({
            "rank": idx,
            "district": district,
            "transaction_count": r[1],
            "avg_unit_price_tping": normalize_unit_price(r[2]),
            "avg_total_price": round(r[3] / 10000, 0) if r[3] else None,
            "median_total_price": round(median / 10000, 0) if median else None,
            "min_total_price": round(min_total / 10000, 0) if min_total else None,
            "avg_building_age": round(avg_age, 1) if avg_age else None,
        })

    result = {"city": city, "districts": ranking, "total": len(ranking)}
    rankings_cache.set(cache_key, result)
    return result


# ---------------------------------------------------------------------------
# 2b. District list for frontend dropdown
# ---------------------------------------------------------------------------

@router.get("/api/list/districts")
def list_districts(db: Session = Depends(get_db)):
    """Return all distinct district names (e.g. '臺北市大同區')."""
    # Cache check
    cached = districts_cache.get("all_districts")
    if cached is not None:
        return cached
    
    rows = db.query(Trade.district).filter(
        Trade.district.isnot(None), Trade.district != ''
    ).distinct().order_by(Trade.district).all()
    result = [r[0] for r in rows]
    districts_cache.set("all_districts", result)
    return result


# ---------------------------------------------------------------------------
# 3. Filtered / Paginated Trade Listing
# ---------------------------------------------------------------------------

VALID_SORT_FIELDS = {
    "total_price",
    "unit_price",
    "unit_price_tping",
    "building_area",
    "main_building_area",
    "trade_date",
    "rooms",
    "living_rooms",
    "bathrooms",
    "floor",
}


@router.get("/api/list/trades")
def list_trades(
    # Location filters
    city: Optional[str] = Query(None, description="City filter"),
    district: Optional[str] = Query(None, description="District filter"),
    keyword: Optional[str] = Query(None, description="Keyword search (address, building name)"),
    # Room filters
    rooms: Optional[int] = Query(None, ge=0, description="Number of rooms"),
    living_rooms: Optional[int] = Query(None, ge=0, description="Number of living rooms"),
    bathrooms: Optional[int] = Query(None, ge=0, description="Number of bathrooms"),
    # Area filters (平方公尺)
    min_area: Optional[float] = Query(None, ge=0, description="Min building area"),
    max_area: Optional[float] = Query(None, ge=0, description="Max building area"),
    # Price filters
    min_price: Optional[float] = Query(None, ge=0, description="Min total price"),
    max_price: Optional[float] = Query(None, ge=0, description="Max total price"),
    min_unit_price: Optional[float] = Query(None, ge=0, description="Min unit price"),
    max_unit_price: Optional[float] = Query(None, ge=0, description="Max unit price"),
    # Floor filters
    min_floor: Optional[int] = Query(None, description="Min floor number"),
    max_floor: Optional[int] = Query(None, description="Max floor number"),
    # Building attributes
    building_type: Optional[str] = Query(None, description="Building type, e.g. 住宅大樓"),
    has_elevator: Optional[bool] = Query(None, description="Has elevator"),
    season: Optional[str] = Query(None, description="Season, e.g. 101S3"),
    # Pagination
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=200, description="Items per page"),
    # Sorting
    sort_by: str = Query("trade_date", description="Field to sort by"),
    sort_order: str = Query("desc", regex="^(asc|desc)$", description="Sort order"),
    # Dependency
    db: Session = Depends(get_db),
):
    """Filtered and paginated trade listing."""

    query = db.query(Trade)

    # --- Apply filters ---
    # City 編碼轉換（台北市→臺北市）
    CITY_ALIAS = {"台北市": "臺北市", "台中市": "臺中市", "台南市": "臺南市", "台東縣": "臺東縣"}
    if city:
        query = query.filter(Trade.city == CITY_ALIAS.get(city, city))
    if district:
        query = query.filter(Trade.district == district)
    if keyword:
        search_pattern = f"%{keyword}%"
        query = query.filter(Trade.address.ilike(search_pattern))
    if rooms is not None:
        query = query.filter(Trade.rooms == rooms)
    if living_rooms is not None:
        query = query.filter(Trade.living_rooms == living_rooms)
    if bathrooms is not None:
        query = query.filter(Trade.bathrooms == bathrooms)
    if min_area is not None:
        query = query.filter(Trade.building_area >= min_area)
    if max_area is not None:
        query = query.filter(Trade.building_area <= max_area)
    if min_price is not None:
        query = query.filter(Trade.total_price >= min_price)
    if max_price is not None:
        query = query.filter(Trade.total_price <= max_price)
    if min_unit_price is not None:
        query = query.filter(Trade.unit_price >= min_unit_price)
    if max_unit_price is not None:
        query = query.filter(Trade.unit_price <= max_unit_price)
    if min_floor is not None:
        query = query.filter(
            func.cast(
                func.regexp_replace(Trade.floor, "[^0-9]", "", "g"), Integer
            ) >= min_floor
        )
    if max_floor is not None:
        query = query.filter(
            func.cast(
                func.regexp_replace(Trade.floor, "[^0-9]", "", "g"), Integer
            ) <= max_floor
        )
    if building_type:
        query = query.filter(Trade.building_type == building_type)
    if has_elevator is not None:
        query = query.filter(Trade.has_elevator == has_elevator)
    if season:
        query = query.filter(Trade.season == season)

    # --- Sorting + Pagination ---
    global _TRADES_TOTAL_CACHE, _TRADES_TOTAL_CACHE_TIME
    
    sort_col = getattr(Trade, sort_by, None) if sort_by in VALID_SORT_FIELDS else Trade.trade_date
    offset = (page - 1) * page_size
    
    # 智慧 COUNT：有篩選條件才查 DB，無篩選用快取
    has_filter = any([city, district, keyword, rooms is not None, living_rooms is not None, 
                      bathrooms is not None, min_area is not None, max_area is not None,
                      min_price is not None, max_price is not None, min_unit_price is not None,
                      max_unit_price is not None, min_floor is not None, max_floor is not None,
                      building_type, has_elevator is not None, season])
    
    if has_filter:
        total = query.count()
    else:
        now = time.time()
        if _TRADES_TOTAL_CACHE and (now - _TRADES_TOTAL_CACHE_TIME) < 300:  # 5 min TTL
            total = _TRADES_TOTAL_CACHE
        else:
            total = query.count()
            _TRADES_TOTAL_CACHE = total
            _TRADES_TOTAL_CACHE_TIME = now
    
    trades = query.order_by(sort_col.desc() if sort_order == "desc" else sort_col.asc()).offset(offset).limit(page_size).all()

    # ── Amenities (即時查詢 poi_master) ──
    POI_CATEGORY_MAP = {
        "bus_station": "transit", "train_station": "transit", "subway_entrance": "transit", "tram_stop": "transit",
        "kindergarten": "education", "school": "education", "university": "education", "college": "education",
        "hospital": "medical", "clinic": "medical", "pharmacy": "medical",
        "supermarket": "shopping", "convenience": "shopping", "department_store": "shopping", "mall": "shopping",
        "playground": "leisure", "park": "leisure", "gym": "leisure", "swimming_pool": "leisure",
        "restaurant": "dining", "cafe": "dining", "food_court": "dining",
    }
    DIM_ORDER = ["transit", "education", "medical", "shopping", "leisure", "dining"]
    DIM_LABELS = {
        "transit": "交通", "education": "教育", "medical": "醫療",
        "shopping": "購物", "leisure": "休閒", "dining": "餐飲",
    }

    EXCLUDED_SUB_TYPES = {"bank", "atm", "motorcycle", "car", "optician", "hairdresser", "beauty", "laundry", "place_of_worship", "information", "hotel", "hostel", "guest_house", "motel"}
    
    def get_pois_for_trade(lat, lon):
        """即時查詢 poi_master，回傳各維度前 5 筆"""
        if not lat or not lon:
            return []
        try:
            dlat = 0.03  # ~3km bounding box
            dlon = 0.03
            excluded = "', '".join(EXCLUDED_SUB_TYPES)
            result = db.execute(text(f"""
                SELECT * FROM (
                    SELECT category, sub_type, name,
                           (6371000 * acos(
                               cos(radians(:lat)) * cos(radians(lat)) *
                               cos(radians(lon) - radians(:lon)) +
                               sin(radians(:lat)) * sin(radians(lat))
                           )) AS dist_m
                    FROM poi_master
                    WHERE lat BETWEEN :lat_min AND :lat_max
                      AND lon BETWEEN :lon_min AND :lon_max
                      AND sub_type NOT IN ('{excluded}')
                ) t
                WHERE dist_m < 3000
                ORDER BY dist_m ASC
                LIMIT 100
            """), {"lat": lat, "lon": lon, "lat_min": lat-dlat, "lat_max": lat+dlat, "lon_min": lon-dlon, "lon_max": lon+dlon})
            rows = result.fetchall()
            dim_groups = {}
            for row in rows:
                cat = row[0]  # category column
                if cat not in DIM_ORDER:
                    continue
                dim_groups.setdefault(cat, []).append({
                    "name": row[2] or row[1],  # name or sub_type
                    "distance": round(row[3] / 1000, 1),
                })
            amenities = []
            for dk in DIM_ORDER:
                if dk in dim_groups:
                    sorted_items = sorted(dim_groups[dk], key=lambda x: x["distance"])[:5]
                    amenities.append({
                        "key": dk,
                        "category": DIM_LABELS[dk],
                        "items": sorted_items,
                    })
            return amenities
        except Exception:
            return []

    items = []
    for t in trades:
        amenities = get_pois_for_trade(t.lat, t.lon)

        items.append({
            "id": t.id,
            "city": t.city,
            "district": t.district,
            "address": t.address,
            "trade_date": t.trade_date.isoformat() if t.trade_date else None,
            "trade_date_roc": t.trade_date_roc,
            "total_price": t.total_price,
            "unit_price": t.unit_price,
            "unit_price_tping": normalize_unit_price(t.unit_price_tping),
            "building_area": t.building_area,
            "main_building_area": t.main_building_area,
            "land_area": t.land_area,
            "building_age": compute_building_age(t.build_complete_date),
            "rooms": t.rooms,
            "living_rooms": t.living_rooms,
            "bathrooms": t.bathrooms,
            "building_type": t.building_type,
            "floor": t.floor,
            "has_elevator": t.has_elevator,
            "season": t.season,
            "lat": t.lat,
            "lon": t.lon,
            "total_floors": t.total_floors,
            "score_overall": t.score_overall,
            "score_transit": t.score_transit,
            "score_education": t.score_education,
            "score_medical": t.score_medical,
            "score_shopping": t.score_shopping,
            "score_leisure": t.score_leisure,
            "score_dining": t.score_dining,
            "amenities": amenities,
        })

    total_pages = (total + page_size - 1) // page_size if total > 0 else 0

    return {
        "items": items,
        "page": page,
        "page_size": page_size,
        "total": total,
        "total_pages": total_pages,
    }
