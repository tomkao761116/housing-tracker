"""
Location POI Lookup — query pre-computed POIs from location_poi table.

Returns nearby POIs per category for a given coordinate.
Uses unique_locations + location_poi for fast lookup.
"""
import logging
from typing import Optional, Dict, Any, List
from fastapi import APIRouter, Query
from sqlalchemy import text

logger = logging.getLogger(__name__)

router = APIRouter()

DB_URL = "postgresql://hermes@localhost:5432/housing_tracker"

DIMENSION_CONFIG = {
    "transit":   {"label": "交通", "icon": "🚇", "color": "#637d56", "radius_m": 1000},
    "education": {"label": "教育", "icon": "🏫", "color": "#475569", "radius_m": 1500},
    "medical":   {"label": "醫療", "icon": "🏥", "color": "#dc2626", "radius_m": 1200},
    "shopping":  {"label": "購物", "icon": "🛒", "color": "#d97706", "radius_m": 800},
    "leisure":   {"label": "休閒", "icon": "🌳", "color": "#556b48", "radius_m": 1000},
    "dining":    {"label": "餐飲", "icon": "🍽️", "color": "#92400e", "radius_m": 600},
}


@router.get("/location-pois")
def get_location_pois(
    lat: float = Query(..., description="Latitude"),
    lon: float = Query(..., description="Longitude"),
):
    """Fetch pre-computed POIs for a location from unique_locations + location_poi."""
    from app.main import engine
    
    try:
        with engine.connect() as conn:
            # Find matching unique location
            loc_result = conn.execute(text("""
                SELECT lon, lat, score_overall,
                       score_transit, score_education, score_medical,
                       score_shopping, score_leisure, score_dining
                FROM unique_locations
                WHERE lon = :lon AND lat = :lat
            """), {"lon": lon, "lat": lat})
            loc_row = loc_result.fetchone()
            
            if not loc_row:
                # Try nearest unique location within 50m
                loc_result = conn.execute(text("""
                    SELECT lon, lat, score_overall,
                           score_transit, score_education, score_medical,
                           score_shopping, score_leisure, score_dining
                    FROM unique_locations
                    ORDER BY point(lon, lat) <-> point(:lon, :lat)
                    LIMIT 1
                """), {"lon": lon, "lat": lat})
                loc_row = loc_result.fetchone()
            
            if not loc_row:
                return {"error": "找不到該位置的生活圈資料"}
            
            scores = {
                "overall": loc_row[2],
                "transit": loc_row[3],
                "education": loc_row[4],
                "medical": loc_row[5],
                "shopping": loc_row[6],
                "leisure": loc_row[7],
                "dining": loc_row[8],
            }
            
            # Fetch POIs per category
            poi_results = {}
            for cat_key in DIMENSION_CONFIG:
                rows = conn.execute(text("""
                    SELECT amenity_name, distance, poi_osm_id
                    FROM location_poi
                    WHERE lon = :lon AND lat = :lat AND category = :cat
                    ORDER BY distance ASC
                """), {"lon": loc_row[0], "lat": loc_row[1], "cat": cat_key}).fetchall()
                
                poi_results[cat_key] = {
                    "label": DIMENSION_CONFIG[cat_key]["label"],
                    "icon": DIMENSION_CONFIG[cat_key]["icon"],
                    "color": DIMENSION_CONFIG[cat_key]["color"],
                    "count": len(rows),
                    "items": [
                        {"name": r[0] or "未命名", "distance": r[1], "osm_id": r[2]}
                        for r in rows
                    ],
                }
            
            return {
                "location": {"lat": loc_row[1], "lon": loc_row[0]},
                "scores": scores,
                "pois": poi_results,
            }
    
    except Exception as e:
        logger.error(f"Location POI lookup failed: {e}", exc_info=True)
        return {"error": f"查詢失敗: {str(e)}"}


@router.get("/location-pois/search")
def search_location_pois(
    lat: float = Query(..., description="Latitude"),
    lon: float = Query(..., description="Longitude"),
    radius: int = Query(1000, ge=100, le=5000, description="Search radius in meters"),
    category: Optional[str] = Query(None, description="Filter by category"),
    limit: int = Query(50, ge=1, le=200, description="Max items per category"),
):
    """Search POIs near any coordinate using PostGIS spatial query on poi_master."""
    from app.main import engine
    
    try:
        with engine.connect() as conn:
            if category and category in DIMENSION_CONFIG:
                categories = [category]
            else:
                categories = list(DIMENSION_CONFIG.keys())
            
            results = {}
            for cat in categories:
                cfg = DIMENSION_CONFIG[cat]
                r = cfg["radius_m"]
                
                rows = conn.execute(text("""
                    SELECT p.name, p.category,
                           ROUND(ST_DistanceSphere(
                               ST_SetSRID(ST_MakePoint(:lon, :lat), 4326),
                               p.geom
                           )::INTEGER) AS distance
                    FROM poi_master p
                    WHERE p.category = :cat
                      AND ST_DWithin(
                          p.geom,
                          ST_SetSRID(ST_MakePoint(:lon, :lat), 4326),
                          :radius
                      )
                    ORDER BY distance ASC
                    LIMIT :limit
                """), {"lon": lon, "lat": lat, "cat": cat, "radius": r, "limit": limit}).fetchall()
                
                results[cat] = {
                    "label": cfg["label"],
                    "icon": cfg["icon"],
                    "color": cfg["color"],
                    "count": len(rows),
                    "items": [
                        {"name": r[0] or "未命名", "distance": r[2]}
                        for r in rows
                    ],
                }
            
            return {
                "location": {"lat": lat, "lon": lon},
                "pois": results,
            }
    
    except Exception as e:
        logger.error(f"POI search failed: {e}", exc_info=True)
        return {"error": f"查詢失敗: {str(e)}"}
