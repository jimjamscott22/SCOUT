"""
Per-source rate limiter backed by ``aiolimiter.AsyncLimiter``.

Each source declares a :class:`~scout.sources.base.RateLimit` on its class.
The orchestrator calls :func:`get_limiter` once per source name to obtain a
shared :class:`SourceRateLimiter` and then uses it as an async context manager
around every ``fetch()`` call::

    limiter = get_limiter(source.name, source.rate_limit)
    async with limiter:
        result = await source.fetch(target, ctx)

Limiters are module-level singletons — the same source always shares one
token bucket across all concurrent fetch calls.
"""

from __future__ import annotations

from aiolimiter import AsyncLimiter

from scout.sources.base import RateLimit

_LIMITERS: dict[str, AsyncLimiter] = {}


def get_limiter(source_name: str, rate_limit: RateLimit) -> AsyncLimiter:
    """Return the shared :class:`AsyncLimiter` for *source_name*.

    Creates a new limiter on the first call for a given *source_name* using the
    supplied *rate_limit* descriptor.  Subsequent calls for the same name always
    return the same instance (the *rate_limit* argument is ignored after the
    first call, so callers must use consistent values).
    """
    if source_name not in _LIMITERS:
        _LIMITERS[source_name] = AsyncLimiter(
            max_rate=rate_limit.requests,
            time_period=rate_limit.window_seconds,
        )
    return _LIMITERS[source_name]


def reset_limiters() -> None:
    """Clear all cached limiters. Intended for use in tests only."""
    _LIMITERS.clear()
