"""Tests for the per-source rate limiter."""

from __future__ import annotations

import asyncio

import pytest

from scout.rate_limit import _LIMITERS, get_limiter, reset_limiters
from scout.sources.base import RateLimit


@pytest.fixture(autouse=True)
def _clean_limiters():
    reset_limiters()
    yield
    reset_limiters()


# ---------------------------------------------------------------------------
# get_limiter
# ---------------------------------------------------------------------------


def test_get_limiter_returns_limiter():
    from aiolimiter import AsyncLimiter

    limiter = get_limiter("src_a", RateLimit(requests=10, window_seconds=60))
    assert isinstance(limiter, AsyncLimiter)


def test_get_limiter_same_name_returns_same_instance():
    rl = RateLimit(requests=5, window_seconds=30)
    a = get_limiter("shared", rl)
    b = get_limiter("shared", rl)
    assert a is b


def test_get_limiter_different_names_different_instances():
    rl = RateLimit(requests=5)
    a = get_limiter("src_x", rl)
    b = get_limiter("src_y", rl)
    assert a is not b


def test_get_limiter_stores_in_registry():
    get_limiter("registered_src", RateLimit(requests=2))
    assert "registered_src" in _LIMITERS


# ---------------------------------------------------------------------------
# reset_limiters
# ---------------------------------------------------------------------------


def test_reset_limiters_clears_registry():
    get_limiter("to_clear", RateLimit(requests=1))
    reset_limiters()
    assert "to_clear" not in _LIMITERS


# ---------------------------------------------------------------------------
# Functional: limiter actually throttles
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_limiter_allows_acquisition():
    limiter = get_limiter("fast_src", RateLimit(requests=100, window_seconds=1))
    async with limiter:
        pass  # should not raise or block meaningfully


@pytest.mark.asyncio
async def test_limiter_is_usable_as_async_context_manager():
    limiter = get_limiter("ctx_src", RateLimit(requests=10, window_seconds=60))
    results = []
    async with limiter:
        results.append(1)
    assert results == [1]
