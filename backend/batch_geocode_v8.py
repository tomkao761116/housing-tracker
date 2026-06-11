#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
批次 Geocoding v8 — 韌性版

相比 v7 新增:
- 速率限制：每秒最多 120 次 Photon 請求（保護 Photon 不被打爆）
- Photon 自動重啟：Worker 偵測到 Photon 當機時自動重啟並等待恢復
- 失敗地址重試：批次結束後自動重跑失敗的地址（最多 3 輪）
- Client 自動重建：每 60 秒重建 httpx client 避免 stale connections

Usage:
    /opt/hermes/.venv/bin/python batch_geocode_v8.py
    /opt/hermes/.venv/bin/python batch_geocode_v8.py --test N
    /opt/hermes/.venv/bin/python batch_geocode_v8.py --city 新竹市
"""
import sys
import re
import time
import threading
import queue
import subprocess
from concurrent.futures import ThreadPoolExecutor
import psycopg2
import httpx
import json
import pathlib as p
import diskcache as dc

sys.stdout.reconfigure(line_buffering=True)

from utils.chinese_to_english import normalize_address

DB_URL = "postgresql://hermes@localhost:5432/housing_tracker"
TEST_LIMIT = None
CITY_FILTER = None
for i, arg in enumerate(sys.argv):
    if arg == '--test' and i + 1 < len(sys.argv):
        TEST_LIMIT = int(sys.argv[i + 1])
    if arg == '--city' and i + 1 < len(sys.argv):
        CITY_FILTER = sys.argv[i + 1]

GEO_WORKERS = 12           # 降為 12（配合速率限制）
MAX_REQUESTS_PER_SEC = 120  # Photon 每秒最大請求數
WRITE_BATCH_SIZE = 500
PROGRESS_INTERVAL = 500
TASK_Q_MAX = 1000          # Buffer size between producer and workers
RESULT_Q_MAX = 2000        # Buffer size between workers and writer
MAX_RETRY_ROUNDS = 3       # 失敗地址最多重試輪數

print(f"⚡ v8: {GEO_WORKERS} workers, rate_limit={MAX_REQUESTS_PER_SEC}/s, retries={MAX_RETRY_ROUNDS}")

# ── httpx client factory ──
def make_client():
    return httpx.Client(
        timeout=httpx.Timeout(10.0),
        limits=httpx.Limits(max_connections=5, max_keepalive_connections=2),
    )


# ── 速率限制器 (Token Bucket) ──
class RateLimiter:
    """Token bucket rate limiter — protects Photon from being overwhelmed."""
    def __init__(self, rate_per_sec):
        self.rate = rate_per_sec
        self.tokens = rate_per_sec  # Start full
        self.max_tokens = rate_per_sec
        self.last_refill = time.monotonic()
        self.lock = threading.Lock()

    def acquire(self):
        """Block until a token is available."""
        while True:
            with self.lock:
                now = time.monotonic()
                elapsed = now - self.last_refill
                self.tokens = min(self.max_tokens, self.tokens + elapsed * self.rate)
                self.last_refill = now
                if self.tokens >= 1:
                    self.tokens -= 1
                    return
            time.sleep(1.0 / self.rate)  # Wait before retrying

rate_limiter = RateLimiter(MAX_REQUESTS_PER_SEC)


# ── Photon 健康檢查 + 自動重啟 ──
_photon_healthy = None  # Unknown initially
_photon_lock = threading.Lock()
_photon_restart_lock = threading.Lock()  # Only one thread restarts at a time
MANAGE_PHOTON_SCRIPT = str(p.Path(__file__).parent / "manage_photon.py")

def check_photon_health():
    """快速檢查 Photon 是否存活."""
    try:
        with httpx.Client(timeout=2.0) as c:
            resp = c.get("http://localhost:2322/api?q=test")
            data = resp.json()
            return data.get('type') == 'FeatureCollection'
    except Exception:
        return False

def restart_photon_service():
    """重啟 Photon 服務並等待恢復."""
    print(f"\n  ⚠️  Photon 無回應！嘗試自動重啟...")
    try:
        result = subprocess.run(
            [sys.executable, MANAGE_PHOTON_SCRIPT, 'restart'],
            capture_output=True, text=True, timeout=180
        )
        if result.returncode == 0:
            print(f"  ✅ Photon 已重啟成功")
            return True
        else:
            print(f"  ❌ Photon 重啟失敗: {result.stderr[:200]}")
            return False
    except subprocess.TimeoutExpired:
        print(f"  ❌ Photon 重啟超時")
        return False
    except Exception as e:
        print(f"  ❌ Photon 重啟錯誤: {e}")
        return False

def photon_or_wait():
    """檢查 Photon 健康狀態，若當機則自動重啟並等待恢復."""
    global _photon_healthy
    if _photon_healthy is None or not _photon_healthy:
        if check_photon_health():
            _photon_healthy = True
            return True
        # 真的當機了，嘗試重啟（只有一個 thread 執行）
        with _photon_restart_lock:
            if check_photon_health():
                _photon_healthy = True
                return True
            if not restart_photon_service():
                return False
        # 等待 Photon 恢復
        for attempt in range(60):  # 最多等 60 秒
            time.sleep(1)
            if check_photon_health():
                _photon_healthy = True
                print(f"  ✅ Photon 已恢復！")
                return True
        print(f"  ❌ Photon 60 秒內未恢復")
        _photon_healthy = False
        return False
    return True


# ── Client 自動重建 ──
_client_last_rebuild = {}
_client_lock = threading.Lock()

def get_fresh_client(thread_name):
    """每 60 秒重建一次 httpx client，避免 stale connections."""
    now = time.time()
    with _client_lock:
        last = _client_last_rebuild.get(thread_name, 0)
        if now - last <= 60:
            return None
        _client_last_rebuild[thread_name] = now
    return make_client()

# ── twaddr road map + city-level bbox ──
# City-level bounding boxes (min_lon,min_lat,max_lon,max_lat)
# Covers entire county/city — used to disambiguate same-named roads across cities
CITY_BBOX = {
    '臺北市':   '121.42,24.90,121.65,25.20',
    '新北市':   '121.15,24.85,121.60,25.15',
    '基隆市':   '121.65,25.05,121.85,25.25',
    '宜蘭縣':   '121.45,24.60,122.00,24.90',
    '桃園市':   '121.00,24.85,121.45,25.10',
    '新竹縣':   '120.80,24.70,121.15,24.95',
    '新竹市':   '120.90,24.75,121.05,24.88',
    '苗栗縣':   '120.65,24.40,120.95,24.80',
    '臺中市':   '120.45,23.90,121.15,24.35',
    '彰化縣':   '120.40,23.90,120.65,24.20',
    '南投縣':   '120.50,23.60,121.15,24.15',
    '雲林縣':   '120.30,23.55,120.60,23.90',
    '嘉義縣':   '120.05,23.25,120.60,23.75',
    '嘉義市':   '120.38,23.40,120.55,23.55',
    '澎湖縣':   '119.20,23.20,120.10,23.80',
    '臺南市':   '119.95,22.80,120.65,23.35',
    '高雄市':   '120.05,22.35,120.70,23.10',
    '屏東縣':   '120.25,22.25,121.00,22.80',
    '花蓮縣':   '121.25,23.50,121.85,24.30',
    '臺東縣':   '120.60,22.00,121.60,23.60',
    '連江縣':   '119.85,25.90,120.20,26.40',
}

# District-level bboxes for finer precision (Taipei + New Taipei districts)
DISTRICT_BBOX = {
    '北投': ('121.48,25.12,121.54,25.17'), '士林': ('121.51,25.07,121.56,25.10'),
    '大同': ('121.50,25.05,121.53,25.08'), '中山': ('121.51,25.05,121.53,25.08'),
    '松山': ('121.53,25.04,121.57,25.07'), '信義': ('121.54,25.02,121.59,25.06'),
    '大安': ('121.52,25.01,121.56,25.05'), '萬華': ('121.49,25.02,121.52,25.05'),
    '中正': ('121.50,25.02,121.53,25.05'), '南港': ('121.57,25.04,121.62,25.08'),
    '內湖': ('121.56,25.05,121.62,25.11'), '文山': ('121.54,24.98,121.60,25.04'),
    '永和': ('121.48,24.98,121.54,25.03'), '中和': ('121.48,24.97,121.53,25.02'),
    '板橋': ('121.44,24.97,121.50,25.03'), '新莊': ('121.43,25.03,121.48,25.08'),
    '三重': ('121.44,25.03,121.48,25.08'), '樹林': ('121.38,24.93,121.43,24.98'),
    '土城': ('121.42,24.93,121.47,24.98'), '鶯歌': ('121.35,24.93,121.40,24.97'),
    '三峽': ('121.30,24.90,121.36,24.95'), '淡水': ('121.40,25.15,121.45,25.20'),
    '蘆洲': ('121.40,25.08,121.45,25.13'), '汐止': ('121.57,25.02,121.63,25.08'),
    '新店': ('121.50,24.93,121.57,24.98'),
}

# Old name → new name mapping for city extraction
OLD_CITY_MAP = {
    '臺北縣': '新北市', '臺中縣': '臺中市', '臺南縣': '臺南市', '高雄縣': '高雄市',
    '臺灣省': '', '台北縣': '新北市', '台中縣': '臺中市', '台南縣': '臺南市', '高雄縣': '高雄市',
}

def _normalize_city_name(city):
    """Normalize city name to standard form"""
    if not city:
        return ""
    for old, new in OLD_CITY_MAP.items():
        city = city.replace(old, new)
    # Handle common variants
    city_map = {
        '台北市': '臺北市', '台中市': '臺中市', '台南市': '臺南市',
        '台中巿': '臺中市', '高雄巿': '高雄市',
    }
    for old, new in city_map.items():
        city = city.replace(old, new)
    return city.strip()

def _load_road_map():
    dataset_path = p.Path(__file__).parent / "utils" / "twaddr_dataset.json"
    try:
        with open(dataset_path) as f:
            return json.load(f).get('roadTrie', {})
    except FileNotFoundError:
        return {}

ROAD_MAP = _load_road_map()

def _extract_city_from_addr(addr):
    """Extract city name from address string — handles both traditional and simplified variants"""
    # Normalize first: convert common simplified to traditional
    norm = addr
    for old, new in OLD_CITY_MAP.items():
        norm = norm.replace(old, new)
    for old, new in {'台北市': '臺北市', '台中市': '臺中市', '台南市': '臺南市', 
                      '台中巿': '臺中市', '高雄巿': '高雄市'}.items():
        norm = norm.replace(old, new)
    
    cities = [
        "臺北市", "新北市", "桃園市", "新竹市", "苗栗縣", "臺中市", "彰化縣",
        "南投縣", "雲林縣", "嘉義市", "嘉義縣", "澎湖縣", "臺南市", "高雄市",
        "屏東縣", "宜蘭縣", "花蓮縣", "臺東縣", "金門縣", "連江縣", "基隆市"
    ]
    for c in cities:
        if c in norm:
            return c
    return ""

def _is_coord_in_bbox(lat, lon, bbox_str):
    """Check if (lat, lon) falls within a bbox string 'min_lon,min_lat,max_lon,max_lat'"""
    if not bbox_str:
        return True  # No bbox constraint
    try:
        min_lon, min_lat, max_lon, max_lat = [float(x) for x in bbox_str.split(',')]
        return min_lon <= lon <= max_lon and min_lat <= lat <= max_lat
    except (ValueError, TypeError):
        return True

def _get_bbox(city, district):
    """Get best bbox: district-level first, fallback to city-level"""
    # Strip "區" suffix for DISTRICT_BBOX lookup
    dist_key = district.replace('區', '').strip() if district else ""
    if dist_key and dist_key in DISTRICT_BBOX:
        return DISTRICT_BBOX[dist_key]
    norm_city = _normalize_city_name(city)
    if norm_city and norm_city in CITY_BBOX:
        return CITY_BBOX[norm_city]
    return None

def _city_matches_result(result_city, target_city):
    """Check if Photon result's city matches our target city (flexible matching)"""
    if not result_city or not target_city:
        return True
    norm_target = _normalize_city_name(target_city)
    # Direct match
    if result_city == norm_target:
        return True
    # Partial match (e.g., "新北市" contains "永和")
    if norm_target in result_city or result_city in norm_target:
        return True
    # Common abbreviations
    city_aliases = {
        '臺北市': ['台北市', '台北'], '新北市': ['新北'],
        '臺中市': ['台中市', '台中'], '臺南市': ['台南市', '台南'],
        '高雄市': ['高雄市', '高雄'], '桃園市': ['桃園'],
        '新竹縣': ['竹北', '新竹縣'], '新竹市': ['新竹市'],
    }
    for canonical, aliases in city_aliases.items():
        if norm_target == canonical:
            for alias in aliases:
                if alias in result_city:
                    return True
        if result_city == canonical or result_city in aliases:
            if norm_target == canonical:
                return True
    return False

def _extract_query(addr, city="", district=""):
    """Extract query string for Photon — returns (pure_road_name, road_part_for_check)."""
    # Strip region prefix (everything up to and including 縣市區鄉鎮)
    after_region = re.sub(r'.*[縣市區鄉鎮]', '', addr)
    # Strip 里 and its name (e.g., "三仙里" -> "")
    after_region = re.sub(r'.*?里', '', after_region)
    
    # ── Clean before extracting road name ──
    no = after_region
    
    # Strip 之X號 FIRST (before general digit stripping, needs digits present)
    no = re.sub(r'[\d０-９]+之[\d０-９]+[號棟]?', '', no)
    no = re.sub(r'之[\d０-９]+[號棟]?', '', no)
    no = re.sub(r'之$', '', no)
    
    # Strip building numbers: must have at least one suffix char (號/棟/層/樓/室/甲/乙/丙/丁)
    # Do NOT strip bare digits — they may be part of 巷/弄 numbers
    no = re.sub(r'[\d０-９]+[號棟層樓室甲乙丙丁]+', '', no)
    
    # Strip 地下X層/樓/室
    no = re.sub(r'地下[\d０-９一二三四五六七八九十室層樓]+', '', no)
    
    # Strip multi-address markers: 及, 、, 等共有, 等公共設施
    no = re.sub(r'[、,].*', '', no)  # Everything after first 、 or ,
    no = re.sub(r'.*及.*$', lambda m: m.group(0).split('及')[0], no)  # Take part before 及
    no = re.sub(r'等共有.*$', '', no)
    no = re.sub(r'等公共設施.*$', '', no)
    no = re.sub(r'\(.*?\)', '', no)  # Remove parentheses content
    
    # Strip remaining floor/building info (digits + 樓/層/F)
    no = re.sub(r'[\d０-９]+\s*[樓層Ff].*$', '', no)
    
    # Strip 底二層, 地下室 etc.
    no = re.sub(r'底[\d０-９一二三四五六七八九十]*[層樓].*$', '', no)
    
    # Restore Chinese section numbers (normalize_address converts 五->5, but Photon needs 五段)
    digit_map = {
        '0': '零', '1': '一', '2': '二', '3': '三', '4': '四',
        '5': '五', '6': '六', '7': '七', '8': '八', '9': '九',
        '10': '十', '11': '十一', '12': '十二', '13': '十三',
        '14': '十四', '15': '十五', '16': '十六', '17': '十七',
        '18': '十八', '19': '十九', '20': '二十',
    }
    def restore_section(m):
        num = m.group(1)
        ch = digit_map.get(num, num)
        return f"{ch}段"
    no = re.sub(r'(\d+)段', restore_section, no)
    
    road_part = no.strip()
    
    # Return pure road name as query — Photon does NOT handle "縣市+區+路名" format
    return road_part, road_part


def query_photon(client, query, bbox=None, target_city="", road_part=""):
    """Query Photon API with optional bbox and city filtering + rate limiting."""
    # 速率限制 — 保護 Photon 不被打爆
    rate_limiter.acquire()
    
    params = {'q': query, 'limit': '5'}
    if bbox:
        params['bbox'] = bbox
    try:
        resp = client.get('http://localhost:2322/api', params=params)
        data = resp.json()
        features = data.get('features', [])
        
        # Use road_part for relevance check (if provided), otherwise use full query
        check_str = road_part if road_part else query
        
        # Filter: prefer results matching target city
        for f in features:
            props = f['properties']
            name = props.get('name', '')
            result_city = props.get('city', '')
            
            # Check name contains query chars (relevance) — use road part only
            if not any(c in name for c in check_str):
                continue
            
            # City match check
            if target_city and not _city_matches_result(result_city, target_city):
                continue
            
            coords = f['geometry']['coordinates']
            return (float(coords[1]), float(coords[0]))
        
        # Fallback: if bbox is set, accept first result (bbox constrains area)
        if features and bbox:
            coords = features[0]['geometry']['coordinates']
            return (float(coords[1]), float(coords[0]))
    except Exception:
        pass
    return None


# ── diskcache ──
geo_cache_store = dc.Cache("/opt/data/home/housing-tracker/backend/.geocode_cache", size_limit=1024**3)

class GeoCache:
    def __init__(self):
        self.lock = threading.Lock()
        self.hits = 0
        self.misses = 0
    
    def get(self, key):
        with self.lock:
            val = geo_cache_store.get(key, default=None)
            if val is not None:
                self.hits += 1
                return val
            self.misses += 1
            return None
    
    def put(self, key, value):
        with self.lock:
            geo_cache_store[key] = value
    
    def stats(self):
        with self.lock:
            total = self.hits + self.misses
            rate = self.hits / total * 100 if total > 0 else 0
            return f"{len(geo_cache_store)} entries, Hit:{self.hits}, Miss:{self.misses}, Rate:{rate:.1f}%"

geo_cache = GeoCache()


def geocode_address(address, city="", district=""):
    cache_key = f"{address}|{city}|{district}"
    cached = geo_cache.get(cache_key)
    if cached is not None:
        return cached
    
    normalized = normalize_address(address)
    clean_addr = re.sub(r'\d+(?:[.-]\d+)?(?:F|樓)', '', normalized)
    clean_addr = re.sub(r'之\d+', '', clean_addr)
    clean_addr = re.sub(r'地下[\d室層樓]+', '', clean_addr)
    clean_addr = re.sub(r'\s+', ' ', clean_addr).strip()
    
    # Ensure city prefix is present
    if not re.search(r'(市|縣)', clean_addr) and city:
        clean_addr = f"{normalize_address(city)}{district if district else ''}{clean_addr}"
    
    normalized = normalize_address(clean_addr)
    
    # Get best bbox (district > city level)
    bbox = _get_bbox(city or _extract_city_from_addr(normalized), district)
    
    client = getattr(threading.current_thread(), '_client', None)
    if client is None:
        client = make_client()
        threading.current_thread()._client = client
    
    norm_city = _normalize_city_name(city or _extract_city_from_addr(normalized))
    
    # Extract query: returns (full_query_with_city_district, road_part_only)
    query_result = _extract_query(normalized, norm_city, district)
    if isinstance(query_result, tuple):
        query_str, road_part = query_result
    else:
        query_str = query_result
        road_part = ""
    
    # ── Strategy 1: Chinese query + bbox (fastest & most accurate) ──
    if query_str:
        result = query_photon(client, query_str, bbox=bbox, target_city=norm_city, road_part=road_part)
        if result:
            if _is_coord_in_bbox(result[0], result[1], CITY_BBOX.get(norm_city)):
                geo_cache.put(cache_key, result)
                return result
        # Fallback: if district bbox was used and failed, retry with city-only bbox
        dist_key = district.replace('區', '').strip() if district else ""
        if dist_key and dist_key in DISTRICT_BBOX:
            city_bbox = CITY_BBOX.get(norm_city)
            if city_bbox and city_bbox != bbox:
                result = query_photon(client, query_str, bbox=city_bbox, target_city=norm_city, road_part=road_part)
                if result:
                    if _is_coord_in_bbox(result[0], result[1], CITY_BBOX.get(norm_city)):
                        geo_cache.put(cache_key, result)
                        return result
    
    city_bbox_str = CITY_BBOX.get(norm_city)
    
    # ── Strategy 2: English via ROAD_MAP + bbox ──
    eng = ROAD_MAP.get(road_part or query_str)
    if eng:
        result = query_photon(client, eng, bbox=bbox, target_city=norm_city)
        if result and _is_coord_in_bbox(result[0], result[1], city_bbox_str):
            geo_cache.put(cache_key, result)
            return result
    
    # ── Strategy 3: chinese_to_english full conversion + bbox ──
    try:
        from utils.chinese_to_english import chinese_to_english
        eng_full = chinese_to_english(normalized)
        if eng_full and eng_full != normalized:
            result = query_photon(client, eng_full, bbox=bbox, target_city=norm_city)
            if result and _is_coord_in_bbox(result[0], result[1], city_bbox_str):
                geo_cache.put(cache_key, result)
                return result
    except Exception:
        pass
    
    # ── Strategy 4: Full address without bbox (last resort) ──
    result = query_photon(client, normalized, target_city=norm_city)
    # Even last resort must be within city bbox — reject drifted coords
    if result and not _is_coord_in_bbox(result[0], result[1], city_bbox_str):
        result = None
    geo_cache.put(cache_key, result)
    return result

_SENTINEL = object()

def geocode_worker(task_q, result_q, shared, print_lock):
    local_client = make_client()
    threading.current_thread()._client = local_client
    
    local_success = 0
    local_failed = 0
    local_bbox_rejected = 0
    local_total = 0
    last_photon_check = time.time()
    thread_name = threading.current_thread().name
    
    while True:
        item = task_q.get()
        if item is _SENTINEL:
            break
        
        # 每 30 秒檢查一次 Photon 健康狀態（自動重啟）
        now = time.time()
        if now - last_photon_check > 30:
            photon_or_wait()
            last_photon_check = now
        
        # 每 60 秒重建 client 避免 stale connections
        new_client = get_fresh_client(thread_name)
        if new_client is not None:
            local_client.close()
            local_client = new_client
            threading.current_thread()._client = local_client
        
        idx, city, district, address = item
        try:
            result = geocode_address(address, city, district)
        except Exception:
            result = None
        
        local_total += 1
        if result:
            # Verify coord is in city bbox (double-check at worker level)
            norm_c = _normalize_city_name(city or _extract_city_from_addr(address))
            c_bbox = CITY_BBOX.get(norm_c)
            if c_bbox and not _is_coord_in_bbox(result[0], result[1], c_bbox):
                local_bbox_rejected += 1
                result = None  # Reject drifted coord
            else:
                local_success += 1
                result_q.put((city, district, address, result[0], result[1]))
        else:
            local_failed += 1
        
        if local_total % PROGRESS_INTERVAL == 0:
            with print_lock:
                elapsed = time.time() - shared['start']
                print(f"  📊 Worker {threading.current_thread().name}: "
                      f"{local_total} proc, {local_success}✓ {local_failed}✗ {local_bbox_rejected}⚠️ | "
                      f"{local_total/elapsed:.1f} req/s")
            local_success = 0
            local_failed = 0
            local_bbox_rejected = 0
            local_total = 0
        
        task_q.task_done()
    
    if local_total > 0:
        with print_lock:
            print(f"  📊 Worker {threading.current_thread().name} done: "
                  f"{local_total} total, {local_success}✓ {local_failed}✗ {local_bbox_rejected}⚠️")
    # Accumulate bbox rejected count in shared
    if local_bbox_rejected > 0:
        with shared.get('lock', threading.Lock()):
            shared['bbox_rejected'] = shared.get('bbox_rejected', 0) + local_bbox_rejected
    
    local_client.close()

def writer_thread(result_q, write_conn, shared, start_time):
    cur = write_conn.cursor()
    cur.execute("SET synchronous_commit = OFF")
    write_conn.commit()
    
    batch = []
    total_updated = 0
    batch_num = 0
    last_flush = time.time()
    
    while True:
        item = result_q.get()
        if item is _SENTINEL:
            if batch:
                rows = _flush(cur, write_conn, batch)
                total_updated += rows
                batch_num += 1
            break
        
        batch.append(item)
        now = time.time()
        if len(batch) >= WRITE_BATCH_SIZE or (now - last_flush > 2 and batch):
            rows = _flush(cur, write_conn, batch)
            total_updated += rows
            batch_num += 1
            last_flush = now
            batch = []
        
        result_q.task_done()
    
    cur.close()
    print(f"\n💾 Writer done: {batch_num} batches, {total_updated:,} rows updated")
    return total_updated

def _flush(cur, conn, batch):
    if not batch:
        return 0
    placeholders = ", ".join(["(%s, %s, %s, %s, %s)"] * len(batch))
    flat = []
    for u_city, u_district, u_addr, u_lat, u_lon in batch:
        flat.extend([u_lat, u_lon, u_addr, u_city, u_district])
    
    sql = f"""
        WITH new_coords AS (
            SELECT * FROM (VALUES {placeholders}) 
            AS t(lat, lon, address, city, district)
        )
        UPDATE trades t SET lat = nc.lat, lon = nc.lon
        FROM new_coords nc
        WHERE t.address = nc.address
        AND t.city = nc.city
        AND t.district = nc.district
        AND (t.lat IS NULL OR t.lon IS NULL)
    """
    cur.execute(sql, flat)
    rows = cur.rowcount
    conn.commit()
    return rows

def producer_thread(db_conn, task_q, shared, print_lock):
    """Feed addresses from DB into task queue — Python-side dedup"""
    # Force index scan — PostgreSQL picks seq scan by default (stale stats)
    db_conn.cursor().execute("SET enable_seqscan = OFF")
    db_conn.commit()
    
    cur = db_conn.cursor('geo_stream')
    cur.itersize = 2000
    
    # DISTINCT at DB level — each unique address geocoded ONCE,
    # then UPDATE propagates to all trades sharing that address
    query = """
        SELECT DISTINCT t.city, t.district, t.address
        FROM trades t
        WHERE (t.lat IS NULL OR t.lon IS NULL)
        AND t.address IS NOT NULL
        AND LENGTH(t.address) >= 5
        AND t.address NOT LIKE '%%地號%%'
        AND t.address NOT LIKE '%%建號%%'
        AND TRIM(t.address) NOT LIKE '地下%%'
        AND TRIM(t.address) NOT LIKE '%%地下[室層樓]'
        AND TRIM(t.address) NOT LIKE '%%地下一%'
        AND t.address NOT LIKE '%%公共設施%%'
        AND t.address NOT LIKE '%%共同使用%%'
        AND t.address NOT LIKE '%%號至%%'
        AND t.address NOT LIKE '%%工業區'
        AND t.address NOT LIKE '%%里 '
    """
    
    params = []
    if CITY_FILTER:
        # Use literal in query (safe — CITY_FILTER comes from fixed whitelist)
        query += f" AND t.city = '{CITY_FILTER}'"
    if TEST_LIMIT:
        query += f" LIMIT {TEST_LIMIT}"
    
    cur.execute(query)
    
    fed = 0
    last_progress = time.time()
    
    while True:
        batch = cur.fetchmany(2000)  # Must match itersize
        if not batch:
            break
        
        for city, district, address in batch:
            fed += 1
            try:
                task_q.put((fed, city, district, address), block=False)
            except queue.Full:
                time.sleep(0.01)
                task_q.put((fed, city, district, address))
        
        now = time.time()
        if now - last_progress > 10:
            elapsed = now - shared['start']
            speed = fed / elapsed if elapsed > 0 else 0
            q_size = task_q.qsize()
            with print_lock:
                print(f"\r  🔄 Producer: {fed:,} unique fed | {speed:.0f} addr/s | Q: {q_size}", end='', flush=True)
            last_progress = now
    
    print()
    cur.close()
    shared['total_unique'] = fed
    shared['producer_done'] = True
    return fed

def main():
    print("=" * 60)
    print("批次 Geocoding v8 — 韌性版")
    print(f"  速率限制: {MAX_REQUESTS_PER_SEC} req/s | Worker: {GEO_WORKERS}")
    print(f"  Photon 自動重啟: ON | 失敗重試: {MAX_RETRY_ROUNDS} 輪")
    print("=" * 60)
    if CITY_FILTER:
        print(f"📍 縣市篩選: {CITY_FILTER}")
    if TEST_LIMIT:
        print(f"🧪 TEST: 前 {TEST_LIMIT} 筆")
    print()
    
    start_time = time.time()
    shared = {'start': start_time, 'producer_done': False, 'total_unique': 0, 'bbox_rejected': 0}
    print_lock = threading.Lock()
    
    # ── 主循環：最多 MAX_RETRY_ROUNDS 輪（每輪只跑還有 NULL 的地址） ──
    for round_num in range(1, MAX_RETRY_ROUNDS + 1):
        # 檢查還有沒有要跑的地址
        check_conn = psycopg2.connect(DB_URL)
        check_cur = check_conn.cursor()
        check_query = """
            SELECT COUNT(*) FROM trades t
            WHERE (t.lat IS NULL OR t.lon IS NULL)
            AND t.address IS NOT NULL AND LENGTH(t.address) >= 5
            AND t.address NOT LIKE '%%地號%%' AND t.address NOT LIKE '%%建號%%'
            AND TRIM(t.address) NOT LIKE '地下%%'
            AND t.address NOT LIKE '%%公共設施%%' AND t.address NOT LIKE '%%共同使用%%'
            AND t.address NOT LIKE '%%號至%%' AND t.address NOT LIKE '%%工業區'
            AND t.address NOT LIKE '%%里 '
        """
        if CITY_FILTER:
            check_query += f" AND t.city = '{CITY_FILTER}'"
        check_cur.execute(check_query)
        remaining = check_cur.fetchone()[0]
        check_cur.close(); check_conn.close()
        
        if remaining == 0:
            break
        
        if round_num > 1:
            print(f"\n{'='*60}")
            print(f"🔄 第 {round_num} 輪重試 — 剩餘 {remaining:,} 個未解析地址")
            print(f"{'='*60}\n")
        
        task_q = queue.Queue(maxsize=TASK_Q_MAX)
        result_q = queue.Queue(maxsize=RESULT_Q_MAX)
        
        # Start writer
        write_conn = psycopg2.connect(DB_URL)
        write_conn.autocommit = False
        writer_t = threading.Thread(target=writer_thread, args=(result_q, write_conn, shared, start_time), daemon=True)
        writer_t.start()
        
        # Start geocoding workers
        workers = []
        for i in range(GEO_WORKERS):
            t = threading.Thread(target=geocode_worker, args=(task_q, result_q, shared, print_lock), daemon=True)
            t.start()
            workers.append(t)
        
        # Start producer (feeds from DB)
        db_conn = psycopg2.connect(DB_URL)
        db_conn.autocommit = False
        producer_t = threading.Thread(target=producer_thread, args=(db_conn, task_q, shared, print_lock), daemon=True)
        producer_t.start()
        
        # Wait for producer to finish
        producer_t.join()
        total_unique = shared['total_unique']
        print(f"\n✅ Producer done: {total_unique:,} unique addresses fed")
        
        # Wait for all tasks to be processed by workers
        task_q.join()
        
        # Signal workers
        for _ in range(GEO_WORKERS):
            task_q.put(_SENTINEL)
        for t in workers:
            t.join()
        
        # Signal writer
        result_q.put(_SENTINEL)
        writer_t.join()
        
        db_conn.close(); write_conn.close()
    
    total_time = time.time() - start_time
    
    print()
    print("=" * 60)
    print(f"Done in {total_time/60:.1f} min ({total_time/3600:.1f} hr)")
    print(f"{geo_cache.stats()}")
    print("=" * 60)
    
    # Final stats
    final_conn = psycopg2.connect(DB_URL)
    final_cur = final_conn.cursor()
    final_cur.execute("SELECT COUNT(*) FROM trades WHERE lat IS NOT NULL AND lon IS NOT NULL")
    total_geocoded = final_cur.fetchone()[0]
    final_cur.execute("SELECT COUNT(*) FROM trades WHERE (lat IS NULL OR lon IS NULL) AND address IS NOT NULL AND LENGTH(address) >= 5")
    still_null = final_cur.fetchone()[0]
    final_cur.close(); final_conn.close()
    
    print(f"\n📊 最終統計:")
    print(f"  ✅ 已解析: {total_geocoded:,}")
    print(f"  ❌ 仍為 NULL: {still_null:,}")
    print(f"  📈 成功率: {(total_geocoded/(total_geocoded+still_null)*100) if (total_geocoded+still_null) > 0 else 0:.1f}%")
    
    print("\n✅ Complete!")

if __name__ == "__main__":
    main()
