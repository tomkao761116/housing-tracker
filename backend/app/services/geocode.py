"""
Geocoding service — hybrid approach:
1. Query local trades table (fuzzy address match)
2. Self-hosted Photon API (fast, Taiwan-optimized)
"""
import logging
from typing import Optional, Tuple

import urllib.request
import urllib.parse
import json

logger = logging.getLogger(__name__)

PHOTON_BASE = "http://127.0.0.1:2322"

# ─── Nominatim fallback (used by amenities service) ──────────────
NOMINATIM_BASE = "https://nominatim.openstreetmap.org"
MAX_RETRIES = 3
BACKOFF_MULTIPLIER = 2
JITTER_RANGE = (0.1, 0.5)
GLOBAL_REQUEST_COUNT = {"count": 0}
_last_request_time = None
_rate_limit_interval = 1.0  # Nominatim requires >=1s between requests
import time as _time_module

def _enforce_rate_limit():
    """Enforce Nominatim's 1-request-per-second policy."""
    global _last_request_time
    if _last_request_time is not None:
        elapsed = _time_module.time() - _last_request_time
        wait = _rate_limit_interval - elapsed
        if wait > 0:
            _time_module.sleep(wait)
    _last_request_time = _time_module.time()



def normalize_address(address: str) -> str:
    """正規化地址：全形→半形、統一繁簡體。"""
    # 全形數字 → 半形
    fullwidth_digits = '０１２３４５６７８９'
    halfwidth_digits = '0123456789'
    table = str.maketrans(fullwidth_digits, halfwidth_digits)
    return address.translate(table)


def _geocode_from_trades(address: str) -> Optional[Tuple[float, float]]:
    """從本地 trades 表查找最相似地址的座標。
    
    策略：
    1. 先提取 city/district 關鍵字做精確篩選
    2. 再用 address LIKE 模糊比對（兩邊都 translate 全形→半形）
    3. 取最近的一筆（若有重複則取最新成交）
    """
    try:
        from app.main import engine
        from sqlalchemy import text
        
        # 清理並正規化地址字串
        clean = normalize_address(address.strip())
        
        # 提取城市/區關鍵字
        city_keywords = []
        district_keywords = []
        
        # 常見縣市（同時支援簡體/繁體變體）
        city_list = [
            ('台北市', '臺北市'), ('新北市', '新北市'), ('桃園市', '桃園市'),
            ('台中市', '臺中市'), ('台南市', '臺南市'), ('高雄市', '高雄市'),
            ('基隆市', '基隆市'), ('新竹市', '新竹市'), ('嘉義市', '嘉義市'),
            ('新竹縣', '新竹縣'), ('苗栗縣', '苗栗縣'), ('彰化縣', '彰化縣'),
            ('南投縣', '南投縣'), ('雲林縣', '雲林縣'), ('嘉義縣', '嘉義縣'),
            ('屏東縣', '屏東縣'), ('宜蘭縣', '宜蘭縣'), ('花蓮縣', '花蓮縣'),
            ('台東縣', '臺東縣'), ('澎湖縣', '澎湖縣'),
        ]
        for simp, trad in city_list:
            if simp in clean or trad in clean:
                city_keywords.append(simp)
                city_keywords.append(trad)
        
        # 嘗試從地址中提取區名（通常在縣市後、路名前的部分）
        import re
        stripped = clean
        for ck in city_keywords:
            stripped = stripped.replace(ck, '', 1)
        district_match = re.search(r'([\u4e00-\u9fff]{1,5}[區鄉鎮市])', stripped)
        if district_match:
            district_keywords.append(district_match.group(1))
        
        # 移除區名後再提取路名
        stripped_no_district = re.sub(r'[\u4e00-\u9fff]{1,5}[區鄉鎮市]', '', stripped)
        
        with engine.connect() as conn:
            # Phase 1: 如果有 city/district，先用它們縮小範圍（用 IN 走索引）
            if city_keywords or district_keywords:
                conditions = []
                params = {}
                
                if city_keywords:
                    placeholders = ','.join([f':city_{i}' for i in range(len(city_keywords))])
                    conditions.append(f"city IN ({placeholders})")
                    for i, c in enumerate(city_keywords):
                        params[f"city_{i}"] = c
                
                if district_keywords:
                    placeholders = ','.join([f':dist_{i}' for i in range(len(district_keywords))])
                    conditions.append(f"district IN ({placeholders})")
                    for i, d in enumerate(district_keywords):
                        params[f"dist_{i}"] = d
                
                base_filter = ' AND '.join(conditions) if conditions else '1=1'
                
                # Phase 2: 在縮小範圍後做 address LIKE 模糊比對
                fragments = []
                road_match = re.search(r'([\u4e00-\u9fff]{1,6}[街路大道])', stripped_no_district)
                if road_match:
                    fragments.append(road_match.group(1))
                
                number_match = re.search(r'(\d+)號', clean)
                if number_match:
                    fragments.append(number_match.group(1))
                
                if fragments:
                    like_conditions = ' OR '.join([f"address LIKE :frag_{i}" for i in range(len(fragments))])
                    query = f"""
                        SELECT lat, lon, address, trade_date
                        FROM trades
                        WHERE {base_filter}
                          AND lat IS NOT NULL AND lon IS NOT NULL
                          AND ({like_conditions})
                        ORDER BY trade_date DESC
                        LIMIT 10
                    """
                    for i, f in enumerate(fragments):
                        params[f"frag_{i}"] = f"%{f}%"
                else:
                    query = f"""
                        SELECT lat, lon, address, trade_date
                        FROM trades
                        WHERE {base_filter}
                          AND lat IS NOT NULL AND lon IS NOT NULL
                        ORDER BY trade_date DESC
                        LIMIT 10
                    """
            else:
                # 沒有 city/district，直接模糊搜尋
                fragments = []
                road_match = re.search(r'([\u4e00-\u9fff]{2,8}[街路大道])', clean)
                if road_match:
                    fragments.append(road_match.group(1))
                
                number_match = re.search(r'(\d+)號', clean)
                if number_match:
                    fragments.append(number_match.group(1))
                
                if fragments:
                    like_conditions = ' OR '.join([f"address LIKE :frag_{i}" for i in range(len(fragments))])
                    query = f"""
                        SELECT lat, lon, address, trade_date
                        FROM trades
                        WHERE lat IS NOT NULL AND lon IS NOT NULL
                          AND ({like_conditions})
                        ORDER BY trade_date DESC
                        LIMIT 10
                    """
                    for i, f in enumerate(fragments):
                        params[f"frag_{i}"] = f"%{f}%"
                else:
                    logger.warning(f"No searchable keywords in address: '{clean}'")
                    return None
            
            result = conn.execute(text(query), params)
            rows = result.fetchall()
            
            if not rows:
                logger.info(f"No local match for: '{clean}'")
                return None
            
            # 如果有超過一筆，取經緯度中位數（更準確）
            lats = [r[0] for r in rows if r[0] is not None]
            lons = [r[1] for r in rows if r[1] is not None]
            
            if lats and lons:
                lats.sort()
                lons.sort()
                mid = len(lats) // 2
                avg_lat = lats[mid] if len(lats) % 2 == 1 else (lats[mid-1] + lats[mid]) / 2
                avg_lon = lons[mid] if len(lons) % 2 == 1 else (lons[mid-1] + lons[mid]) / 2
                
                logger.info(f"Local geocode match ({len(rows)} results): '{clean}' → ({avg_lat:.5f}, {avg_lon:.5f})")
                return (float(avg_lat), float(avg_lon))
            
            return None
            
    except Exception as e:
        logger.warning(f"Local geocode lookup failed: {e}")
        return None


def _geocode_from_photon(address: str) -> Optional[Tuple[float, float]]:
    """從自架 Photon API 查找座標。"""
    try:
        url = (
            f"{PHOTON_BASE}/api/"
            f"?q={urllib.parse.quote(address)}"
            f"&limit=5"
        )
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            features = data.get("features", [])
            if features:
                geom = features[0].get("geometry", {})
                coords = geom.get("coordinates", [])
                props = features[0].get("properties", {})
                if len(coords) >= 2:
                    lon, lat = coords[0], coords[1]
                    logger.info(
                        f"Photon result: '{address}' → ({lat:.5f}, {lon:.5f}) "
                        f"[{props.get('name', '')} {props.get('street', '')}]"
                    )
                    return (float(lat), float(lon))
        logger.info(f"No Photon result for: '{address}'")
        return None
    except Exception as e:
        logger.warning(f"Photon geocode failed: {e}")
        return None


def strip_house_number(address: str) -> str:
    """Remove house number suffix from address for better geocoding.
    
    Photon can't resolve to doorplate level, so we strip numbers after 號/之/巷等.
    Examples:
      '台北市文山區景興路87號' -> '台北市文山區景興路'
      '台中市西區精誠路237號' -> '台中市西區精誠路'
    """
    import re
    cleaned = re.sub(r'\s*\d+\s*號\s*$', '', address)
    cleaned = re.sub(r'\s*之\s*\d+\s*(號)?\s*$', '', cleaned)
    cleaned = re.sub(r'\s*\d+\s*$', '', cleaned)
    return cleaned.strip()


def extract_road_name(address: str) -> str:
    """Extract just the road name from address for Photon geocoding.
    
    Photon's Taiwan data only has bare road names (e.g., '景興路'), not full
    city/district+road combos. So we extract just the road part.
    """
    import re
    cleaned = strip_house_number(address)
    
    # Find road suffix position from the end
    road_suffixes = ['大道', '街', '路', '巷']
    for suffix in road_suffixes:
        idx = cleaned.rfind(suffix)
        if idx != -1:
            before = cleaned[:idx]
            # Split by district markers and take the last part (road name)
            parts = re.split(r'[市區縣]', before)
            road_part = parts[-1].strip() if parts else ''
            if not road_part:
                chars_match = re.search(r'([\u4e00-\u9fff]{2,6})$', before)
                road_part = chars_match.group(1) if chars_match else ''
            road = road_part + suffix
            # Check for X段 after
            after_idx = idx + len(suffix)
            after = cleaned[after_idx:]
            segment_match = re.match(r'([\u4e00-\u9fff]*段)', after)
            if segment_match:
                road += segment_match.group(1)
            return road
    
    return cleaned


def geocode_address(address: str) -> Optional[Tuple[float, float]]:
    """Geocode a Taiwan address → (lat, lon).
    
    Priority:
    1. Local trades table (fast, accurate for Taiwan)
    2. Self-hosted Photon API (strips house number first since Photon can't resolve to doorplate)
    3. Photon with extracted road name only (fallback - Photon's Taiwan data only has bare road names)
    """
    # Step 1: Try local trades table first
    local_result = _geocode_from_trades(address)
    if local_result:
        return local_result
    
    # Step 2: Strip house number and query Photon
    clean_address = strip_house_number(address)
    if clean_address != address:
        logger.info(f"Stripped house number: '{address}' -> '{clean_address}'")
    
    photon_result = _geocode_from_photon(clean_address)
    if photon_result:
        return photon_result
    
    # Step 3: Extract road name only and query Photon
    # Photon's Taiwan data only has bare road names like '景興路', not '台北市文山區景興路'
    road_name = extract_road_name(address)
    if road_name != clean_address:
        logger.info(f"Extracted road name: '{address}' -> '{road_name}'")
        photon_result = _geocode_from_photon(road_name)
        if photon_result:
            return photon_result
    
    logger.warning(f"No geocode result for: '{address}'")
    return None


def reverse_geocode(lat: float, lon: float) -> Optional[str]:
    """Reverse geocode coordinates → address string via Photon."""
    url = (
        f"{PHOTON_BASE}/reverse/?lat={lat}&lon={lon}"
    )
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            props = data.get("properties", {})
            parts = []
            for key in ("housenumber", "street", "locality", "district", "city", "country"):
                val = props.get(key)
                if val:
                    parts.append(val)
            return "".join(parts) if parts else ""
    except Exception as e:
        logger.warning(f"Reverse geocode failed: {e}")
        return None


def batch_geocode_trades(db_session, limit: int = 500) -> dict:
    """Batch geocode trades that lack coordinates using local+Photon."""
    from sqlalchemy import text
    
    if limit > 0:
        query_sql = """
        SELECT id, city, district, address 
        FROM trades 
        WHERE lat IS NULL OR lon IS NULL 
        ORDER BY id 
        LIMIT :limit
    """
        trades = db_session.execute(text(query_sql), {"limit": limit}).fetchall()
    else:
        query_sql = """
        SELECT id, city, district, address 
        FROM trades 
        WHERE lat IS NULL OR lon IS NULL 
        ORDER BY id
    """
        trades = db_session.execute(text(query_sql)).fetchall()
    
    success = 0
    failed = 0
    
    for i, t in enumerate(trades):
        try:
            coords = geocode_address(t.address)
            if coords:
                db_session.execute(text("""
                    UPDATE trades SET lat = :lat, lon = :lon WHERE id = :id
                """), {"lat": coords[0], "lon": coords[1], "id": t.id})
                success += 1
                if (i + 1) % 10 == 0:
                    db_session.commit()
                    logger.info(f"[Geocode] {i+1}/{len(trades)} done, success={success}")
            else:
                failed += 1
        except Exception as e:
            failed += 1
            logger.warning(f"[Geocode] Failed for trade {t.id}: {e}")
    
    db_session.commit()
    logger.info(f"[Geocode] Complete: success={success}, failed={failed}")
    return {"success": success, "failed": failed}


def batch_score_trades(db_session, limit: int = 0) -> dict:
    """Batch compute scorecard for trades that have coordinates but no scores.
    
    Args:
        db_session: SQLAlchemy session
        limit: Max trades to score (0 = all)
    
    Returns:
        {"success": int, "failed": int}
    """
    from datetime import datetime
    from sqlalchemy import text
    from app.routers.scorecard import compute_scorecard_for_location as get_scores
    
    query = text("""
        SELECT id, city, district, lat, lon 
        FROM trades 
        WHERE lat IS NOT NULL AND lon IS NOT NULL AND (score_overall IS NULL OR score_overall = 0)
        ORDER BY id
    """)
    if limit > 0:
        query = text(str(query).rstrip() + f" LIMIT {limit}")
    
    trades = db_session.execute(query).fetchall()
    
    success = 0
    failed = 0
    
    for i, t in enumerate(trades):
        try:
            scores = get_scores(float(t.lat), float(t.lon))
            db_session.execute(text("""
                UPDATE trades SET
                    score_overall = :overall,
                    score_transit = :transit,
                    score_education = :education,
                    score_medical = :medical,
                    score_shopping = :shopping,
                    score_leisure = :leisure,
                    score_dining = :dining,
                    score_updated_at = NOW()
                WHERE id = :id
            """), {
                "overall": scores["overall"],
                "transit": scores["transit"],
                "education": scores["education"],
                "medical": scores["medical"],
                "shopping": scores["shopping"],
                "leisure": scores["leisure"],
                "dining": scores["dining"],
                "id": t.id,
            })
            success += 1
            if (i + 1) % 10 == 0:
                db_session.commit()
                logger.info(f"[Score] {i+1}/{len(trades)} done, success={success}")
        except Exception as e:
            failed += 1
            logger.warning(f"[Score] Failed for trade {t.id}: {e}")
    
    db_session.commit()
    logger.info(f"[Score] Complete: success={success}, failed={failed}")
    return {"success": success, "failed": failed}
