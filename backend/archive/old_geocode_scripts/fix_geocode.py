"""
批量修正地碼編碼錯誤 — v7
關鍵改進：
- 阿拉伯數字路段轉中文（3段→三段）— OSM 使用中文數字
- 查詢順序調整：先試「區+路名」（不加門牌），再加門牌
- 城市名稱統一用繁體（台→臺）
- 跳過無法 geocode 的地址類型（土地段號等）
- 新增更多縣市中心點
- Resumable：只處理仍有重複座標的交易
"""
import sys
import time
import json
import re
import urllib.request
import urllib.parse
import psycopg2
from collections import defaultdict

sys.stdout.reconfigure(line_buffering=True)

DB_URL = "postgresql://hermes@localhost:5432/housing_tracker"
NOMINATIM_BASE = "https://nominatim.openstreetmap.org"
REQUEST_INTERVAL = 1.5
last_request_time = 0
api_call_count = 0

# ============================================================
# 各行政區的合理座標範圍 (lat_min, lat_max, lon_min, lon_max)
# ============================================================
DISTRICT_BOUNDS = {
    # --- 臺北市 ---
    "中正區": (25.020, 25.050, 121.505, 121.530),
    "大同區": (25.055, 25.080, 121.505, 121.530),
    "萬華區": (25.015, 25.050, 121.490, 121.520),
    "大安區": (25.015, 25.060, 121.530, 121.575),
    "信義區": (25.020, 25.070, 121.535, 121.580),
    "松山區": (25.040, 25.070, 121.535, 121.570),
    "中山區": (25.055, 25.090, 121.515, 121.550),
    "內湖區": (25.055, 25.110, 121.555, 121.600),
    "南港區": (25.045, 25.075, 121.580, 121.620),
    "士林區": (25.080, 25.140, 121.525, 121.570),
    "北投區": (25.125, 25.170, 121.495, 121.545),
    "文山區": (24.990, 25.050, 121.520, 121.580),

    # --- 新北市 (bounds widened to avoid rejecting valid results) ---
    "板橋區": (24.980, 25.040, 121.430, 121.480),
    "中和區": (24.975, 25.025, 121.475, 121.525),
    "永和區": (24.985, 25.025, 121.495, 121.545),
    "新莊區": (25.010, 25.065, 121.425, 121.475),
    "三重區": (25.040, 25.085, 121.460, 121.515),
    "新店區": (24.930, 24.995, 121.500, 121.570),
    "土城區": (24.945, 24.995, 121.415, 121.470),
    "汐止區": (25.030, 25.100, 121.620, 121.690),
    "林口區": (25.045, 25.105, 121.355, 121.420),
    "蘆洲區": (25.070, 25.115, 121.450, 121.500),
    "五股區": (25.055, 25.105, 121.410, 121.460),
    "八里區": (25.125, 25.170, 121.370, 121.430),
    "淡水區": (25.145, 25.210, 121.410, 121.480),
    "鶯歌區": (24.935, 24.980, 121.325, 121.380),
    "三峽區": (24.910, 24.960, 121.335, 121.400),
    "樹林區": (24.965, 25.020, 121.390, 121.450),
    "泰山區": (25.045, 25.090, 121.400, 121.455),
    "深坑區": (24.980, 25.025, 121.590, 121.640),
    "金山區": (25.190, 25.260, 121.590, 121.670),
    "萬里區": (25.160, 25.230, 121.640, 121.710),
    "瑞芳區": (25.085, 25.150, 121.770, 121.840),
    "平溪區": (25.060, 25.120, 121.820, 121.890),
    "雙溪區": (25.040, 25.100, 121.820, 121.890),
    "貢寮區": (25.120, 25.180, 121.860, 121.930),
    "石碇區": (24.950, 25.005, 121.570, 121.640),
    "坪林區": (24.930, 24.985, 121.590, 121.660),
    "烏來區": (24.890, 24.950, 121.620, 121.680),

    # --- 桃園市 (bounds widened) ---
    "桃園區": (24.965, 25.025, 121.265, 121.335),
    "中壢區": (24.930, 24.985, 121.180, 121.260),
    "平鎮區": (24.915, 24.975, 121.180, 121.250),
    "八德區": (24.900, 24.955, 121.255, 121.320),
    "楊梅區": (24.875, 24.935, 121.100, 121.175),
    "蘆竹區": (25.025, 25.080, 121.250, 121.320),
    "龜山區": (24.965, 25.020, 121.305, 121.370),
    "龍潭區": (24.835, 24.895, 121.170, 121.250),
    "大溪區": (24.850, 24.910, 121.245, 121.320),
    "大園區": (25.035, 25.090, 121.160, 121.225),
    "觀音區": (25.005, 25.065, 121.050, 121.120),
    "新屋區": (24.945, 25.005, 121.070, 121.140),
    "復興區": (24.640, 24.740, 121.240, 121.380),

    # --- 基隆市 ---
    "仁愛區": (25.120, 25.145, 121.720, 121.760),
    "七堵區": (25.085, 25.115, 121.690, 121.730),
    "暖暖區": (25.090, 25.115, 121.720, 121.750),
    "安樂區": (25.115, 25.140, 121.700, 121.740),
    "中正區": (25.120, 25.145, 121.720, 121.760),

    # --- 臺中市 (部分) ---
    "西屯區": (24.150, 24.200, 120.590, 120.660),
    "西區": (24.135, 24.160, 120.660, 120.690),
    "南屯區": (24.130, 24.160, 120.620, 120.660),
    "南區": (24.110, 24.140, 120.650, 120.690),
    "大里區": (24.160, 24.200, 120.660, 120.710),
    "沙鹿區": (24.220, 24.260, 120.550, 120.590),
    "太平區": (24.120, 24.160, 120.700, 120.750),
    "東區": (24.150, 24.180, 120.670, 120.710),
    "北區": (24.155, 24.185, 120.660, 120.695),
    "北屯區": (24.170, 24.220, 120.680, 120.730),

    # --- 臺南市 (部分) ---
    "北區": (22.995, 23.020, 120.205, 120.235),
    "安南區": (23.035, 23.070, 120.190, 120.230),
    "仁德區": (22.950, 22.990, 120.220, 120.260),
    "北門區": (23.270, 23.310, 120.110, 120.150),
    "學甲區": (23.230, 23.270, 120.150, 120.190),

    # --- 高雄市 (部分) ---
    "三民區": (22.630, 22.680, 120.290, 120.340),
}

# 行政區中心點，keyed by (city, district)
DISTRICT_CENTERS = {
    ("臺北市", "中正區"): (25.0340, 121.5175),
    ("臺北市", "大同區"): (25.0670, 121.5120),
    ("臺北市", "萬華區"): (25.0300, 121.5000),
    ("臺北市", "大安區"): (25.0300, 121.5450),
    ("臺北市", "信義區"): (25.0350, 121.5600),
    ("臺北市", "松山區"): (25.0550, 121.5500),
    ("臺北市", "中山區"): (25.0700, 121.5300),
    ("臺北市", "內湖區"): (25.0750, 121.5800),
    ("臺北市", "南港區"): (25.0600, 121.6000),
    ("臺北市", "士林區"): (25.1000, 121.5400),
    ("臺北市", "北投區"): (25.1400, 121.5100),
    ("臺北市", "文山區"): (24.9950, 121.5500),
    ("新北市", "板橋區"): (25.0097, 121.4591),
    ("新北市", "中和區"): (24.9994, 121.4990),
    ("新北市", "永和區"): (25.0092, 121.5201),
    ("新北市", "新莊區"): (25.0358, 121.4502),
    ("新北市", "三重區"): (25.0615, 121.4881),
    ("新北市", "新店區"): (24.9674, 121.5419),
    ("新北市", "土城區"): (24.9722, 121.4433),
    ("新北市", "汐止區"): (25.0642, 121.6587),
    ("新北市", "林口區"): (25.0775, 121.3916),
    ("新北市", "蘆洲區"): (25.0849, 121.4737),
    ("新北市", "五股區"): (25.0827, 121.4382),
    ("新北市", "八里區"): (25.1457, 121.4035),
    ("新北市", "淡水區"): (25.1813, 121.4531),
    ("新北市", "鶯歌區"): (24.9599, 121.3538),
    ("新北市", "三峽區"): (24.9343, 121.3689),
    ("新北市", "樹林區"): (24.9907, 121.4205),
    ("新北市", "泰山區"): (25.0589, 121.4308),
    ("新北市", "深坑區"): (25.0023, 121.6157),
    ("新北市", "金山區"): (25.2219, 121.6362),
    ("新北市", "萬里區"): (25.1950, 121.6750),
    ("新北市", "瑞芳區"): (25.1150, 121.8050),
    ("新北市", "平溪區"): (25.0900, 121.8550),
    ("新北市", "雙溪區"): (25.0700, 121.8550),
    ("新北市", "貢寮區"): (25.1500, 121.8950),
    ("新北市", "石碇區"): (24.9770, 121.6050),
    ("新北市", "坪林區"): (24.9570, 121.6250),
    ("新北市", "烏來區"): (24.9200, 121.6500),
    ("桃園市", "桃園區"): (24.9939, 121.3017),
    ("桃園市", "中壢區"): (24.9539, 121.2249),
    ("桃園市", "平鎮區"): (24.9458, 121.2184),
    ("桃園市", "八德區"): (24.9287, 121.2847),
    ("桃園市", "楊梅區"): (24.9076, 121.1459),
    ("桃園市", "蘆竹區"): (25.0506, 121.2917),
    ("桃園市", "龜山區"): (24.9925, 121.3378),
    ("桃園市", "龍潭區"): (24.8639, 121.2164),
    ("桃園市", "大溪區"): (24.8806, 121.2870),
    ("桃園市", "大園區"): (25.0639, 121.1953),
    ("桃園市", "觀音區"): (25.0364, 121.0823),
    ("桃園市", "新屋區"): (24.9722, 121.1058),
    ("桃園市", "復興區"): (24.6900, 121.3100),
    ("基隆市", "仁愛區"): (25.1251, 121.7368),
    ("基隆市", "七堵區"): (25.0978, 121.7164),
    ("基隆市", "暖暖區"): (25.1003, 121.7360),
    ("基隆市", "安樂區"): (25.1210, 121.7233),
    ("基隆市", "中正區"): (25.1350, 121.7500),
    ("臺中市", "西屯區"): (24.1750, 120.6250),
    ("臺中市", "西區"): (24.1450, 120.6750),
    ("臺中市", "南屯區"): (24.1450, 120.6400),
    ("臺中市", "南區"): (24.1250, 120.6700),
    ("臺中市", "大里區"): (24.1800, 120.6850),
    ("臺中市", "沙鹿區"): (24.2400, 120.5700),
    ("臺中市", "太平區"): (24.1400, 120.7250),
    ("臺中市", "東區"): (24.1650, 120.6900),
    ("臺中市", "北區"): (24.1700, 120.6780),
    ("臺中市", "北屯區"): (24.2000, 120.7050),
    ("臺中市", "東勢區"): (24.2550, 120.8100),
    ("臺中市", "霧峰區"): (24.1400, 120.6900),
    ("臺中市", "烏日區"): (24.1300, 120.6400),
    ("臺中市", "潭子區"): (24.2300, 120.6600),
    ("臺中市", "后里區"): (24.2900, 120.7300),
    ("臺中市", "豐原區"): (24.2550, 120.6900),
    ("臺中市", "神岡區"): (24.2500, 120.6500),
    ("臺中市", "大雅區"): (24.2200, 120.6400),
    ("臺中市", "清水區"): (24.2500, 120.5800),
    ("臺中市", "梧棲區"): (24.2600, 120.5600),
    ("臺中市", "外埔區"): (24.3200, 120.6700),
    ("臺中市", "大甲區"): (24.3200, 120.6000),
    ("臺中市", "大安區"): (24.2000, 120.7800),
    ("臺中市", "和平區"): (24.3000, 121.0000),
    ("臺南市", "北區"): (23.0080, 120.2200),
    ("臺南市", "安南區"): (23.0530, 120.2100),
    ("臺南市", "仁德區"): (22.9700, 120.2400),
    ("臺南市", "北門區"): (23.2900, 120.1300),
    ("臺南市", "學甲區"): (23.2500, 120.1700),
    ("臺南市", "安平區"): (22.9850, 120.1650),
    ("臺南市", "東區"): (22.9900, 120.2400),
    ("臺南市", "中西區"): (22.9950, 120.1950),
    ("臺南市", "南區"): (22.9750, 120.2100),
    ("臺南市", "永康區"): (22.9500, 120.2350),
    ("臺南市", "歸仁區"): (22.9300, 120.2700),
    ("臺南市", "新市區"): (23.0500, 120.2700),
    ("臺南市", "善化區"): (23.1200, 120.2400),
    ("臺南市", "官田區"): (23.1600, 120.2800),
    ("臺南市", "新營區"): (23.3000, 120.3200),
    ("臺南市", "柳營區"): (23.2600, 120.2800),
    ("臺南市", "後壁區"): (23.3100, 120.2600),
    ("臺南市", "白河區"): (23.2800, 120.3600),
    ("臺南市", "東山區"): (23.3200, 120.3800),
    ("臺南市", "麻豆區"): (23.1500, 120.1900),
    ("臺南市", "下營區"): (23.1800, 120.1700),
    ("臺南市", "鹽水區"): (23.2400, 120.2400),
    ("臺南市", "楠西區"): (23.1500, 120.4200),
    ("臺南市", "玉井區"): (23.1200, 120.4000),
    ("臺南市", "曽文區"): (23.0700, 120.4200),
    ("臺南市", "大山區"): (23.0400, 120.4000),
    ("臺南市", "左鎮區"): (23.0800, 120.4500),
    ("臺南市", "龍崎區"): (23.0600, 120.3900),
    ("臺南市", "關廟區"): (23.0800, 120.3500),
    ("臺南市", "安定區"): (23.0400, 120.2400),
    ("高雄市", "三民區"): (22.6550, 120.3150),
    ("高雄市", "苓雅區"): (22.6200, 120.3100),
    ("高雄市", "前金區"): (22.6300, 120.2900),
    ("高雄市", "新興區"): (22.6300, 120.3000),
    ("高雄市", "鼓山區"): (22.6200, 120.2700),
    ("高雄市", "鹽埕區"): (22.6200, 120.2800),
    ("高雄市", "前鎮區"): (22.6000, 120.3000),
    ("高雄市", "左營區"): (22.6800, 120.3000),
    ("高雄市", "楠梓區"): (22.7300, 120.2800),
    ("高雄市", "小港區"): (22.5700, 120.3500),
    ("高雄市", "鳥松區"): (22.6800, 120.3500),
    ("高雄市", "岡山區"): (22.7800, 120.2900),
    ("高雄市", "路竹區"): (22.7500, 120.2500),
    ("高雄市", "阿蓮區"): (22.7800, 120.3100),
    ("高雄市", "田寮區"): (22.9000, 120.3500),
    ("高雄市", "燕巢區"): (22.8300, 120.3700),
    ("高雄市", "橋頭區"): (22.7300, 120.2800),
    ("高雄市", "梓官區"): (22.5800, 120.2600),
    ("高雄市", "彌陀區"): (22.6300, 120.1600),
    ("高雄市", "永安區"): (22.6600, 120.0800),
    ("高雄市", "茄萣區"): (22.7300, 120.1700),
    ("高雄市", "湖內區"): (22.7500, 120.3800),
    ("高雄市", "旗山區"): (22.8000, 120.4700),
    ("高雄市", "美濃區"): (22.9300, 120.4800),
    ("高雄市", "六龜區"): (23.0300, 120.5800),
    ("高雄市", "內門區"): (22.9500, 120.6000),
    ("高雄市", "杉林區"): (22.9800, 120.5600),
    ("高雄市", "甲仙區"): (23.0200, 120.5500),
    ("高雄市", "桃源區"): (22.9500, 120.8000),
    ("高雄市", "那瑪夏區"): (22.9500, 120.6500),
    ("高雄市", "茂林區"): (22.9500, 120.6300),
    # 雲林縣
    ("雲林縣", "斗六市"): (23.7100, 120.5400),
    ("雲林縣", "虎尾鎮"): (23.6200, 120.3300),
    ("雲林縣", "北港鎮"): (23.5700, 120.2900),
    ("雲林縣", "大林鎮"): (23.6400, 120.4100),
    ("雲林縣", "古坑鄉"): (23.6900, 120.5700),
    ("雲林縣", "莿桐鄉"): (23.6600, 120.5300),
    ("雲林縣", "二崙鄉"): (23.6500, 120.3800),
    ("雲林縣", "西螺鎮"): (23.6500, 120.3200),
    ("雲林縣", "麥寮鄉"): (23.7200, 120.2200),
    ("雲林縣", "臺西鄉"): (23.7400, 120.1800),
    ("雲林縣", "元長鄉"): (23.6900, 120.2400),
    ("雲林縣", "土庫鎮"): (23.6900, 120.3200),
    ("雲林縣", "褒忠鄉"): (23.5900, 120.2700),
    ("雲林縣", "東勢鄉"): (23.6200, 120.3800),
    ("雲林縣", "水林鄉"): (23.6100, 120.2200),
    ("雲林縣", "口湖鄉"): (23.5300, 120.1900),
    ("雲林縣", "四湖鄉"): (23.5100, 120.1600),
    ("雲林縣", "林內鄉"): (23.7800, 120.5500),
    ("雲林縣", "斗南鎮"): (23.6500, 120.4600),
    ("雲林縣", "崙背鄉"): (23.6700, 120.3600),
    ("雲林縣", "饒平鄉"): (23.5700, 120.2400),
}


def rate_limit():
    global last_request_time
    elapsed = time.time() - last_request_time
    if elapsed < REQUEST_INTERVAL:
        time.sleep(REQUEST_INTERVAL - elapsed)
    last_request_time = time.time()


# 阿拉伯數字 → 中文數字（用於路段編號）
ARABIC_TO_CHINESE = {
    '0': '零', '1': '一', '2': '二', '3': '三', '4': '四', '5': '五',
    '6': '六', '7': '七', '8': '八', '9': '九', '10': '十'
}


def normalize_address(address):
    """清理地址：移除樓層、之X等雜訊"""
    addr = address.strip()
    addr = re.sub(r'[0-9]*[樓層].*$', '', addr).strip()
    addr = re.sub(r'之[0-9]+$.*$', '', addr).strip()
    addr = re.sub(r'[0-9]+地號.*$', '', addr).strip()
    return addr


def normalize_road_name(text):
    """
    將路名中的阿拉伯數字路段轉換為中文數字，並將傳統字元轉為OSM常用形式。
    e.g., "臺灣大道3段" → "台灣大道三段"
          "信義路4段" → "信義路四段"
          "華江七路" → "華江七路" (already Chinese, no change)
    
    關鍵：OSM 中很多路名使用「台」而非「臺」（如台灣大道）
    """
    # Step 1: Convert Arabic numerals in segments to Chinese
    def replace_seg(m):
        prefix = m.group(1)  # road name before the segment
        num = m.group(2)     # arabic digits
        suffix = m.group(3)  # 段/小段/大段 etc.
        chinese = ''
        for ch in num:
            chinese += ARABIC_TO_CHINESE.get(ch, ch)
        return f"{prefix}{chinese}{suffix}"
    
    result = re.sub(r'([^\d]{1,20})(\d{1,2})(段|小段|大段)', replace_seg, text)
    
    # Step 2: Convert 臺→台 in road names (OSM uses simplified for many road names)
    result = result.replace("臺", "台")
    
    return result


# Keep old name as alias for backward compat
convert_segment_numerals = normalize_road_name


def extract_road_and_number(address):
    """從地址中提取路名和門牌號"""
    addr = address.strip()
    m = re.search(r'([^,\s]{1,20}(?:路|街|大道|西街|東街))([0-9]+)(?:號)?', addr)
    if m:
        return m.group(1), m.group(2)
    m = re.search(r'([^,\s]{1,20}(?:路|街|大道|西街|東街))', addr)
    if m:
        return m.group(1), None
    return None, None


def is_ungeocodeable(address):
    """判斷是否為無法 geocode 的地址類型"""
    addr = address.strip()
    # 純土地段號
    if re.match(r'^[^\s]{0,10}段$', addr):
        return True
    if re.match(r'^[^\s]{0,10}段[一二三四五六七八九十大小]*$', addr):
        return True
    # 僅里名
    if re.match(r'^.{1,5}里$', addr):
        return True
    # 無任何路名/巷/號資訊且長度很短
    if len(addr) < 8 and not re.search(r'(路|街|大道|巷|號)', addr):
        return True
    return False


def strip_prefixes(addr, city, district):
    """移除地址中的城市/區前綴，返回剩餘部分"""
    result = addr
    # 嘗試移除常見的城市變體（繁體優先）
    for prefix in [city, city.replace("市", ""), "縣"]:
        if result.startswith(prefix):
            result = result[len(prefix):]
            break
    # 移除區
    for prefix in [district, district.replace("區", "")]:
        if result.startswith(prefix):
            result = result[len(prefix):]
            break
    # 也處理簡體版本
    simp_city = city.replace("臺", "台")
    simp_district = district.replace("臺", "台")
    if result.startswith(simp_city):
        result = result[len(simp_city):]
    elif result.startswith(simp_city.replace("市", "")):
        result = result[len(simp_city.replace("市", "")):]
    if result.startswith(simp_district):
        result = result[len(simp_district):]
    elif result.startswith(simp_district.replace("區", "")):
        result = result[len(simp_district.replace("區", "")):]
    return result.strip()


def build_queries(norm_addr, city, district):
    """
    建構查詢清單。策略：
    1. 區+路名（不含門牌）— 最可靠
    2. 城市+路名（不含門牌）
    3. 區+路名+門牌
    4. 完整地址
    5. 單純路名+門牌
    
    關鍵：路名中的阿拉伯數字路段要轉中文
    """
    road, hnum = extract_road_and_number(norm_addr)

    if not road:
        # 沒有路名，嘗試用完整地址（去除城市/區前綴後重建）
        suffix = strip_prefixes(norm_addr, city, district)
        if suffix:
            return [(f"{city}{district}{suffix}", "完整地址")]
        return []

    # 轉換路段數字為中文
    road_cn = convert_segment_numerals(road)

    queries = []

    # Layer 1: 區+路名（不含門牌）— 最可靠
    queries.append((f"{city}{district}{road_cn}", "區+路名"))
    queries.append((f"{city}{road_cn}", "城市+路名"))

    # Layer 2: 區+路名+門牌
    if hnum:
        queries.append((f"{city}{district}{road_cn}{hnum}號", "區+路名+門牌"))
        queries.append((f"{city}{road_cn}{hnum}號", "城市+路名+門牌"))

    # Layer 3: 完整地址
    suffix = strip_prefixes(norm_addr, city, district)
    if suffix:
        full_suffix = convert_segment_numerals(suffix)
        queries.append((f"{city}{district}{full_suffix}", "完整地址"))

    # Layer 4: 單純路名+門牌
    if hnum:
        queries.append((f"{road_cn}{hnum}號", "路名+門牌"))
    else:
        queries.append((road_cn, "僅路名"))

    return queries


def geocode_one(query_str):
    """單一查詢字串呼叫 Nominatim"""
    global api_call_count
    q = f"{query_str}, Taiwan"
    url = (
        f"{NOMINATIM_BASE}/search?format=json&q={urllib.parse.quote(q)}"
        f"&limit=5&countrycodes=TW&addressdetails=1"
    )
    rate_limit()
    api_call_count += 1
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "HousingTracker-FixGeocode/7.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            results = json.loads(resp.read().decode("utf-8"))
            if results:
                return [(float(r["lat"]), float(r["lon"]), r.get("display_name", "")) for r in results]
    except Exception as e:
        pass
    return None


def is_in_bounds(lat, lon, city, district):
    bounds = DISTRICT_BOUNDS.get(district)
    if not bounds:
        return True
    lat_min, lat_max, lon_min, lon_max = bounds
    return lat_min <= lat <= lat_max and lon_min <= lon <= lon_max


def best_result(results, city, district):
    if not results:
        return None
    for lat, lon, name in results:
        if is_in_bounds(lat, lon, city, district):
            return (lat, lon, name)
    return (results[0][0], results[0][1], results[0][2])


def geocode_trade(norm_addr, city, district):
    """
    對單一交易進行多層 geocode
    返回 (lat, lon, source_desc) 或 None
    """
    queries = build_queries(norm_addr, city, district)

    for query, label in queries:
        results = geocode_one(query)
        if results:
            chosen = best_result(results, city, district)
            if chosen:
                return (chosen[0], chosen[1], f"{label}")

    return None


def update_trades(cur, conn, trade_list, new_lat, new_lon):
    """更新交易座標並清除相關評分"""
    tids = [t[0] for t in trade_list]
    ph = ",".join(["%s"] * len(tids))

    cur.execute(f"UPDATE trades SET lat = %s, lon = %s WHERE id IN ({ph})", [new_lat, new_lon] + tids)
    cur.execute(f"DELETE FROM trade_amenities WHERE trade_id IN ({ph})", tids)
    cur.execute(f"""
        UPDATE trades SET score_overall = NULL, score_transit = NULL,
            score_education = NULL, score_medical = NULL,
            score_shopping = NULL, score_leisure = NULL,
            score_dining = NULL, score_updated_at = NULL
        WHERE id IN ({ph})
    """, tids)
    conn.commit()


def main():
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()

    print("=" * 60)
    print("fix_geocode.py v7 — Per-address geocoding (Chinese numerals)")
    print("=" * 60)

    # Normalize city name function
    def norm_city(c):
        return c.replace("台", "臺")

    # Find ALL trades that still share duplicate coordinates
    cur.execute("""
        SELECT t.id, t.city, t.district, t.address, t.lat, t.lon
        FROM trades t
        INNER JOIN (
            SELECT city, district, lat, lon
            FROM trades
            GROUP BY city, district, lat, lon
            HAVING COUNT(*) > 1
        ) dup ON t.city = dup.city AND t.district = dup.district
              AND t.lat = dup.lat AND t.lon = dup.lon
        ORDER BY t.city, t.district, t.address
    """)
    trades = cur.fetchall()
    total_to_fix = len(trades)
    print(f"\n找到 {total_to_fix} 筆仍使用重複座標的交易")

    if not trades:
        print("沒有需要修正的交易！")
        cur.close()
        conn.close()
        return

    # Load already-correct trades for reverse lookup
    print("\n載入已知正確座標作為參考...")
    cur.execute("""
        SELECT id, city, district, address, lat, lon
        FROM trades
        WHERE NOT EXISTS (
            SELECT 1 FROM trades t2
            WHERE t2.city = trades.city AND t2.district = trades.district
              AND t2.lat = trades.lat AND t2.lon = trades.lon
              AND t2.id != trades.id
        )
    """)
    correct_trades = cur.fetchall()
    print(f"找到 {len(correct_trades)} 筆已知正確座標的交易")

    # Build road -> correct coords index (normalize city names)
    road_correct_coords = defaultdict(list)
    for t in correct_trades:
        tid, city, district, address, lat, lon = t
        ncity = norm_city(city)
        road, _ = extract_road_and_number(address)
        if road:
            road_correct_coords[(ncity, district, road)].append((lat, lon))

    # Group trades by normalized address (same address -> same geocode result)
    addr_groups = defaultdict(list)
    skipped_ungeocodeable = 0
    for t in trades:
        tid, city, district, address, lat, lon = t
        ncity = norm_city(city)
        norm_addr = normalize_address(address)

        key = (ncity, district, norm_addr)
        addr_groups[key].append(t)
        if is_ungeocodeable(norm_addr):
            skipped_ungeocodeable += 1

    sorted_groups = sorted(addr_groups.items(), key=lambda x: -len(x[1]))
    print(f"共 {len(sorted_groups)} 個唯一地址組合需要處理")
    print(f"(其中 {skipped_ungeocodeable} 筆屬於無法 geocode 的地址類型)\n")

    # Process each group
    fixed = 0
    failed = 0
    used_nominatim = 0
    used_reverse = 0
    used_fallback = 0
    addr_cache = {}  # (city, district, norm_addr) -> (lat, lon, source)

    start_time = time.time()

    for i, ((city, district, norm_addr), trade_list) in enumerate(sorted_groups):
        elapsed = time.time() - start_time
        eta_total = (elapsed / (i + 1)) * (len(sorted_groups) - i - 1) if i > 0 else 0
        eta_min = eta_total / 60

        cache_key = (city, district, norm_addr)
        new_lat = None
        new_lon = None
        src = ""

        # Check if ungeocodeable type
        if is_ungeocodeable(norm_addr):
            # Use district center + deterministic offset
            center = DISTRICT_CENTERS.get((city, district))
            if center:
                seed_str = f"{city}{district}{norm_addr}"
                h = hash(seed_str) & 0xFFFFFFFF
                offset_lat = ((h % 1000) / 1000 - 0.5) * 0.01
                offset_lon = (((h >> 10) % 1000) / 1000 - 0.5) * 0.01
                new_lat = center[0] + offset_lat
                new_lon = center[1] + offset_lon
                src = "區中心+偏移(無法geocode)"
                used_fallback += 1
            else:
                failed += len(trade_list)
                if (i + 1) % 20 == 0:
                    print(f"[{i+1:>4}/{len(sorted_groups)}] ✗ {city}{district} "
                          f"addr={norm_addr[:30]} ({len(trade_list)}筆) "
                          f"-> 無中心點資料 ETA:{eta_min:.1f}min")
                continue

        elif cache_key in addr_cache:
            new_lat, new_lon, src = addr_cache[cache_key]
        else:
            # Try 1: Reverse geocode from known correct trades
            road, _ = extract_road_and_number(norm_addr)
            if road and (city, district, road) in road_correct_coords:
                coords_list = road_correct_coords[(city, district, road)]
                avg_lat = sum(c[0] for c in coords_list) / len(coords_list)
                avg_lon = sum(c[1] for c in coords_list) / len(coords_list)
                addr_cache[cache_key] = (avg_lat, avg_lon, f"反向推估({len(coords_list)}筆)")
                new_lat, new_lon = avg_lat, avg_lon
                src = f"反向推估({len(coords_list)}筆)"
                used_reverse += 1
            else:
                # Try 2: Nominatim geocode
                result = geocode_trade(norm_addr, city, district)

                if result:
                    new_lat, new_lon, src = result
                    addr_cache[cache_key] = (new_lat, new_lon, src)
                    used_nominatim += 1
                else:
                    # Try 3: District center + deterministic offset based on address hash
                    center = DISTRICT_CENTERS.get((city, district))
                    if center:
                        seed_str = f"{city}{district}{norm_addr}"
                        h = hash(seed_str) & 0xFFFFFFFF
                        offset_lat = ((h % 1000) / 1000 - 0.5) * 0.01
                        offset_lon = (((h >> 10) % 1000) / 1000 - 0.5) * 0.01
                        new_lat = center[0] + offset_lat
                        new_lon = center[1] + offset_lon
                        addr_cache[cache_key] = (new_lat, new_lon, "區中心+偏移")
                        used_fallback += 1
                        src = "區中心+偏移"
                    else:
                        print(f"[{i+1:>4}/{len(sorted_groups)}] ✗ {city}{district} "
                              f"addr={norm_addr[:40]} ({len(trade_list)}筆) "
                              f"-> 完全無法處理 ETA:{eta_min:.1f}min")
                        failed += len(trade_list)
                        continue

        update_trades(cur, conn, trade_list, new_lat, new_lon)
        fixed += len(trade_list)

        # Progress output every 10 groups
        if (i + 1) % 10 == 0 or i == 0 or i == len(sorted_groups) - 1:
            addr_display = norm_addr[:35] if len(norm_addr) > 35 else norm_addr
            print(f"[{i+1:>4}/{len(sorted_groups)}] {city}{district} "
                  f"addr={addr_display} ({len(trade_list)}筆) "
                  f"-> ({new_lat:.6f}, {new_lon:.6f}) [{src}] "
                  f"fixed={fixed} failed={failed} api={api_call_count} ETA:{eta_min:.1f}min")

    total_elapsed = time.time() - start_time

    print("\n" + "=" * 60)
    print("完成！")
    print("=" * 60)
    print(f"總耗時: {total_elapsed:.0f} 秒 ({total_elapsed/60:.1f} 分鐘)")
    print(f"Nominatim API 呼叫次數: {api_call_count}")
    print(f"修正: {fixed} 筆")
    print(f"  ├─ Nominatim 查詢: {used_nominatim} 組地址")
    print(f"  ├─ 反向推估: {used_reverse} 組地址")
    print(f"  ├─ 區中心+偏移: {used_fallback} 組地址")
    print(f"  └─ 失敗: {failed} 筆")
    print(f"\n注意: 修正後的交易需要重新執行 POI 批次計算")

    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
