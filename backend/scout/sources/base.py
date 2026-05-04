"""
Source protocol, RateLimit descriptor, FetchContext, and plugin registry.

Usage
-----
Implementing a source::

    from scout.sources.base import register, FetchContext, RateLimit
    from scout.models.domain import InputType, Mode, SourceResult

    @register
    class MySource:
        name = "my_source"
        modes = {Mode.FOOTPRINT}
        accepts = {InputType.EMAIL}
        auth_required = False
        rate_limit = RateLimit(requests=10, window_seconds=60)

        async def fetch(self, target: str, ctx: FetchContext) -> SourceResult: ...

Querying the registry::

    from scout.sources.base import get_sources
    sources = get_sources(mode=Mode.FOOTPRINT, input_type=InputType.EMAIL)
"""

from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    import httpx

from scout.models.domain import InputType, Mode, SourceResult


@dataclasses.dataclass(frozen=True)
class RateLimit:
    """Declares how often a source may be called.

    The orchestrator uses these values to configure an ``aiolimiter``
    ``AsyncLimiter(max_rate=requests, time_period=window_seconds)``.
    """

    requests: int
    window_seconds: float = 60.0


@dataclasses.dataclass
class FetchContext:
    """Shared resources passed to every ``Source.fetch()`` call.

    ``http`` is a single shared ``httpx.AsyncClient`` with a reasonable
    timeout/headers; sources should NOT create their own clients.
    ``api_keys`` is a flat dict of ``{source_name: key}`` populated from
    ``ScoutConfig``.  Sources that are ``auth_required`` should raise
    ``ValueError`` if their key is missing or empty.
    """

    http: httpx.AsyncClient
    api_keys: dict[str, str] = dataclasses.field(default_factory=dict)


@runtime_checkable
class Source(Protocol):
    """Every data-source plugin must satisfy this interface.

    Class attributes are read by the registry and the orchestrator; they must
    be declared as class-level attributes (not instance attributes) so that
    the registry can inspect them without instantiating the class.
    """

    name: str
    modes: set[Mode]
    accepts: set[InputType]
    auth_required: bool
    rate_limit: RateLimit

    async def fetch(self, target: str, ctx: FetchContext) -> SourceResult: ...


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

_REGISTRY: dict[str, Source] = {}


def register(cls: type) -> type:
    """Class decorator that registers a source plugin.

    The decorated class is instantiated once and stored in the global registry
    keyed by ``cls.name``.  Duplicate names raise ``ValueError``.

    Example::

        @register
        class HibpSource:
            name = "haveibeenpwned"
            ...
    """
    instance: Source = cls()
    if instance.name in _REGISTRY:
        raise ValueError(f"Source name already registered: {instance.name!r}")
    _REGISTRY[instance.name] = instance
    return cls


def get_sources(
    mode: Mode | None = None,
    input_type: InputType | None = None,
) -> list[Source]:
    """Return registered sources optionally filtered by mode and/or input type.

    Passing neither argument returns all registered sources.
    """
    results: list[Source] = []
    for src in _REGISTRY.values():
        if mode is not None and mode not in src.modes:
            continue
        if input_type is not None and input_type not in src.accepts:
            continue
        results.append(src)
    return results


def get_source(name: str) -> Source | None:
    """Return the source registered under *name*, or ``None``."""
    return _REGISTRY.get(name)
