"""Tests for TTLCache — pure logic, no mocks needed."""

import time

from api.services.cache import TTLCache


def test_set_and_get_returns_value():
    cache = TTLCache(ttl=60)
    cache.set("k", "v")
    assert cache.get("k") == "v"


def test_expired_key_returns_none():
    cache = TTLCache(ttl=0.01)
    cache.set("k", "v")
    time.sleep(0.02)
    assert cache.get("k") is None


def test_max_size_evicts_oldest():
    cache = TTLCache(ttl=60, max_size=2)
    cache.set("a", 1)
    cache.set("b", 2)
    cache.set("c", 3)
    assert cache.get("a") is None  # evicted
    assert cache.get("b") == 2
    assert cache.get("c") == 3


def test_get_refreshes_lru_order():
    cache = TTLCache(ttl=60, max_size=2)
    cache.set("a", 1)
    cache.set("b", 2)
    cache.get("a")  # refresh a — now b is oldest
    cache.set("c", 3)  # should evict b, not a
    assert cache.get("a") == 1
    assert cache.get("b") is None  # evicted
    assert cache.get("c") == 3
