"""通勤時間熱力圖 API — Commute Time Map
根據距離估算通勤時間（開車 / 大眾運輸），回傳符合條件的房源 + 等時圈半徑
"""
from fastapi import APIRouter, Query, Depends
from app.utils import compute_building_age, normalize_floor_local, normalize_unit_price
from typing import Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import and_
import math
import json

from app.models.database import Trade
from app.main import get_db

router = APIRouter()


def normalize_unit_price(val):
    """Convert raw unit_price_tping to 萬/坪 (old data may be in 元/坪)"""
    if val is None:
        return None
    return round(val / 10000, 1) if val > 10000 else round(val, 1)

# ── 速度常數 (km/h) ──
SPEED_DRIVING_KMH = 30.0       # 開車平均速度
SPEED_TRANSIT_KMH = 20.0       # 大眾運輸平均速度


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Haversine distance in km"""
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2)
    return R * 2 * math.asin(min(1.0, math.sqrt(a)))


def estimate_commute_time_km(max_time_min: float, mode: str = "driving") -> float:
    """根據通勤時間上限與交通模式，計算可達半徑 (km)"""
    speed = SPEED_DRIVING_KMH if mode == "driving" else SPEED_TRANSIT_KMH
    return speed * (max_time_min / 60.0)


@router.get("/time")
def commute_time(
    lat: float = Query(..., description="起點緯度"),
    lon: float = Query(..., description="起點經度"),
    destination: str = Query(..., description="目的地（地址）"),
):
    """
    計算從起點到目的地的通勤時間（使用 OSRM / Nominatim）
    回傳所有交通方式的預估時間
    """
    import urllib.parse
    
    # 速度常數 (km/h) — 用於估算各交通方式時間
    # （定義在下方 modes 列表中）
    
    results = []
    
    # 嘗試用 Nominatim 解析目的地
    dest_name = urllib.parse.quote(destination)
    nominatim_url = f"https://nominatim.openstreetmap.org/search?format=json&q={dest_name}&limit=1"
    
    try:
        import urllib.request
        req = urllib.request.Request(nominatim_url, headers={"User-Agent": "HousingTracker/1.0"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            dest_data = json.loads(resp.read())
        
        if not dest_data or len(dest_data) == 0:
            return {"error": "找不到目的地", "data": []}
        
        dest_lat = float(dest_data[0]["lat"])
        dest_lon = float(dest_data[0]["lon"])
        
        # 計算 Haversine 距離（直線 fallback）
        dist = haversine_km(lat, lon, dest_lat, dest_lon)
        
        # 先用 OSRM driving 取得實際路線距離
        osrm_dist_km = None
        osrm_url = f"http://router.project-osrm.org/route/v1/driving/{lon},{lat};{dest_lon},{dest_lat}?overview=false"
        try:
            req = urllib.request.Request(osrm_url, headers={"User-Agent": "HousingTracker/1.0"})
            with urllib.request.urlopen(req, timeout=5) as resp:
                osrm_data = json.loads(resp.read())
            if osrm_data.get("routes"):
                osrm_dist_km = round(osrm_data["routes"][0]["distance"] / 1000, 2)
        except Exception:
            pass
        
        # 若 OSRM 失敗，用直線距離
        route_dist = osrm_dist_km if osrm_dist_km else round(dist, 2)
        
        # 各交通方式的速度 (km/h) 和對應標籤
        modes = [
            {"mode": "car", "label": "開車", "speed_kmh": 35},
            {"mode": "public", "label": "大眾運輸", "speed_kmh": 22},
            {"mode": "bike", "label": "自行車", "speed_kmh": 15},
            {"mode": "walk", "label": "步行", "speed_kmh": 5},
        ]
        
        for m in modes:
            duration_min = max(1, round(route_dist / m["speed_kmh"] * 60))
            results.append({
                "mode": m["mode"],
                "label": m["label"],
                "destination": destination,
                "distance": route_dist,
                "duration": duration_min,
                "source": "osrm_route" if osrm_dist_km else "estimate",
            })
        
    except Exception as e:
        return {"error": f"無法解析目的地: {str(e)}", "data": []}
    
    return {"data": results}


@router.get("/commute")
def commute_search(
    end_lat: float = Query(..., description="上班地點緯度"),
    end_lon: float = Query(..., description="上班地點經度"),
    max_time_min: float = Query(30, ge=5, le=180, description="最大通勤時間（分鐘）"),
    start_lat: Optional[float] = Query(None, description="住處中心緯度（選填，用於顯示相對位置）"),
    start_lon: Optional[float] = Query(None, description="住處中心經度（選填）"),
    mode: str = Query("driving", regex="^(driving|transit)$", description="交通模式：driving / transit"),
    min_price: Optional[int] = Query(None, ge=0, description="最低總價（元）"),
    max_price: Optional[int] = Query(None, ge=0, description="最高總價（元）"),
    min_area: Optional[float] = Query(None, ge=0, description="最小建築面積（㎡）"),
    max_area: Optional[float] = Query(None, ge=0, description="最大建築面積（㎡）"),
    city: Optional[str] = Query(None, description="縣市篩選"),
    district: Optional[str] = Query(None, description="行政區篩選"),
    building_type: Optional[str] = Query(None, description="建物型態"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """
    通勤時間熱力圖搜尋
    以「上班地點」為中心，找出在指定通勤時間內可到達的所有房源（PostGIS 空間查詢）
    """
    from sqlalchemy import text
    
    # Calculate isochrone radius
    speed = SPEED_DRIVING_KMH if mode == "driving" else SPEED_TRANSIT_KMH
    radius_km = speed * (max_time_min / 60.0)
    
    # Bounding box approach - much faster than PostGIS on this hardware
    deg_lat = radius_km / 111.0
    deg_lon = radius_km / (111.0 * math.cos(math.radians(end_lat)))
    
    # Build WHERE clause with bbox
    where_parts = [
        "lat IS NOT NULL AND lon IS NOT NULL",
        f"lat BETWEEN {end_lat - deg_lat} AND {end_lat + deg_lat}",
        f"lon BETWEEN {end_lon - deg_lon} AND {end_lon + deg_lon}",
    ]
    params: dict = {}
    
    if min_price is not None:
        where_parts.append("total_price >= :min_price")
        params["min_price"] = min_price
    if max_price is not None:
        where_parts.append("total_price <= :max_price")
        params["max_price"] = max_price
    if min_area is not None:
        where_parts.append("building_area >= :min_area")
        params["min_area"] = min_area
    if max_area is not None:
        where_parts.append("building_area <= :max_area")
        params["max_area"] = max_area
    if city:
        where_parts.append("city = :city")
        params["city"] = city
    if district:
        where_parts.append("district = :district")
        params["district"] = district
    if building_type:
        where_parts.append("building_type ILIKE :building_type")
        params["building_type"] = f"%{building_type}%"
    
    where_clause = " AND ".join(where_parts)
    
    # Fetch paginated results - distance computed in Python
    query_sql = text(f'''
        SELECT id, city, district, address, lat, lon,
               trade_date, total_price, unit_price, unit_price_tping,
               building_area, land_area, main_building_area,
               rooms, living_rooms, bathrooms, building_type,
               floor, total_floors, has_elevator, build_complete_date
        FROM trades
        WHERE {where_clause}
        ORDER BY ABS(lat - {end_lat})
        LIMIT :limit OFFSET :offset
    ''')
    params["limit"] = page_size * 3 + 1
    params["offset"] = (page - 1) * page_size
    result = db.execute(query_sql, params)
    rows = result.fetchall()
    
    # Haversine distance calculation (optimized)
    R_EARTH = 6371000.0
    rad_end_lat = math.radians(end_lat)
    cos_rad_end_lat = math.cos(rad_end_lat)
    
    def haversine_dist(rlat, rlon):
        dlat = math.radians(rlat - end_lat)
        dlon = math.radians(rlon - end_lon)
        a = math.sin(dlat/2)**2 + cos_rad_end_lat * math.cos(math.radians(rlat)) * math.sin(dlon/2)**2
        return R_EARTH * 2 * math.asin(min(1.0, math.sqrt(a)))
    
    # Filter by actual radius and sort by distance
    with_distances = []
    for row in rows:
        _d = dict(row._mapping) if hasattr(row, '_mapping') else dict(zip(['id','city','district','address','lat','lon','trade_date','total_price','unit_price','unit_price_tping','building_area','land_area','main_building_area','rooms','living_rooms','bathrooms','building_type','floor','total_floors','has_elevator','build_complete_date'], row))
        rlat = _d.get("lat")
        rlon = _d.get("lon")
        dist_m = round(haversine_dist(rlat, rlon)) if rlat and rlon else None
        if dist_m is not None and dist_m / 1000.0 <= radius_km:
            with_distances.append((_d, dist_m))
    
    # Sort by distance
    with_distances.sort(key=lambda x: x[1])
    
    has_more = len(with_distances) > page_size
    results = []
    for _d, dist_m in with_distances[:page_size]:
        dist_km = dist_m / 1000.0
        commute_min = round(dist_km / speed * 60, 1)
        
        results.append({
            "id": _d["id"],
            "city": _d["city"],
            "district": _d["district"],
            "address": _d["address"],
            "lat": round(_d["lat"], 6) if _d.get("lat") else None,
            "lon": round(_d["lon"], 6) if _d.get("lon") else None,
            "distance_km": round(dist_km, 2),
            "commute_time_min": commute_min,
            "trade_date": _d["trade_date"].isoformat() if _d.get("trade_date") else None,
            "total_price": _d["total_price"],
            "total_price_wan": round(_d["total_price"] / 10000) if _d.get("total_price") else None,
            "unit_price_tping": normalize_unit_price(_d.get("unit_price_tping")),
            "unit_price_wan": round(normalize_unit_price(_d.get("unit_price_tping")) / 1, 2) if _d.get("unit_price_tping") else None,
            "building_area": round(_d["building_area"], 2) if _d.get("building_area") else None,
            "building_area_ping": round(_d["building_area"] / 3.3058, 2) if _d.get("building_area") else None,
            "building_age": compute_building_age(_d.get("build_complete_date")),
            "rooms": _d.get("rooms"),
            "living_rooms": _d.get("living_rooms"),
            "bathrooms": _d.get("bathrooms"),
            "building_type": _d.get("building_type"),
            "floor": normalize_floor_local(_d.get("floor")),
            "has_elevator": _d.get("has_elevator"),
        })
    
    # Calculate summary stats
    prices = [r["total_price"] for r in results if r["total_price"]]
    unit_prices = [r["unit_price_tping"] for r in results if r["unit_price_tping"]]
    distances = [r["distance_km"] for r in results]
    
    avg_total_price = round(sum(prices) / len(prices) / 10000) if prices else 0
    avg_unit_price = round(sum(unit_prices) / len(unit_prices), 2) if unit_prices else 0
    avg_distance = round(sum(distances) / len(distances), 1) if distances else 0
    max_distance = round(max(distances), 1) if distances else 0
    
    return {
        "isochrone": {
            "center_lat": end_lat,
            "center_lon": end_lon,
            "radius_km": round(radius_km, 2),
            "mode": mode,
            "max_time_min": max_time_min,
            "speed_kmh": speed,
        },
        "summary": {
            "total_in_range": len(results),
            "total_available": len(results),
            "has_more": has_more,
            "avg_commute_time_min": round(sum(r["commute_time_min"] for r in results) / len(results), 1) if results else 0,
            "avg_distance_km": avg_distance,
            "max_distance_km": max_distance,
            "avg_total_price_wan": avg_total_price,
            "avg_unit_price_wan_ping": avg_unit_price,
        },
        "page": page,
        "page_size": page_size,
        "data": results,
    }


@router.get("/commute/multi-office")
def multi_office_compare(
    offices: str = Query(..., description="多個上班地點，格式：lat,lon|name,lat,lon|name,..."),
    max_time_min: float = Query(30, ge=5, le=180, description="最大通勤時間（分鐘）"),
    mode: str = Query("driving", regex="^(driving|transit)$", description="交通模式"),
    min_price: Optional[int] = Query(None, ge=0),
    max_price: Optional[int] = Query(None, ge=0),
    city: Optional[str] = Query(None),
    district: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """
    多辦公地點比較模式
    同時比較多個上班地點的等時圈範圍與房源
    """
    # 解析上班地點
    office_list = []
    for part in offices.split(","):
        pass  # handled below

    # 正確解析：lat,lon|name,lat,lon|name
    parts = offices.split("|")
    offices_parsed = []
    i = 0
    while i < len(parts):
        try:
            lat = float(parts[i])
            lon = float(parts[i + 1])
            name = parts[i + 2] if i + 2 < len(parts) else f"地點 {len(offices_parsed) + 1}"
            offices_parsed.append({"lat": lat, "lon": lon, "name": name})
            i += 3
        except (ValueError, IndexError):
            i += 1

    if not offices_parsed:
        return {"error": "無法解析上班地點，請使用格式：lat,lon|name,lat,lon|name"}

    speed = SPEED_DRIVING_KMH if mode == "driving" else SPEED_TRANSIT_KMH
    radius_km = speed * (max_time_min / 60.0)

    # 查詢所有有座標的房源
    filters = [Trade.lat.isnot(None), Trade.lon.isnot(None)]
    if min_price is not None:
        filters.append(Trade.total_price >= min_price)
    if max_price is not None:
        filters.append(Trade.total_price <= max_price)
    if city:
        filters.append(Trade.city == city)
    if district:
        filters.append(Trade.district == district)

    all_trades = db.query(Trade).filter(and_(*filters)).all()

    # 對每個辦公地點計算等時圈內的房源
    comparisons = []
    for office in offices_parsed:
        in_range = []
        for t in all_trades:
            dist = haversine_km(t.lat, t.lon, office["lat"], office["lon"])
            if dist <= radius_km:
                commute_min = round(dist / speed * 60, 1)
                in_range.append({
                    "id": t.id,
                    "city": t.city,
                    "district": t.district,
                    "address": t.address,
                    "lat": round(t.lat, 6),
                    "lon": round(t.lon, 6),
                    "distance_km": round(dist, 2),
                    "commute_time_min": commute_min,
                    "total_price_wan": round(t.total_price / 10000) if t.total_price else None,
                    "unit_price_wan": normalize_unit_price(t.unit_price_tping),
                    "building_area_ping": round(t.building_area / 3.3058, 2) if t.building_area else None,
                    "building_age": compute_building_age(t.build_complete_date),
                })
        in_range.sort(key=lambda x: x["commute_time_min"])

        prices = [r["total_price_wan"] for r in in_range if r["total_price_wan"]]
        unit_prices = [r["unit_price_wan"] for r in in_range if r["unit_price_wan"]]

        comparisons.append({
            "office_name": office["name"],
            "office_lat": office["lat"],
            "office_lon": office["lon"],
            "radius_km": round(radius_km, 2),
            "count_in_range": len(in_range),
            "avg_total_price_wan": round(sum(prices) / len(prices)) if prices else 0,
            "avg_unit_price_wan_ping": round(sum(unit_prices) / len(unit_prices), 2) if unit_prices else 0,
            "trades": in_range[:50],  # 限制回傳數量
        })

    return {
        "mode": mode,
        "max_time_min": max_time_min,
        "comparisons": comparisons,
    }
