"""
Simple in-memory cache with TTL support.
Uses a singleton pattern per cache name.
"""
import time
import threading
from typing import Any, Optional

_caches: dict[str, "Cache"] = {}
_lock = threading.Lock()


def get_cache(name: str = "default", ttl: int = 3600) -> "Cache":
    """Get or create a named cache instance."""
    with _lock:
        if name not in _caches:
            _caches[name] = Cache(ttl=ttl)
        return _caches[name]


class Cache:
    """Thread-safe in-memory cache with TTL."""

    def __init__(self, ttl: int = 3600):
        self.ttl = ttl
        self._store: dict[str, tuple[Any, float]] = {}
        self._lock = threading.Lock()

    def get(self, key: str) -> Optional[Any]:
        with self._lock:
            if key in self._store:
                value, expiry = self._store[key]
                if time.time() < expiry:
                    return value
                else:
                    del self._store[key]
            return None

    def set(self, key: str, value: Any) -> None:
        with self._lock:
            self._store[key] = (value, time.time() + self.ttl)

    def delete(self, key: str) -> bool:
        with self._lock:
            if key in self._store:
                del self._store[key]
                return True
            return False

    def clear(self) -> None:
        with self._lock:
            self._store.clear()

    def size(self) -> int:
        with self._lock:
            now = time.time()
            return sum(1 for _, expiry in self._store.values() if now < expiry)
