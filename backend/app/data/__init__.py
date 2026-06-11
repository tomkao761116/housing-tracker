"""地理靜態資料包 - 台灣縣市與行政區映射"""
from .county_districts import COUNTY_DISTRICTS, get_counties, get_districts

__all__ = ["COUNTY_DISTRICTS", "get_counties", "get_districts"]
