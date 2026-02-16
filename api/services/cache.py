"""Simple TTL cache with optional LRU eviction."""

import time
from collections import OrderedDict
from typing import Any


class TTLCache:
    """Thread-safe in-memory cache with time-to-live and max-size eviction.

    Usage::

        cache = TTLCache(ttl=300, max_size=100)
        cache.set("key", value)
        hit = cache.get("key")  # returns value or None if expired/missing
    """

    def __init__(self, ttl: float = 300, max_size: int = 100) -> None:
        self._ttl = ttl
        self._max_size = max_size
        # OrderedDict preserves insertion order for LRU eviction
        self._store: OrderedDict[str, tuple[Any, float]] = OrderedDict()

    def get(self, key: str) -> Any | None:
        """Return the cached value if present and not expired, else None."""
        entry = self._store.get(key)
        if entry is None:
            return None
        value, ts = entry
        if time.time() - ts > self._ttl:
            del self._store[key]
            return None
        # Move to end (most recently used)
        self._store.move_to_end(key)
        return value

    def set(self, key: str, value: Any) -> None:
        """Store a value under *key*, evicting the oldest entry if at capacity."""
        if key in self._store:
            self._store.move_to_end(key)
        self._store[key] = (value, time.time())
        # Evict oldest entries if over max_size
        while len(self._store) > self._max_size:
            self._store.popitem(last=False)
