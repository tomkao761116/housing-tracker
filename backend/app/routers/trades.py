"""買賣交易查詢 API"""
from fastapi import APIRouter, Query, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func, desc, and_, Integer
from app.main import get_db
from app.models.database import Trade
from app.utils import compute_building_age, normalize_total_floors
import re
from pydantic import BaseModel
from typing import Optional, List
from datetime import date, datetime, timezone


def parse_chinese_num(s: str) -> Optional[int]:
    """將中文數字轉為阿拉伯數字。"""
    if not s or not isinstance(s, str):
        return None
    s = s.strip()
    if s.isdigit():
        return int(s)
    s = s.replace('層', '')
    if s.isdigit():
        return int(s)
    cn_map = {'零': 0, '一': 1, '二': 2, '三': 3, '四': 4, '五': 5, '六': 6, '七': 7, '八': 8, '九': 9, '十': 10, '百': 100, '千': 1000, '萬': 10000}
    if not any(c in cn_map for c in s):
        return None
    try:
        result = 0
        current = 0
        for ch in s:
            if ch == '十':
                current = (current or 1) * 10
                result += current
                current = 0
            elif ch in ('百', '千', '萬'):
                current = (current or 1) * cn_map[ch]
                result += current
                current = 0
            elif ch in cn_map:
                current = cn_map[ch]
            else:
                return None
        result += current
        return result if result else None
    except Exception:
        return None


def normalize_floor_local(floor_val) -> Optional[str]:
    """標準化樓層欄位。"""
    if floor_val is None:
        return None
    s = str(floor_val).strip()
    if not s or s == '全':
        return s if s else None
    # 處理「十層，十一層」這種多樓層合併交易格式 — 取第一個數字
    parts = re.split(r'[，,、]+', s)
    for part in parts:
        num = parse_chinese_num(part.strip())
        if num is not None:
            return str(num)
    num = parse_chinese_num(s)
    return str(num) if num is not None else s

router = APIRouter()


def normalize_unit_price(val):
    """Convert raw unit_price_tping to 萬/坪 (old data may be in 元/坪)"""
    if val is None:
        return None
    return round(val / 10000, 1) if val > 10000 else round(val, 1)


class TradeResponse(BaseModel):
    id: int
    city: str
    district: str
    address: str
    lat: Optional[float] = None
    lon: Optional[float] = None
    trade_date: Optional[date] = None
    total_price: Optional[int] = None
    unit_price: Optional[float] = None
    unit_price_tping: Optional[float] = None
    building_area: Optional[float] = None
    main_building_area: Optional[float] = None
    rooms: Optional[int] = None
    living_rooms: Optional[int] = None
    bathrooms: Optional[int] = None
    building_type: Optional[str] = None
    floor: Optional[str] = None
    has_elevator: Optional[bool] = None
    build_complete_date: Optional[str] = None
    building_age: Optional[int] = None
    total_floors: Optional[str] = None
    score_overall: Optional[int] = None
    score_transit: Optional[int] = None
    score_education: Optional[int] = None
    score_medical: Optional[int] = None
    score_shopping: Optional[int] = None
    score_leisure: Optional[int] = None
    score_dining: Optional[int] = None

    model_config = {"from_attributes": True}


class FilterRequest(BaseModel):
    city: Optional[str] = None
    district: Optional[str] = None
    min_price: Optional[int] = None
    max_price: Optional[int] = None
    min_unit_price: Optional[float] = None
    max_unit_price: Optional[float] = None
    min_area: Optional[float] = None
    max_area: Optional[float] = None
    min_age: Optional[int] = None
    max_age: Optional[int] = None
    min_rooms: Optional[int] = None
    min_bathrooms: Optional[int] = None
    building_type: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    page: int = 1
    page_size: int = 20


@router.get("", response_model=dict)
def list_trades(
    city: Optional[str] = None,
    district: Optional[str] = None,
    min_price: Optional[int] = None,
    max_price: Optional[int] = None,
    min_unit_price: Optional[float] = None,
    max_unit_price: Optional[float] = None,
    min_area: Optional[float] = None,
    max_area: Optional[float] = None,
    min_age: Optional[int] = None,
    max_age: Optional[int] = None,
    min_rooms: Optional[int] = None,
    building_type: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """列出買賣交易紀錄（支援多條件篩選）"""
    query = db.query(Trade)

    if city:
        query = query.filter(Trade.city == city)
    if district:
        query = query.filter(Trade.district == district)
    if min_price is not None:
        query = query.filter(Trade.total_price >= min_price)
    if max_price is not None:
        query = query.filter(Trade.total_price <= max_price)
    if min_unit_price is not None:
        query = query.filter(Trade.unit_price >= min_unit_price)
    if max_unit_price is not None:
        query = query.filter(Trade.unit_price <= max_unit_price)
    if min_area is not None:
        query = query.filter(Trade.building_area >= min_area)
    if max_area is not None:
        query = query.filter(Trade.building_area <= max_area)
    if min_age is not None or max_age is not None:
        # Compute building age from ROC date format in SQL
        # build_complete_date format: '1010726' = ROC 101/07/26
        # Extract year: substring(build_complete_date from 1 for length-4) for 7-char
        # Simpler: cast first digits based on length
        age_expr = func.extract('year', func.now()) - (
            1911 + func.cast(
                func.case(
                    (func.length(Trade.build_complete_date) == 7, func.substring(Trade.build_complete_date, 1, 3)),
                    (func.length(Trade.build_complete_date) >= 5, func.substring(Trade.build_complete_date, 1, 2) + 100),
                    else_=func.substring(Trade.build_complete_date, 1, 3)
                ),
                Integer
            )
        )
        if min_age is not None:
            query = query.filter(age_expr >= min_age)
        if max_age is not None:
            query = query.filter(age_expr <= max_age)
    if min_rooms is not None:
        query = query.filter(Trade.rooms >= min_rooms)
    if building_type:
        query = query.filter(Trade.building_type.ilike(f"%{building_type}%"))
    if start_date:
        query = query.filter(Trade.trade_date >= start_date)
    if end_date:
        query = query.filter(Trade.trade_date <= end_date)

    total = query.count()
    trades = (
        query.order_by(desc(Trade.trade_date))
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    # Lazy scoring: 對有座標但無評分（NULL 或 0）的記錄，優先從 trade_amenities 計算
    unscored = [t for t in trades if t.lat is not None and t.lon is not None and (t.score_overall is None or t.score_overall == 0)]
    if unscored:
        from app.services.amenities import compute_scores_from_db
        for t in unscored:
            try:
                scores = compute_scores_from_db(t.id)
                if scores:
                    t.score_overall = float(scores["overall"])
                    t.score_transit = float(scores["transit"])
                    t.score_education = float(scores["education"])
                    t.score_medical = float(scores["medical"])
                    t.score_shopping = float(scores["shopping"])
                    t.score_leisure = float(scores["leisure"])
                    t.score_dining = float(scores["dining"])
                    t.score_updated_at = datetime.now(timezone.utc)
                    print(f"[LazyScore] Trade {t.id}: computed from DB -> overall={scores['overall']}")
                else:
                    # Fallback to API-based scoring
                    from app.routers.scorecard import compute_scorecard_for_location as get_scores
                    api_scores = get_scores(t.lat, t.lon)
                    t.score_overall = float(api_scores["overall"])
                    t.score_transit = float(api_scores["transit"])
                    t.score_education = float(api_scores["education"])
                    t.score_medical = float(api_scores["medical"])
                    t.score_shopping = float(api_scores["shopping"])
                    t.score_leisure = float(api_scores["leisure"])
                    t.score_dining = float(api_scores["dining"])
                    t.score_updated_at = datetime.now(timezone.utc)
                    print(f"[LazyScore] Trade {t.id}: computed via API -> overall={api_scores['overall']}")
            except Exception as e:
                print(f"[LazyScore] Failed for trade {t.id}: {e}")
        db.commit()
        for t in trades:
            db.refresh(t)

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "data": [
            {
                "id": t.id,
                "city": t.city,
                "district": t.district,
                "address": t.address,
                "lat": round(t.lat, 6) if t.lat else None,
                "lon": round(t.lon, 6) if t.lon else None,
                "trade_date": t.trade_date.isoformat() if t.trade_date else None,
                "total_price": t.total_price,
                "unit_price": normalize_unit_price(t.unit_price),
                "unit_price_tping": normalize_unit_price(t.unit_price_tping),
                "building_area": round(t.building_area, 2) if t.building_area else None,
                "land_area": round(t.land_area, 2) if t.land_area else None,
                "main_building_area": round(t.main_building_area, 2) if t.main_building_area else None,
                "is_land_only": (t.building_type == '其他') and (not t.building_area or t.building_area == 0),
                "rooms": t.rooms,
                "living_rooms": t.living_rooms,
                "bathrooms": t.bathrooms,
                "building_type": t.building_type,
                "floor": normalize_floor_local(t.floor),
                "total_floors": normalize_total_floors(t.total_floors),
                "has_elevator": t.has_elevator,
                "score_overall": round(t.score_overall) if t.score_overall is not None else None,
                "score_transit": round(t.score_transit) if t.score_transit is not None else None,
                "score_education": round(t.score_education) if t.score_education is not None else None,
                "score_medical": round(t.score_medical) if t.score_medical is not None else None,
                "score_shopping": round(t.score_shopping) if t.score_shopping is not None else None,
                "score_leisure": round(t.score_leisure) if t.score_leisure is not None else None,
                "score_dining": round(t.score_dining) if t.score_dining is not None else None,
                "build_complete_date": t.build_complete_date,
                "building_age": compute_building_age(t.build_complete_date),
            }
            for t in trades
        ]
    }


@router.get("/nearby")
def nearby_trades(
    lat: float = Query(..., description="緯度"),
    lon: float = Query(..., description="經度"),
    radius: int = Query(1000, ge=100, le=10000, description="搜尋半徑（公尺）"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db)
):
    """找出指定座標附近一定半徑內的成交紀錄（PostGIS 空間查詢）"""
    from sqlalchemy import text
    
    # Bounding box approach - uses B-tree index on (lon, lat), much faster than GiST on this hardware
    # ~1 degree ≈ 111km ≈ 111000m for lat; lon depends on latitude: 111000 * cos(lat) m/deg
    import math as _math
    deg_lat = radius / 111000.0
    deg_lon = radius / (111000.0 * _math.cos(_math.radians(lat)))
    
    lat_min = lat - deg_lat
    lat_max = lat + deg_lat
    lon_min = lon - deg_lon
    lon_max = lon + deg_lon
    
    # Fetch paginated results with distance (computed in Python for speed)
    query_sql = text(f'''
        SELECT id, city, district, address, lat, lon,
               trade_date, total_price, unit_price, unit_price_tping,
               building_area, land_area, main_building_area,
               rooms, living_rooms, bathrooms, building_type,
               floor, total_floors, has_elevator, build_complete_date
        FROM trades
        WHERE lat IS NOT NULL AND lon IS NOT NULL
        AND lat BETWEEN {lat_min} AND {lat_max}
        AND lon BETWEEN {lon_min} AND {lon_max}
        ORDER BY ABS(lat - {lat})
        LIMIT :limit OFFSET :offset
    ''')
    # Fetch more rows to account for haversine filtering at bbox edges
    fetch_limit = page_size * 3 + 1
    result = db.execute(query_sql, {"limit": fetch_limit, "offset": (page - 1) * page_size})
    rows = result.fetchall()
    
    # Haversine distance calculation
    R_EARTH = 6371000.0
    rad_lat = _math.radians(lat)
    cos_rad_lat = _math.cos(rad_lat)
    
    def haversine_dist(rlat, rlon):
        dlat = _math.radians(rlat - lat)
        dlon = _math.radians(rlon - lon)
        a = _math.sin(dlat/2)**2 + cos_rad_lat * _math.cos(_math.radians(rlat)) * _math.sin(dlon/2)**2
        return R_EARTH * 2 * _math.asin(min(1.0, _math.sqrt(a)))
    
    # Filter by actual radius and sort by distance
    with_distances = []
    for row in rows:
        _d = dict(row._mapping) if hasattr(row, '_mapping') else dict(zip(['id','city','district','address','lat','lon','trade_date','total_price','unit_price','unit_price_tping','building_area','land_area','main_building_area','rooms','living_rooms','bathrooms','building_type','floor','total_floors','has_elevator','build_complete_date'], row))
        rlat = _d.get("lat")
        rlon = _d.get("lon")
        dist = round(haversine_dist(rlat, rlon)) if rlat and rlon else None
        if dist is not None and dist <= radius:
            with_distances.append((_d, dist))
    
    # Sort by distance
    with_distances.sort(key=lambda x: x[1])
    
    has_more = len(with_distances) > page_size
    results = []
    for _d, dist in with_distances[:page_size]:
        results.append({
            "id": _d["id"],
            "city": _d["city"],
            "district": _d["district"],
            "address": _d["address"],
            "building_name": _d["address"],
            "trade_date": _d["trade_date"].isoformat() if _d.get("trade_date") else None,
            "total_price": _d["total_price"],
            "unit_price": normalize_unit_price(_d.get("unit_price_tping")),
            "area_sqm": round(_d["building_area"], 2) if _d.get("building_area") else None,
            "floor": normalize_floor_local(_d.get("floor")),
            "total_floors": normalize_total_floors(_d.get("total_floors")),
            "building_age": compute_building_age(_d.get("build_complete_date")),
            "distance_m": dist,
        })
    
    return {
        "count": len(results),
        "has_more": has_more,
        "page": page,
        "page_size": page_size,
        "data": results,
    }


@router.get("/search")
def search_address(
    q: str = Query(..., min_length=2),
    city: Optional[str] = None,
    limit: int = Query(20, ge=1, le=50),
    db: Session = Depends(get_db)
):
    """依地址關鍵字搜尋"""
    query = db.query(Trade).filter(Trade.address.ilike(f"%{q}%"))
    if city:
        query = query.filter(Trade.city == city)
    
    results = query.order_by(desc(Trade.trade_date)).limit(limit).all()
    
    # Group by unique addresses, show latest price
    seen = {}
    for t in results:
        key = t.address
        if key not in seen:
            seen[key] = t
    
    return {
        "query": q,
        "count": len(seen),
        "data": [
            {
                "city": t.city,
                "district": t.district,
                "address": t.address,
                "latest_date": t.trade_date.isoformat() if t.trade_date else None,
                "latest_price": t.total_price,
                "latest_unit_price": normalize_unit_price(t.unit_price),
            }
            for t in seen.values()
        ]
    }


@router.get("/{trade_id}")
def get_trade(trade_id: int, db: Session = Depends(get_db)):
    """取得單一交易詳情"""
    trade = db.query(Trade).filter(Trade.id == trade_id).first()
    if not trade:
        return {"error": "Not found"}
    resp = TradeResponse.model_validate(trade)
    resp.unit_price = normalize_unit_price(resp.unit_price)
    resp.unit_price_tping = normalize_unit_price(resp.unit_price_tping)
    resp.building_age = compute_building_age(resp.build_complete_date)
    return resp
