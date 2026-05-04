"""Tests for the TTL response cache."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest

from scout.cache import ResponseCache, _cache_id
from scout.db import get_engine, get_session_factory, init_db
from scout.models.db import ResponseCache as ResponseCacheRow


@pytest.fixture()
def cache() -> ResponseCache:
    engine = get_engine(Path(":memory:"))
    init_db(engine)
    return ResponseCache(get_session_factory(engine))


# ---------------------------------------------------------------------------
# _cache_id
# ---------------------------------------------------------------------------


def test_cache_id_deterministic():
    assert _cache_id("hibp", "email:a@b.com") == _cache_id("hibp", "email:a@b.com")


def test_cache_id_different_sources_differ():
    assert _cache_id("hibp", "email:a@b.com") != _cache_id("vt", "email:a@b.com")


def test_cache_id_different_keys_differ():
    assert _cache_id("hibp", "email:a@b.com") != _cache_id("hibp", "email:x@y.com")


def test_cache_id_length():
    assert len(_cache_id("hibp", "email:a@b.com")) == 32


# ---------------------------------------------------------------------------
# get — miss
# ---------------------------------------------------------------------------


def test_get_missing_returns_none(cache: ResponseCache):
    assert cache.get("hibp", "email:nobody@example.com") is None


# ---------------------------------------------------------------------------
# set / get round-trip
# ---------------------------------------------------------------------------


def test_set_then_get_returns_data(cache: ResponseCache):
    data = {"breaches": ["Adobe"], "count": 1}
    cache.set("hibp", "email:a@b.com", data, ttl_seconds=3600)
    result = cache.get("hibp", "email:a@b.com")
    assert result == data


def test_set_overwrites_existing(cache: ResponseCache):
    cache.set("hibp", "email:a@b.com", {"v": 1}, ttl_seconds=3600)
    cache.set("hibp", "email:a@b.com", {"v": 2}, ttl_seconds=3600)
    assert cache.get("hibp", "email:a@b.com") == {"v": 2}


def test_different_keys_are_independent(cache: ResponseCache):
    cache.set("hibp", "email:a@b.com", {"a": 1}, ttl_seconds=3600)
    cache.set("hibp", "email:x@y.com", {"x": 9}, ttl_seconds=3600)
    assert cache.get("hibp", "email:a@b.com") == {"a": 1}
    assert cache.get("hibp", "email:x@y.com") == {"x": 9}


def test_different_sources_same_key_independent(cache: ResponseCache):
    cache.set("hibp", "email:a@b.com", {"src": "hibp"}, ttl_seconds=3600)
    cache.set("vt", "email:a@b.com", {"src": "vt"}, ttl_seconds=3600)
    assert cache.get("hibp", "email:a@b.com") == {"src": "hibp"}
    assert cache.get("vt", "email:a@b.com") == {"src": "vt"}


# ---------------------------------------------------------------------------
# Expiry
# ---------------------------------------------------------------------------


def test_expired_entry_returns_none(cache: ResponseCache):
    cache.set("hibp", "email:old@b.com", {"x": 1}, ttl_seconds=60)
    # Wind the clock forward past expiry
    future = datetime.now(UTC) + timedelta(seconds=120)
    with patch("scout.cache.datetime") as mock_dt:
        mock_dt.now.return_value = future
        result = cache.get("hibp", "email:old@b.com")
    assert result is None


def test_expired_entry_is_deleted_from_db(cache: ResponseCache):
    cache.set("hibp", "email:old@b.com", {"x": 1}, ttl_seconds=60)
    future = datetime.now(UTC) + timedelta(seconds=120)
    with patch("scout.cache.datetime") as mock_dt:
        mock_dt.now.return_value = future
        cache.get("hibp", "email:old@b.com")

    # After the lazy-eviction read, the row should be gone
    result = cache.get("hibp", "email:old@b.com")
    assert result is None


def test_not_yet_expired_entry_is_returned(cache: ResponseCache):
    cache.set("hibp", "email:fresh@b.com", {"x": 1}, ttl_seconds=3600)
    # Wind forward by less than TTL
    near_future = datetime.now(UTC) + timedelta(seconds=1800)
    with patch("scout.cache.datetime") as mock_dt:
        mock_dt.now.return_value = near_future
        mock_dt.side_effect = None
        result = cache.get("hibp", "email:fresh@b.com")
    assert result == {"x": 1}


# ---------------------------------------------------------------------------
# evict_expired
# ---------------------------------------------------------------------------


def test_evict_expired_removes_stale_entries(cache: ResponseCache):
    cache.set("hibp", "email:a@b.com", {"a": 1}, ttl_seconds=10)
    cache.set("hibp", "email:b@b.com", {"b": 2}, ttl_seconds=10)
    cache.set("hibp", "email:c@b.com", {"c": 3}, ttl_seconds=7200)

    future = datetime.now(UTC) + timedelta(seconds=30)
    with patch("scout.cache.datetime") as mock_dt:
        mock_dt.now.return_value = future
        count = cache.evict_expired()

    assert count == 2


def test_evict_expired_returns_zero_when_nothing_expired(cache: ResponseCache):
    cache.set("hibp", "email:a@b.com", {"a": 1}, ttl_seconds=7200)
    count = cache.evict_expired()
    assert count == 0


def test_evict_expired_preserves_valid_entries(cache: ResponseCache):
    cache.set("hibp", "email:keep@b.com", {"keep": True}, ttl_seconds=7200)
    cache.set("hibp", "email:drop@b.com", {"drop": True}, ttl_seconds=1)

    future = datetime.now(UTC) + timedelta(seconds=10)
    with patch("scout.cache.datetime") as mock_dt:
        mock_dt.now.return_value = future
        cache.evict_expired()

    assert cache.get("hibp", "email:keep@b.com") == {"keep": True}
