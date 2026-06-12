"""Simple LRU cache for API responses — no external deps needed."""
import time
import threading
from collections import OrderedDict


class LRUCache:
    """Thread-safe LRU cache with TTL support.
    
    Usage:
        cache = LRUCache(max_size=100, default_ttl=300)
        cache.set("key", data)
        result = cache.get("key")  # None if expired or missing
    """

    def __init__(self, max_size: int = 100, default_ttl: int = 300):
        self._cache = OrderedDict()
        self._expiry = {}
        self._lock = threading.Lock()
        self._max_size = max_size
        self._default_ttl = default_ttl

    def get(self, key: str):
        with self._lock:
            if key not in self._cache:
                return None
            if time.time() > self._expiry.get(key, 0):
                self._cache.pop(key, None)
                self._expiry.pop(key, None)
                return None
            # Move to end (most recently used)
            self._cache.move_to_end(key)
            return self._cache[key]

    def set(self, key: str, value, ttl: int = None):
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
            else:
                if len(self._cache) >= self._max_size:
                    oldest_key = next(iter(self._cache))
                    self._cache.pop(oldest_key)
                    self._expiry.pop(oldest_key, None)
            self._cache[key] = value
            self._expiry[key] = time.time() + (ttl or self._default_ttl)

    def invalidate_pattern(self, pattern: str):
        """Remove all keys containing the pattern."""
        with self._lock:
            keys_to_remove = [k for k in self._cache if pattern in k]
            for k in keys_to_remove:
                self._cache.pop(k, None)
                self._expiry.pop(k, None)

    def clear(self):
        with self._lock:
            self._cache.clear()
            self._expiry.clear()

    @property
    def stats(self):
        with self._lock:
            return {
                "size": len(self._cache),
                "max_size": self._max_size,
            }


# Module-level singleton — shared across API calls
api_cache = LRUCache(max_size=200, default_ttl=300)  # 5 min TTL