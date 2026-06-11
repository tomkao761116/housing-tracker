"""由內而外搜尋 API — Radial Search
以目標行政區為中心，向外分圈層顯示房源
"""
from fastapi import APIRouter, Query, Depends
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from app.utils import compute_building_age
import math

from app.models.database import Trade, TradeAmenity

router = APIRouter()


def get_db():
    from app.main import SessionLocal
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def haversine_km(lat1, lon1, lat2, lon2):
    """Haversine distance in km"""
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2)
    return R * 2 * math.asin(math.sqrt(a))


def normalize_unit_price(val):
    """Convert raw unit_price_tping to 萬/坪 (old data may be in 元/坪)"""
    if val is None:
        return None
    return round(val / 10000, 1) if val > 10000 else round(val, 1)


@router.get("/radial-search")
def radial_search(
    center_city: str = Query(..., description="中心縣市"),
    center_district: str = Query(..., description="中心行政區"),
    max_price: Optional[float] = Query(None, description="最高總價（元）"),
    min_area: Optional[float] = Query(None, description="最小建築面積（㎡）"),
    building_type: Optional[str] = Query(None, description="建物型態"),
    ring_distance_km: float = Query(15.0, description="搜尋半徑（公里）", ge=1, le=100),
    limit_per_ring: int = Query(20, description="每圈最多回傳筆數", ge=1, le=100),
    db: Session = Depends(get_db),
):
    """
    由內而外搜尋：以目標行政區為中心，向外分圈層顯示房源
    Ring 0 = 目標行政區, Ring 1+ = 按距離分層的相鄰區域
    """
    if db is None:
        from app.main import get_db_session
        db = get_db_session()

    # Step 1: Get center district centroid and trades
    center_trades = db.query(Trade).filter(
        Trade.city == center_city,
        Trade.district == center_district,
        Trade.lat.isnot(None),
        Trade.lon.isnot(None)
    ).all()

    if not center_trades:
        return {"error": f"找不到 {center_city}{center_district} 的交易資料"}

    center_lat = sum(t.lat for t in center_trades) / len(center_trades)
    center_lon = sum(t.lon for t in center_trades) / len(center_trades)

    # Step 2: Build filter conditions
    filters = [Trade.lat.isnot(None), Trade.lon.isnot(None)]
    if max_price:
        filters.append(Trade.total_price <= max_price * 10000)  # Convert 萬 to 元
    if min_area:
        filters.append(Trade.building_area >= min_area)
    if building_type:
        filters.append(Trade.building_type == building_type)

    # Step 3: Get all matching trades with their district info
    all_trades = db.query(Trade).filter(and_(*filters)).all()

    # Step 4: Group by city+district and compute distances
    districts = {}
    for trade in all_trades:
        key = (trade.city, trade.district)
        if key not in districts:
            # Compute centroid for this district
            dist_trades = [t for t in all_trades if t.city == trade.city and t.district == trade.district]
            dist_lat = sum(t.lat for t in dist_trades) / len(dist_trades)
            dist_lon = sum(t.lon for t in dist_trades) / len(dist_trades)
            dist_km = haversine_km(center_lat, center_lon, dist_lat, dist_lon)
            districts[key] = {
                "city": trade.city,
                "district": trade.district,
                "centroid_lat": dist_lat,
                "centroid_lon": dist_lon,
                "distance_km": round(dist_km, 1),
                "trades": []
            }
        districts[key]["trades"].append(trade)

    # Step 5: Filter by ring_distance_km and sort by distance
    valid_districts = {k: v for k, v in districts.items() 
                       if v["distance_km"] <= ring_distance_km}
    
    sorted_districts = sorted(valid_districts.values(), key=lambda d: d["distance_km"])

    # Step 6: Assign rings based on distance bands
    # Ring 0 = center district (distance ~0)
    # Ring 1 = 0-5km, Ring 2 = 5-10km, Ring 3 = 10-20km, etc.
    def assign_ring(dist_km):
        if dist_km < 2:
            return 0
        elif dist_km < 5:
            return 1
        elif dist_km < 10:
            return 2
        elif dist_km < 20:
            return 3
        else:
            return 4

    # Compute center district stats
    center_key = (center_city, center_district)
    center_data = districts.get(center_key)
    center_avg_price = 0
    center_avg_area = 0
    if center_data and center_data["trades"]:
        prices = [normalize_unit_price(t.unit_price_tping) for t in center_data["trades"] if t.unit_price_tping]
        areas = [t.building_area for t in center_data["trades"] if t.building_area]
        center_avg_price = sum(prices) / len(prices) if prices else 0
        center_avg_area = sum(areas) / len(areas) if areas else 0

    # Step 7: Build response rings
    rings = []
    for d in sorted_districts:
        ring = assign_ring(d["distance_km"])
        
        # Sort trades by price (cheapest first) and limit
        d["trades"].sort(key=lambda t: normalize_unit_price(t.unit_price_tping) or 999999)
        limited_trades = d["trades"][:limit_per_ring]

        # Compute stats
        prices = [normalize_unit_price(t.unit_price_tping) for t in limited_trades if t.unit_price_tping]
        areas = [t.building_area for t in limited_trades if t.building_area]
        total_prices = [t.total_price for t in limited_trades if t.total_price]
        
        avg_unit_price = sum(prices) / len(prices) if prices else 0
        avg_area = sum(areas) / len(areas) if areas else 0
        avg_total_price = sum(total_prices) / len(total_prices) if total_prices else 0

        # Compute diffs vs center
        price_diff_pct = round((avg_unit_price - center_avg_price) / center_avg_price * 100, 1) if center_avg_price else 0
        area_diff = round(avg_area - center_avg_area, 1) if center_avg_area else 0

        # Compute average life amenity scores for this district
        scored_trades = [t for t in limited_trades if t.score_overall is not None]
        avg_scores = {}
        if scored_trades:
            score_fields = ['score_transit', 'score_education', 'score_medical', 'score_shopping', 'score_leisure', 'score_dining']
            for field in score_fields:
                vals = [getattr(t, field) for t in scored_trades if getattr(t, field) is not None]
                avg_scores[field] = round(sum(vals) / len(vals), 1) if vals else None
            overall_vals = [t.score_overall for t in scored_trades if t.score_overall is not None]
            avg_scores['score_overall'] = round(sum(overall_vals) / len(overall_vals), 1) if overall_vals else None
        else:
            avg_scores = {f'score_{k}': None for k in ['overall', 'transit', 'education', 'medical', 'shopping', 'leisure', 'dining']}

        # Get top POIs for this district (aggregate from all trades)
        trade_ids = [t.id for t in limited_trades]
        top_amenities = {}
        if trade_ids:
            poi_rows = db.query(TradeAmenity).filter(
                TradeAmenity.trade_id.in_(trade_ids)
            ).order_by(TradeAmenity.distance).limit(50).all()
            
            # Group by category and pick nearest ones
            grouped = {}
            for row in poi_rows:
                cat = row.category
                if cat not in grouped or len(grouped[cat]) < 3:
                    grouped.setdefault(cat, []).append({
                        "name": row.amenity_name,
                        "distance": row.distance,
                    })
            top_amenities = grouped

        ring_data = {
            "ring": ring,
            "city": d["city"],
            "district": d["district"],
            "distance_km": d["distance_km"],
            "trade_count": len(limited_trades),
            "avg_unit_price_tping": round(avg_unit_price),
            "avg_building_area": round(avg_area, 1),
            "avg_building_age": round(sum(a for a in [compute_building_age(t.build_complete_date) for t in limited_trades] if a is not None) / max(1, sum(1 for a in [compute_building_age(t.build_complete_date) for t in limited_trades] if a is not None)), 1),
            "avg_total_price": round(avg_total_price / 10000, 1),  # In 萬
            "price_diff_pct": price_diff_pct,
            "area_diff_sqm": area_diff,
            "life_scores": avg_scores,
            "amenities": top_amenities,
            "trades": [
                {
                    "id": t.id,
                    "address": t.address,
                    "unit_price_tping": normalize_unit_price(t.unit_price_tping),
                    "total_price": round(t.total_price / 10000, 1) if t.total_price else None,
                    "building_area": t.building_area,
                    "building_age": compute_building_age(t.build_complete_date),
                    "building_type": t.building_type,
                    "floor": t.floor,
                    "rooms": t.rooms,
                    "living_rooms": t.living_rooms,
                    "bathrooms": t.bathrooms,
                    "trade_date": str(t.trade_date) if t.trade_date else None,
                    "score_overall": t.score_overall,
                    "score_transit": t.score_transit,
                    "score_education": t.score_education,
                    "score_medical": t.score_medical,
                    "score_shopping": t.score_shopping,
                    "score_leisure": t.score_leisure,
                    "score_dining": t.score_dining,
                }
                for t in limited_trades
            ]
        }
        rings.append(ring_data)

    # Step 8: Find best value ring
    best_value_ring = None
    best_value_reason = ""
    if len(rings) > 1:
        # Best value = ring with most negative price_diff and positive area_diff
        outer_rings = [r for r in rings if r["ring"] > 0]
        if outer_rings:
            best = max(outer_rings, key=lambda r: (-r["price_diff_pct"] + max(0, r["area_diff_sqm"]) * 2))
            best_value_ring = best["ring"]
            if best["price_diff_pct"] < 0 and best["area_diff_sqm"] > 0:
                best_value_reason = f"單價便宜 {abs(best['price_diff_pct']):.0f}%，平均大 {best['area_diff_sqm']:.1f} 坪"
            elif best["price_diff_pct"] < 0:
                best_value_reason = f"單價便宜 {abs(best['price_diff_pct']):.0f}%"
            elif best["area_diff_sqm"] > 0:
                best_value_reason = f"平均大 {best['area_diff_sqm']:.1f} 坪"

    return {
        "center": {
            "city": center_city,
            "district": center_district,
            "centroid_lat": round(center_lat, 4),
            "centroid_lon": round(center_lon, 4),
            "avg_unit_price_tping": round(center_avg_price),
            "avg_building_area": round(center_avg_area, 1),
        },
        "rings": rings,
        "summary": {
            "total_rings": len(rings),
            "total_trades": sum(r["trade_count"] for r in rings),
            "search_radius_km": ring_distance_km,
            "best_value_ring": best_value_ring,
            "best_value_district": next((r["district"] for r in rings if r["ring"] == best_value_ring), None),
            "best_value_reason": best_value_reason,
        }
    }
