"""
批次 Geocoding + POI 查詢 — 差異更新版本
只處理缺乏資料的紀錄，已完成的跳過不重跑
"""
import time
import json
import urllib.request
import urllib.parse
import sqlite3
from collections import defaultdict

DB_PATH = "/opt/data/home/housing-tracker/backend/data.db"

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# ============================================
# Step 0: 建立 trade_amenities 表（若不存在）
# ============================================
print("=== 建立 trade_amenities 表 ===")
with get_db() as conn:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS trade_amenities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            trade_id INTEGER NOT NULL,
            category TEXT NOT NULL,
            amenity_name TEXT NOT NULL,
            distance INTEGER NOT NULL,
            lat REAL,
            lon REAL,
            UNIQUE(trade_id, category, amenity_name),
            FOREIGN KEY (trade_id) REFERENCES trades(id)
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_trade_amenities_trade_id 
        ON trade_amenities(trade_id)
    """)
    conn.commit()
    print("✓ trade_amenities 表就緒")

# ============================================
# Step 1: 統計目前狀態
# ============================================
print("\n=== 目前資料庫狀態 ===")
with get_db() as conn:
    total = conn.execute("SELECT COUNT(*) FROM trades").fetchone()[0]
    has_coords = conn.execute("SELECT COUNT(*) FROM trades WHERE lat IS NOT NULL AND lon IS NOT NULL").fetchone()[0]
    no_coords = total - has_coords
    
    # 有座標但缺少 POI 的
    trades_with_coords = [r[0] for r in conn.execute("SELECT id FROM trades WHERE lat IS NOT NULL AND lon IS NOT NULL").fetchall()]
    trades_with_poi = set()
    if trades_with_coords:
        placeholders = ",".join(["?"] * len(trades_with_coords))
        poi_result = conn.execute(f"SELECT DISTINCT trade_id FROM trade_amenities WHERE trade_id IN ({placeholders})", trades_with_coords).fetchall()
        trades_with_poi = {r[0] for r in poi_result}
    
    missing_poi = len(trades_with_coords) - len(trades_with_poi)
    
    print(f"總筆數: {total}")
    print(f"已有座標: {has_coords}")
    print(f"缺少座標: {no_coords}")
    print(f"有座標但缺少 POI: {missing_poi}")

# ============================================
# Step 2: 批次 Geocoding（只處理沒座標的）
# ============================================
print("\n=== 批次 Geocoding（差異更新）===")

geo_cache = {}

def geocode_address(city, district):
    """Geocode using city+district."""
    cache_key = f"{city}{district}"
    if cache_key in geo_cache:
        return geo_cache[cache_key]
    
    addr = f"{city}{district}"
    url = f"https://nominatim.openstreetmap.org/search?format=json&q={urllib.parse.quote(addr)}&limit=1&countrycodes=TW"
    req = urllib.request.Request(url, headers={"User-Agent": "HousingTracker/1.0"})
    
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            results = json.loads(resp.read().decode("utf-8"))
            if results:
                lat = float(results[0]["lat"])
                lon = float(results[0]["lon"])
                geo_cache[cache_key] = (lat, lon)
                return (lat, lon)
    except Exception as e:
        print(f"  ✗ '{addr}' 解析失敗: {e}")
    
    return None

# 取得所有沒座標的紀錄
with get_db() as conn:
    no_coord_trades = conn.execute("""
        SELECT id, city, district, address FROM trades 
        WHERE lat IS NULL OR lon IS NULL
    """).fetchall()

print(f"需 Geocoding: {len(no_coord_trades)} 筆")

# 依 city+district 分組（相同位置只需查一次）
location_groups = defaultdict(list)
for trade in no_coord_trades:
    key = (trade["city"], trade["district"])
    location_groups[key].append(trade["id"])

print(f"唯一位置組合: {len(location_groups)} 個")

# 開始 Geocoding
geo_success = 0
geo_failed = 0
updated_ids = []

for i, ((city, district), trade_ids) in enumerate(location_groups.items()):
    print(f"[{i+1}/{len(location_groups)}] {city}{district} ({len(trade_ids)} 筆)", end=" → ")
    
    coords = geocode_address(city, district)
    if coords:
        with get_db() as conn:
            conn.execute(
                "UPDATE trades SET lat = ?, lon = ? WHERE id IN (SELECT id FROM trades WHERE city = ? AND district = ? AND (lat IS NULL OR lon IS NULL))",
                (coords[0], coords[1], city, district)
            )
            conn.commit()
        updated_ids.extend(trade_ids)
        geo_success += len(trade_ids)
        print(f"✓ Lat: {coords[0]:.6f}, Lon: {coords[1]:.6f}")
    else:
        geo_failed += len(trade_ids)
        print("✗ 失敗")
    
    time.sleep(1.2)  # Nominatim rate limit

print(f"\nGeocoding 完成: 成功 {geo_success} 筆, 失敗 {geo_failed} 筆")

# ============================================
# Step 3: 批次 POI 查詢（只處理沒 POI 的）
# ============================================
print("\n=== 批次 POI 查詢（差異更新）===")

CATEGORIES = {
    "school": {"query": "amenity=school", "label": "學校"},
    "transit": {"query": "railway=station", "label": "捷運/火車站"},
    "hospital": {"query": "amenity=hospital", "label": "醫院"},
    "shop": {"query": "shop=supermarket", "label": "超市"},
    "park": {"query": "leisure=park", "label": "公園"},
    "restaurant": {"query": "amenity=restaurant", "label": "餐廳"},
    "pharmacy": {"query": "amenity=pharmacy", "label": "藥局"},
}

def haversine(lat1, lon1, lat2, lon2):
    """計算兩點距離（公尺）"""
    import math
    R = 6371000
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
    return R * 2 * math.asin(math.sqrt(a))

def fetch_poi(lat, lon, category, query):
    """使用 Overpass API 查詢周邊設施"""
    bbox = 0.01  # ~1km radius
    overpass_query = f"""
        [out:json][timeout:10];
        node["{query.split('=')[0]}="{query.split('=')[1]}""](around:500,{lat},{lon});
        out center limit 10;
    """
    url = "https://overpass-api.de/api/interpreter"
    data = urllib.parse.urlencode({"data": overpass_query}).encode()
    req = urllib.request.Request(url, data=data, headers={"User-Agent": "HousingTracker/1.0"})
    
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            elements = result.get("elements", [])
            pois = []
            for elem in elements:
                name = elem.get("tags", {}).get("name", "未知")
                elat = elem.get("lat", lat)
                elon = elem.get("lon", lon)
                dist = int(haversine(lat, lon, elat, elon))
                pois.append({
                    "name": name,
                    "distance": dist,
                    "lat": elat,
                    "lon": elon
                })
            return sorted(pois, key=lambda x: x["distance"])[:5]  # 只留最近 5 個
    except Exception as e:
        print(f"  POI 查詢失敗 ({category}): {e}")
        return []

# 取得有座標但缺少 POI 的紀錄
with get_db() as conn:
    trades_with_coords = conn.execute("""
        SELECT id, lat, lon FROM trades WHERE lat IS NOT NULL AND lon IS NOT NULL
    """).fetchall()
    
    # 排除已有 POI 的
    all_ids = [t["id"] for t in trades_with_coords]
    if all_ids:
        placeholders = ",".join(["?"] * len(all_ids))
        has_poi = {r[0] for r in conn.execute(f"SELECT DISTINCT trade_id FROM trade_amenities WHERE trade_id IN ({placeholders})", all_ids).fetchall()}
        needs_poi = [t for t in trades_with_coords if t["id"] not in has_poi]
    else:
        needs_poi = trades_with_coords

print(f"需查詢 POI: {len(needs_poi)} 筆")

poi_success = 0
poi_failed = 0

for i, trade in enumerate(needs_poi):
    tid = trade["id"]
    lat = trade["lat"]
    lon = trade["lon"]
    
    print(f"[{i+1}/{len(needs_poi)}] Trade #{tid} ({lat:.4f}, {lon:.4f})", end=" → ")
    
    total_pois = 0
    with get_db() as conn:
        for cat, info in CATEGORIES.items():
            pois = fetch_poi(lat, lon, cat, info["query"])
            for poi in pois:
                try:
                    conn.execute(
                        "INSERT OR IGNORE INTO trade_amenities (trade_id, category, amenity_name, distance, lat, lon) VALUES (?, ?, ?, ?, ?, ?)",
                        (tid, cat, poi["name"], poi["distance"], poi["lat"], poi["lon"])
                    )
                    total_pois += 1
                except Exception as e:
                    print(f"  插入失敗: {e}")
            conn.commit()
            time.sleep(0.5)  # Overpass rate limit
    
    if total_pois > 0:
        poi_success += 1
        print(f"✓ {total_pois} 個設施")
    else:
        poi_failed += 1
        print("✗ 無資料")
    
    time.sleep(1.0)  # General rate limit

print(f"\nPOI 查詢完成: 成功 {poi_success} 筆, 失敗 {poi_failed} 筆")

# ============================================
# Step 4: 最終統計
# ============================================
print("\n=== 最終統計 ===")
with get_db() as conn:
    total = conn.execute("SELECT COUNT(*) FROM trades").fetchone()[0]
    has_coords = conn.execute("SELECT COUNT(*) FROM trades WHERE lat IS NOT NULL AND lon IS NOT NULL").fetchone()[0]
    total_pois = conn.execute("SELECT COUNT(DISTINCT trade_id) FROM trade_amenities").fetchone()[0]
    poi_records = conn.execute("SELECT COUNT(*) FROM trade_amenities").fetchone()[0]
    
    print(f"總筆數: {total}")
    print(f"已有座標: {has_coords} ({has_coords/total*100:.1f}%)")
    print(f"已有 POI: {total_pois} 筆 ({poi_records} 條設施紀錄)")
