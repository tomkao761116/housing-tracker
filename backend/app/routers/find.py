"""找房 API — 一站式購屋篩選
整合：條件篩選 + 生活機能評分 + 通勤評估 + 價格分析
"""
from fastapi import APIRouter, Query, Depends
from typing import Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_, Integer, text
from app.utils import compute_building_age
from app.cache import api_cache
import math
import time
import hashlib

from app.models.database import Trade, TradeAmenity

router = APIRouter()


def _make_cache_key(func_name: str, **kwargs) -> str:
    """Build a deterministic cache key from function name and query params."""
    parts = [func_name]
    for k, v in sorted(kwargs.items()):
        if v is not None:
            parts.append(f"{k}={v}")
    raw = "|".join(parts)
    return hashlib.md5(raw.encode()).hexdigest()


def get_db():
    from app.main import SessionLocal
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def normalize_unit_price(val):
    if val is None:
        return None
    return round(val / 10000, 1) if val > 10000 else round(val, 1)


def haversine_km(lat1, lon1, lat2, lon2):
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2)
    return R * 2 * math.asin(min(1, math.sqrt(a)))


# ─── 預設通勤地點（各大城市主要辦公區）───
OFFICE_LOCATIONS = {
    '臺北市': [
        {'name': '信義計畫區', 'lat': 25.0338, 'lon': 121.5645},
        {'name': '南港軟體園區', 'lat': 25.0529, 'lon': 121.6068},
        {'name': '內湖科技園區', 'lat': 25.0742, 'lon': 121.5750},
    ],
    '新北市': [
        {'name': '板橋車站', 'lat': 25.0140, 'lon': 121.4602},
        {'name': '新莊副都心', 'lat': 25.0405, 'lon': 121.4538},
    ],
    '桃園市': [
        {'name': '中壢站前', 'lat': 24.9536, 'lon': 121.2295},
        {'name': '桃園高鐵站', 'lat': 25.0153, 'lon': 121.2193},
    ],
    '新竹市': [
        {'name': '竹科', 'lat': 24.7894, 'lon': 121.0094},
    ],
    '新竹縣': [
        {'name': '竹科', 'lat': 24.7894, 'lon': 121.0094},
        {'name': '竹北交流道', 'lat': 24.8069, 'lon': 121.0267},
    ],
    '臺中市': [
        {'name': '中科', 'lat': 24.1586, 'lon': 120.6667},
        {'name': '台中七期', 'lat': 24.1477, 'lon': 120.6737},
    ],
    '台南市': [
        {'name': '台南火車站', 'lat': 22.9963, 'lon': 120.2131},
    ],
    '高雄市': [
        {'name': '高雄捷運紅線', 'lat': 22.6376, 'lon': 120.3137},
    ],
}


@router.get("/find")
def find_homes(
    # ── 地區篩選 ──
    city: Optional[str] = Query(None, description="縣市"),
    district: Optional[str] = Query(None, description="行政區"),
    region: Optional[str] = Query(None, description="區域: 北部/中部/南部/東部"),
    keyword: Optional[str] = Query(None, description="關鍵字搜尋（地址）"),

    # ── 預算篩選 ──
    min_total_price: Optional[float] = Query(None, ge=0, description="最低總價（萬元）"),
    max_total_price: Optional[float] = Query(None, ge=0, description="最高總價（萬元）"),
    min_unit_price: Optional[float] = Query(None, ge=0, description="最低單價（萬/坪）"),
    max_unit_price: Optional[float] = Query(None, ge=0, description="最高單價（萬/坪）"),

    # ── 房屋條件 ──
    min_area_tping: Optional[float] = Query(None, ge=0, description="最小面積（坪）"),
    max_area_tping: Optional[float] = Query(None, ge=0, description="最大面積（坪）"),
    min_age: Optional[int] = Query(None, ge=0, description="最小屋齡（年）"),
    max_age: Optional[int] = Query(None, ge=0, description="最大屋齡（年）"),
    building_type: Optional[str] = Query(None, description="建物型態"),
    min_rooms: Optional[int] = Query(None, ge=0, description="最少房間數"),
    min_living_rooms: Optional[int] = Query(None, ge=0, description="最少廳數"),
    min_bathrooms: Optional[int] = Query(None, ge=0, description="最少衛浴數"),
    has_elevator: Optional[bool] = Query(None, description="是否有電梯"),

    # ── 生活機能篩選 ──
    min_score_overall: Optional[int] = Query(None, ge=0, le=100, description="最低綜合評分"),
    min_score_transit: Optional[int] = Query(None, ge=0, le=100, description="最低交通分"),
    min_score_education: Optional[int] = Query(None, ge=0, le=100, description="最低教育分"),
    min_score_medical: Optional[int] = Query(None, ge=0, le=100, description="最低醫療分"),
    min_score_shopping: Optional[int] = Query(None, ge=0, le=100, description="最低購物分"),
    min_score_leisure: Optional[int] = Query(None, ge=0, le=100, description="最低休閒分"),
    min_score_dining: Optional[int] = Query(None, ge=0, le=100, description="最低餐飲分"),

    # ── 通勤篩選 ──
    commute_city: Optional[str] = Query(None, description="通勤目的地縣市"),
    max_commute_time: Optional[int] = Query(None, ge=5, le=120, description="最長通勤時間（分鐘，車程估算）"),

    # ── 排序與分頁 ──
    sort_by: str = Query("trade_date", description="排序欄位"),
    sort_order: str = Query("desc", regex="^(asc|desc)$", description="排序方向"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),

    db: Session = Depends(get_db),
):
    """
    一站式找房 API — 支援所有維度的篩選、排序和分頁
    """

    # ── Cache lookup (3 min TTL for find results) ──
    cache_key = _make_cache_key("find_homes",
        city=city, district=district, region=region, keyword=keyword,
        min_total_price=min_total_price, max_total_price=max_total_price,
        min_unit_price=min_unit_price, max_unit_price=max_unit_price,
        min_area_tping=min_area_tping, max_area_tping=max_area_tping,
        min_age=min_age, max_age=max_age, building_type=building_type,
        min_rooms=min_rooms, min_living_rooms=min_living_rooms,
        min_bathrooms=min_bathrooms, has_elevator=has_elevator,
        min_score_overall=min_score_overall, min_score_transit=min_score_transit,
        min_score_education=min_score_education, min_score_medical=min_score_medical,
        min_score_shopping=min_score_shopping, min_score_leisure=min_score_leisure,
        min_score_dining=min_score_dining,
        commute_city=commute_city, max_commute_time=max_commute_time,
        sort_by=sort_by, sort_order=sort_order, page=page, page_size=page_size,
    )
    cached = api_cache.get(cache_key)
    if cached is not None:
        return cached

    query = db.query(Trade)

    # ── 繁簡體縣市名稱對照（前端可能傳簡體）───
    CITY_NORMALIZE = {
        '台北': '臺北', '台中': '臺中', '台南': '臺南', '台東': '臺東',
    }
    
    def normalize_city(name):
        """把繁簡體統一轉成 DB 中的寫法"""
        if not name:
            return name
        for simp, trad in CITY_NORMALIZE.items():
            name = name.replace(simp, trad)
        return name

    # ── 地區篩選（用 city 欄位走索引，不走 address LIKE 全表掃描）───
    if city:
        normalized = normalize_city(city)
        query = query.filter(Trade.city == normalized)
    if district:
        query = query.filter(Trade.district == district)
    if region:
        regions = {
            '北部': ['基隆市', '宜蘭縣', '臺北市', '新北市', '桃園市', '新竹市', '新竹縣'],
            '中部': ['苗栗縣', '臺中市', '彰化縣', '南投縣', '雲林縣', '嘉義縣', '嘉義市'],
            '南部': ['澎湖縣', '臺南市', '高雄市', '屏東縣'],
            '東部': ['花蓮縣', '臺東縣', '金門縣', '連江縣'],
        }
        counties = [normalize_city(c) for c in regions.get(region, [])]
        if counties:
            query = query.filter(Trade.city.in_(counties))

    # ── 關鍵字搜尋（地址、建案名稱）───
    if keyword:
        query = query.filter(Trade.address.ilike(f'%{keyword}%'))

    # ── 預算篩選（前端輸入萬元，資料庫存元）───
    if min_total_price is not None:
        query = query.filter(Trade.total_price >= int(min_total_price * 10000))
    if max_total_price is not None:
        query = query.filter(Trade.total_price <= int(max_total_price * 10000))
    # 單價：前端輸入萬/坪，DB unit_price_tping 是元/坪 → 需乘 10000
    if min_unit_price is not None:
        query = query.filter(Trade.unit_price_tping >= min_unit_price * 10000)
    if max_unit_price is not None:
        query = query.filter(Trade.unit_price_tping <= max_unit_price * 10000)

    # ── 面積篩選（前端輸入坪，資料庫存平方公尺）───
    if min_area_tping is not None:
        query = query.filter(Trade.building_area >= min_area_tping * 3.3058)
    if max_area_tping is not None:
        query = query.filter(Trade.building_area <= max_area_tping * 3.3058)

    # ── 屋齡篩選 ──
    if min_age is not None or max_age is not None:
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

    # ── 房屋條件 ──
    if building_type:
        # 前端傳簡短名稱（住宅大樓/華廈大樓/公寓/別墅/集合住宅），DB 存完整名稱 → 用 LIKE
        query = query.filter(Trade.building_type.ilike(f'%{building_type}%'))
    if min_rooms is not None:
        query = query.filter(Trade.rooms >= min_rooms)
    if min_living_rooms is not None:
        query = query.filter(Trade.living_rooms >= min_living_rooms)
    if min_bathrooms is not None:
        query = query.filter(Trade.bathrooms >= min_bathrooms)
    if has_elevator is not None:
        query = query.filter(Trade.has_elevator == has_elevator)

    # ── 生活機能評分篩選 ──
    if min_score_overall is not None:
        query = query.filter(Trade.score_overall >= min_score_overall)
    if min_score_transit is not None:
        query = query.filter(Trade.score_transit >= min_score_transit)
    if min_score_education is not None:
        query = query.filter(Trade.score_education >= min_score_education)
    if min_score_medical is not None:
        query = query.filter(Trade.score_medical >= min_score_medical)
    if min_score_shopping is not None:
        query = query.filter(Trade.score_shopping >= min_score_shopping)
    if min_score_leisure is not None:
        query = query.filter(Trade.score_leisure >= min_score_leisure)
    if min_score_dining is not None:
        query = query.filter(Trade.score_dining >= min_score_dining)

    # ── 排序欄位對照 ──
    valid_sorts = {
        'trade_date': Trade.trade_date,
        'total_price': Trade.total_price,
        'unit_price': Trade.unit_price,
        'building_area': Trade.building_area,
        'building_age': Trade.build_complete_date,
        'score_overall': Trade.score_overall,
    }
    sort_col = valid_sorts.get(sort_by, Trade.trade_date)

    # ── 建構排序表達式（NULLS LAST 避免空值排最前）───
    from sqlalchemy import nullslast
    if sort_order == 'desc':
        order_expr = nullslast(sort_col.desc())
    else:
        order_expr = nullslast(sort_col.asc())

    # ── 快速總數（用 SQL COUNT）───
    total = query.count() or 0

    if total == 0:
        return {
            "items": [],
            "page": page,
            "page_size": page_size,
            "total": 0,
            "total_pages": 0,
            "stats": {},
        }

    # ── 通勤篩選（需要計算距離 — 只在有座標時才做）───
    if commute_city and max_commute_time is not None:
        offices = OFFICE_LOCATIONS.get(commute_city, [])
        if offices:
            # 通勤篩選需要載入有座標的記錄到記憶體
            offset = (page - 1) * page_size
            candidate_trades = query.filter(Trade.lat.isnot(None), Trade.lon.isnot(None))\
                .order_by(order_expr)\
                .limit(page_size * 5).offset(offset).all()

            filtered = []
            for t in candidate_trades:
                min_dist = min(
                    haversine_km(t.lat, t.lon, o['lat'], o['lon'])
                    for o in offices
                )
                commute_min = int(min_dist / 30 * 60)
                if commute_min <= max_commute_time:
                    t._commute_time = commute_min
                    t._commute_dist = round(min_dist, 1)
                    filtered.append(t)

            # 通勤模式下 total 不精確（因為需要逐一計算），用近似值
            total = len(filtered)
            page_trades = filtered[:page_size]
        else:
            page_trades = []
    else:
        # ── 標準分頁：SQL ORDER BY + LIMIT/OFFSET（不用載入全部到記憶體）───
        offset = (page - 1) * page_size
        page_trades = query.order_by(
            order_expr
        ).limit(page_size).offset(offset).all()

    total_pages = (total + page_size - 1) // page_size if total > 0 else 0

    # ── 批次載入 POI 明細（避免 N+1）──
    amenity_map = {}
    if page_trades:
        trade_ids = [t.id for t in page_trades]
        amenities = db.query(TradeAmenity).filter(TradeAmenity.trade_id.in_(trade_ids)).all()
        for am in amenities:
            if am.trade_id not in amenity_map:
                amenity_map[am.trade_id] = []
            amenity_map[am.trade_id].append({
                "category": am.category,
                "name": am.amenity_name,
                "distance": am.distance,
            })

    items = []
    for t in page_trades:
        item = {
            "id": t.id,
            "city": t.city,
            "district": t.district,
            "address": t.address,
            "lat": t.lat,
            "lon": t.lon,
            "trade_date": t.trade_date.isoformat() if t.trade_date else None,
            "total_price": t.total_price,
            "total_price_wan": round(t.total_price / 10000) if t.total_price else None,
            "unit_price": normalize_unit_price(t.unit_price),
            "unit_price_tping": normalize_unit_price(t.unit_price_tping),
            "building_area": t.building_area,
            "building_area_tping": round(t.building_area / 3.3058, 1) if t.building_area else None,
            "land_area": t.land_area,
            "main_building_area": t.main_building_area,
            "building_age": compute_building_age(t.build_complete_date),
            "build_complete_date": t.build_complete_date,
            "rooms": t.rooms,
            "living_rooms": t.living_rooms,
            "bathrooms": t.bathrooms,
            "building_type": t.building_type,
            "floor": t.floor,
            "total_floors": t.total_floors,
            "has_elevator": t.has_elevator,
            "is_land_only": (t.building_type == '其他') and (not t.building_area or t.building_area == 0),
            "score_overall": t.score_overall,
            "score_transit": t.score_transit,
            "score_education": t.score_education,
            "score_medical": t.score_medical,
            "score_shopping": t.score_shopping,
            "score_leisure": t.score_leisure,
            "score_dining": t.score_dining,
        }
        # 通勤資訊
        if hasattr(t, '_commute_time'):
            item["commute_time"] = t._commute_time
            item["commute_dist"] = t._commute_dist
        # POI 明細
        item["amenities"] = amenity_map.get(t.id, [])
        items.append(item)

    # ── 統計摘要 ──
    stats = {}
    if items:
        prices = [i['total_price_wan'] for i in items if i['total_price_wan']]
        unit_prices = [i['unit_price_tping'] for i in items if i['unit_price_tping']]
        areas = [i['building_area_tping'] for i in items if i['building_area_tping']]
        ages = [i['building_age'] for i in items if i['building_age'] is not None]
        scores = [i['score_overall'] for i in items if i['score_overall'] is not None]

        stats = {
            "avg_total_price_wan": round(sum(prices) / len(prices)) if prices else None,
            "median_total_price_wan": sorted(prices)[len(prices)//2] if prices else None,
            "avg_unit_price_tping": round(sum(unit_prices) / len(unit_prices), 1) if unit_prices else None,
            "avg_area_tping": round(sum(areas) / len(areas), 1) if areas else None,
            "avg_building_age": round(sum(ages) / len(ages), 1) if ages else None,
            "avg_score": round(sum(scores) / len(scores), 1) if scores else None,
            "price_range": [min(prices), max(prices)] if prices else None,
        }

    result = {
        "items": items,
        "page": page,
        "page_size": page_size,
        "total": total,
        "total_pages": total_pages,
        "stats": stats,
    }

    # ── Cache the result (3 min TTL) ──
    api_cache.set(cache_key, result, ttl=180)

    return result


@router.get("/find/map-points")
def find_map_points(
    # ── Bounding box ──
    min_lat: float = Query(..., description="最小緯度"),
    max_lat: float = Query(..., description="最大緯度"),
    min_lon: float = Query(..., description="最小經度"),
    max_lon: float = Query(..., description="最大經度"),

    # ── Zoom level (controls density) ──
    zoom: int = Query(6, ge=0, le=18, description="地圖縮放等級"),

    # ── 地區篩選 ──
    city: Optional[str] = Query(None),
    district: Optional[str] = Query(None),

    # ── 預算篩選 ──
    min_total_price: Optional[float] = Query(None, ge=0),
    max_total_price: Optional[float] = Query(None, ge=0),
    min_unit_price: Optional[float] = Query(None, ge=0),
    max_unit_price: Optional[float] = Query(None, ge=0),

    # ── 房屋條件 ──
    min_area_tping: Optional[float] = Query(None, ge=0),
    max_area_tping: Optional[float] = Query(None, ge=0),
    building_type: Optional[str] = Query(None),
    has_elevator: Optional[bool] = Query(None),

    # ── 著色模式 ──
    color_mode: str = Query("score", pattern="^(score|price)$", description="著色模式"),

    db: Session = Depends(get_db),
):
    """
    地圖點位 API — 根據視窗範圍和縮放等級回傳適量點位
    
    Zoom < 9: 最多 500 筆（熱力圖密度）
    Zoom 9-11: 最多 2000 筆（聚類標記）
    Zoom > 11: 最多 5000 筆（個別標記）
    """
    # 根據 zoom 決定最大回傳數量
    if zoom < 9:
        max_results = 500
    elif zoom < 12:
        max_results = 2000
    else:
        max_results = 5000

    query = db.query(Trade)

    # Bounding box 篩選
    query = query.filter(
        Trade.lat >= min_lat,
        Trade.lat <= max_lat,
        Trade.lon >= min_lon,
        Trade.lon <= max_lon,
        Trade.lat.isnot(None),
        Trade.lon.isnot(None)
    )

    # 地區篩選
    if city:
        query = query.filter(Trade.city == city)
    if district:
        query = query.filter(Trade.district == district)

    # 預算篩選
    if min_total_price is not None:
        query = query.filter(Trade.total_price >= int(min_total_price * 10000))
    if max_total_price is not None:
        query = query.filter(Trade.total_price <= int(max_total_price * 10000))
    if min_unit_price is not None:
        query = query.filter(Trade.unit_price >= min_unit_price)
    if max_unit_price is not None:
        query = query.filter(Trade.unit_price <= max_unit_price)

    # 面積篩選
    if min_area_tping is not None:
        query = query.filter(Trade.building_area >= min_area_tping * 3.3058)
    if max_area_tping is not None:
        query = query.filter(Trade.building_area <= max_area_tping * 3.3058)

    if building_type:
        query = query.filter(Trade.building_type == building_type)
    if has_elevator is not None:
        query = query.filter(Trade.has_elevator == has_elevator)

    # 隨機取樣（避免每次都回傳同樣的點）
    query = query.order_by(text("RANDOM()")).limit(max_results)

    trades = query.all()

    points = []
    for t in trades:
        # 計算顏色
        if color_mode == "price":
            price = t.total_price or 0
            unit_price = price / 10000
            if unit_price > 200:
                color = "#dc2626"
            elif unit_price > 150:
                color = "#f97316"
            elif unit_price > 100:
                color = "#eab308"
            elif unit_price > 50:
                color = "#22c55e"
            else:
                color = "#3b82f6"
        else:  # score
            score = t.score_overall or 0
            if score >= 80:
                color = "#22c55e"
            elif score >= 60:
                color = "#3b82f6"
            elif score >= 40:
                color = "#eab308"
            else:
                color = "#ef4444"

        points.append({
            "id": t.id,
            "lat": t.lat,
            "lon": t.lon,
            "color": color,
            # 基本 Popup 資訊
            "address": t.address,
            "city": t.city,
            "district": t.district,
            "total_price_wan": round(t.total_price / 10000) if t.total_price else None,
            "unit_price_tping": normalize_unit_price(t.unit_price_tping),
            "score_overall": t.score_overall,
            # 完整交易紀錄（供詳細資訊彈窗使用）
            "trade_date": t.trade_date.isoformat() if t.trade_date else None,
            "building_type": t.building_type,
            "building_age": compute_building_age(t.build_complete_date),
            "building_area": t.building_area,
            "land_area": t.land_area,
            "main_building_area": t.main_building_area,
            "attached_building_area": t.attached_building_area,
            "balcony_area": t.balcony_area,
            "floor": t.floor,
            "total_floors": t.total_floors,
            "rooms": t.rooms,
            "living_rooms": t.living_rooms,
            "bathrooms": t.bathrooms,
            "has_elevator": t.has_elevator,
            "is_land_only": (t.building_type == '其他') and (not t.building_area or t.building_area == 0),
            "total_price": t.total_price,
            "unit_price": t.unit_price,
            "score_food": t.score_dining,
            "score_edu": t.score_education,
            "score_medical": t.score_medical,
            "score_transport": t.score_transit,
            "score_shopping": t.score_shopping,
            "score_recreation": t.score_leisure,
        })

    return {
        "points": points,
        "count": len(points),
        "max_results": max_results,
    }


# 快取篩選選項 — 資料不會頻繁改變，避免每次請求都掃 400 萬筆資料
_FIND_OPTIONS_CACHE = None
_FIND_OPTIONS_CACHE_TIME = 0
_FIND_OPTIONS_CACHE_TTL = 3600  # 1 小時


@router.get("/find/options")
def find_options():
    """取得篩選選項（全部來自記憶體，不查 DB）"""
    global _FIND_OPTIONS_CACHE, _FIND_OPTIONS_CACHE_TIME
    
    now = time.time()
    if _FIND_OPTIONS_CACHE and (now - _FIND_OPTIONS_CACHE_TIME) < _FIND_OPTIONS_CACHE_TTL:
        return _FIND_OPTIONS_CACHE
    
    from app.data.county_districts import get_counties, COUNTY_DISTRICTS
    
    result = {
        "cities": get_counties(),
        "city_districts": COUNTY_DISTRICTS,
        "year_range": {"min_roc": 95, "max_roc": None},
        "price_range": {"min_total": 0, "max_total": 0, "min_unit": 0, "max_unit": 0},
        "building_types": [],
    }
    
    _FIND_OPTIONS_CACHE = result
    _FIND_OPTIONS_CACHE_TIME = now
    return result
