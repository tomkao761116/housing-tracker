"""共用工具函式 — 避免各模組重複實作"""
import math
import re
from datetime import date
from typing import Optional


# ── 國字數字轉換 ─────────────────────────────────────────

def chinese_to_arabic(chinese_str: str) -> Optional[int]:
    """
    將中文數字字串轉為阿拉伯數字。
    支援格式：'二十三層', '十五', '四層', '二十九層'
    不支援的格式回傳 None。
    """
    if not chinese_str or not isinstance(chinese_str, str):
        return None
    
    s = chinese_str.strip()
    # 純數字直接回傳
    if s.isdigit():
        return int(s)
    
    # 移除「層」字
    s = s.replace('層', '')
    if s.isdigit():
        return int(s)
    
    # 中文數字映射
    cn_map = {
        '零': 0, '一': 1, '二': 2, '三': 3, '四': 4,
        '五': 5, '六': 6, '七': 7, '八': 8, '九': 9,
        '十': 10, '百': 100, '千': 1000, '萬': 10000
    }
    
    # 檢查是否包含中文數字
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
        return result if result > 0 else None
    except (ValueError, TypeError):
        return None


def normalize_floor_local(floor_val) -> Optional[str]:
    """Standardize floor field."""
    if floor_val is None:
        return None
    s = str(floor_val).strip()
    if not s or s == '全':
        return s if s else None
    parts = re.split(r'[，,、]+', s)
    for part in parts:
        num = chinese_to_arabic(part.strip())
        if num is not None:
            return str(num)
    num = chinese_to_arabic(s)
    return str(num) if num is not None else s


def normalize_floor(floor_val) -> Optional[str]:
    """
    標準化樓層欄位，回傳純數字或 '全'。
    '二十三層' → '23', '十層，十一層' → '10', '全' → '全', None → None
    """
    if floor_val is None:
        return None
    s = str(floor_val).strip()
    if not s or s == '全':
        return s if s else None
    
    # 處理「十層，十一層」這種多樓層合併交易格式 — 取第一個數字
    parts = re.split(r'[，,、]+', s)
    for part in parts:
        num = chinese_to_arabic(part.strip())
        if num is not None:
            return str(num)
    
    #  fallback: 嘗試直接轉換
    num = chinese_to_arabic(s)
    return str(num) if num is not None else s


def normalize_total_floors(total_floors_val) -> Optional[int]:
    """
    標準化總樓層數，回傳整數。
    '二十三層' → 23, '4' → 4, None → None
    """
    if total_floors_val is None:
        return None
    num = chinese_to_arabic(str(total_floors_val))
    return num


# ── 地理計算 ──────────────────────────────────────────────

def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Haversine distance in kilometers."""
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2)
    return R * 2 * math.asin(min(1.0, math.sqrt(a)))


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Haversine distance in meters."""
    return haversine_km(lat1, lon1, lat2, lon2) * 1000


def meters_to_degrees(meters: float, lat: float) -> float:
    """Convert meters to degrees at given latitude (returns max of lat/lon degrees for square viewbox)."""
    lat_deg = meters / 111320
    lon_deg = meters / (111320 * math.cos(math.radians(lat)))
    return max(lat_deg, lon_deg)


# ── 資料解析 ──────────────────────────────────────────────

def parse_int(val: str) -> Optional[int]:
    """Parse string to int, returning None for empty/invalid values."""
    if not val or str(val).strip() == "":
        return None
    try:
        return int(float(val))
    except (ValueError, TypeError):
        return None


def parse_float(val: str) -> Optional[float]:
    """Parse string to float, returning None for empty/invalid values."""
    if not val or str(val).strip() == "":
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def parse_bool(val: str) -> Optional[bool]:
    """Parse '有'/'無' string to bool."""
    if not val:
        return None
    return str(val).strip() == "有"


def parse_roc_date(roc_str: str) -> Optional[date]:
    """民國年月日 (如 '1140518') → date object.
    
    格式為 7 位數字: ROC_YEAR(3) + MM(2) + DD(2)
    西元年 = 民國年 + 1911
    """
    try:
        roc_str = str(roc_str).strip()
        if len(roc_str) < 7:
            return None
        y = int(roc_str[:3]) + 1911
        m = int(roc_str[3:5])
        d = int(roc_str[5:7])
        return date(y, m, d)
    except (ValueError, IndexError):
        return None


def roc_date_to_string(d: date) -> str:
    """date object → 民國年月日 string (e.g. '1140518')."""
    roc_year = d.year - 1911
    return f"{roc_year:03d}{d.month:02d}{d.day:02d}"


# ── 常數 ──────────────────────────────────────────────────

SQM_PER_TPING = 3.3058  # 平方公尺 / 建坪


# ── 屋齡計算 ──────────────────────────────────────────────

def compute_building_age(build_complete_date_str):
    """
    從民國年月日字串計算屋齡（年）。
    格式範例：'1010726' = 民國101年7月26日
    
    Returns:
        int | None: 屋齡（整數年），無資料則回傳 None
    """
    if not build_complete_date_str or not isinstance(build_complete_date_str, str):
        return None
    
    s = build_complete_date_str.strip()
    if not s.isdigit():
        return None
    
    try:
        length = len(s)
        if length == 7:
            roc_year = int(s[0:3])
            month = int(s[3:5])
            day = int(s[5:7])
        elif length == 6:
            roc_year = int(s[0:2]) + 100 if int(s[0:2]) < 100 else int(s[0:2])
            month = int(s[2:4])
            day = int(s[4:6])
        elif length == 5:
            roc_year = int(s[0:1]) + 100
            month = int(s[1:3])
            day = int(s[3:5])
        elif length == 4:
            roc_year = int(s[0:2]) + 100 if int(s[0:2]) < 100 else int(s[0:2])
            month = int(s[2:4])
            day = 1
        else:
            return None
        
        gregorian_year = 1911 + roc_year
        today = date.today()
        age = today.year - gregorian_year
        
        if today.month < month or (today.month == month and today.day < day):
            age -= 1
        
        return max(0, age)
    except (ValueError, IndexError):
        return None


def parse_roc_year(build_complete_date_str):
    """
    從民國年月日字串提取西元年份。
    Returns:
        int | None
    """
    if not build_complete_date_str or not isinstance(build_complete_date_str, str):
        return None
    
    s = build_complete_date_str.strip()
    if not s.isdigit():
        return None
    
    try:
        length = len(s)
        if length >= 2:
            if length == 7:
                roc_year = int(s[0:3])
            elif length >= 6:
                roc_year = int(s[0:2]) + 100 if int(s[0:2]) < 100 else int(s[0:2])
            else:
                return None
            return 1911 + roc_year
    except (ValueError, IndexError):
        pass
    return None


def normalize_unit_price(val):
    """Convert raw unit_price_tping to 萬/坪 (old data may be in 元/坪)"""
    if val is None:
        return None
    return round(val / 10000, 1) if val > 10000 else round(val, 1)
