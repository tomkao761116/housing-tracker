"""API Response Cache — TTL-based in-memory cache for read-heavy endpoints."""
from cachetools import TTLCache
import json


class APICache:
    """Simple TTL cache for API responses. Thread-safe via cachetools."""

    def __init__(self, maxsize=100, ttl=300):
        # maxsize=100 筆、ttl=5 分鐘
        self._cache = TTLCache(maxsize=maxsize, ttl=ttl)

    def get(self, key: str):
        return self._cache.get(key)

    def set(self, key: str, value):
        self._cache[key] = value

    @property
    def stats(self):
        cur_size = len(self._cache)
        # cachetools TTLCache 沒有 hits/misses counter，自己算
        return f"APICache: {cur_size} entries"


# 全域快取實例（不同 TTL）
rankings_cache = APICache(maxsize=50, ttl=600)     # 排行資料 10 分鐘
districts_cache = APICache(maxsize=20, ttl=1800)   # 區鄉鎮列表 30 分鐘
stats_cache = APICache(maxsize=20, ttl=300)         # 統計資料 5 分鐘
