"""Tests for the source protocol, registry, and filtering logic."""

from __future__ import annotations

import pytest
from scout.models.domain import InputType, Mode, SourceResult
from scout.sources.base import (
    _REGISTRY,
    FetchContext,
    RateLimit,
    Source,
    get_source,
    get_sources,
    register,
)

# ---------------------------------------------------------------------------
# Helpers — minimal stub sources registered only within each test
# ---------------------------------------------------------------------------


def _make_stub(
    name: str,
    modes: set[Mode],
    accepts: set[InputType],
    *,
    auth_required: bool = False,
) -> type:
    """Return a minimal Source class (not yet registered)."""

    class _Stub:
        pass

    _Stub.name = name  # type: ignore[attr-defined]
    _Stub.modes = modes  # type: ignore[attr-defined]
    _Stub.accepts = accepts  # type: ignore[attr-defined]
    _Stub.auth_required = auth_required  # type: ignore[attr-defined]
    _Stub.rate_limit = RateLimit(requests=10)  # type: ignore[attr-defined]

    async def fetch(self: _Stub, target: str, ctx: FetchContext) -> SourceResult:
        return SourceResult(source_name=self.name)

    _Stub.fetch = fetch  # type: ignore[attr-defined]
    _Stub.__name__ = name
    return _Stub


@pytest.fixture(autouse=True)
def _clean_registry():
    """Isolate registry state between tests."""
    before = dict(_REGISTRY)
    yield
    _REGISTRY.clear()
    _REGISTRY.update(before)


# ---------------------------------------------------------------------------
# Protocol conformance
# ---------------------------------------------------------------------------


def test_stub_satisfies_protocol():
    cls = _make_stub("proto_test", {Mode.FOOTPRINT}, {InputType.EMAIL})
    assert isinstance(cls(), Source)


# ---------------------------------------------------------------------------
# @register decorator
# ---------------------------------------------------------------------------


def test_register_stores_instance():
    cls = _make_stub("reg_store", {Mode.FOOTPRINT}, {InputType.EMAIL})
    register(cls)
    assert "reg_store" in _REGISTRY
    assert isinstance(_REGISTRY["reg_store"], cls)


def test_register_duplicate_raises():
    cls = _make_stub("dup_source", {Mode.FOOTPRINT}, {InputType.EMAIL})
    register(cls)
    cls2 = _make_stub("dup_source", {Mode.THREAT}, {InputType.IP})
    with pytest.raises(ValueError, match="dup_source"):
        register(cls2)


def test_register_returns_original_class():
    cls = _make_stub("ret_cls", {Mode.FOOTPRINT}, {InputType.EMAIL})
    result = register(cls)
    assert result is cls


# ---------------------------------------------------------------------------
# get_sources filtering
# ---------------------------------------------------------------------------


def test_get_sources_no_filter_returns_all():
    a = _make_stub("src_a", {Mode.FOOTPRINT}, {InputType.EMAIL})
    b = _make_stub("src_b", {Mode.THREAT}, {InputType.IP})
    register(a)
    register(b)
    names = {s.name for s in get_sources()}
    assert {"src_a", "src_b"}.issubset(names)


def test_get_sources_filter_by_mode():
    a = _make_stub("fp_only", {Mode.FOOTPRINT}, {InputType.EMAIL})
    b = _make_stub("th_only", {Mode.THREAT}, {InputType.IP})
    register(a)
    register(b)
    fp = {s.name for s in get_sources(mode=Mode.FOOTPRINT)}
    assert "fp_only" in fp
    assert "th_only" not in fp


def test_get_sources_filter_by_input_type():
    a = _make_stub("email_src", {Mode.FOOTPRINT}, {InputType.EMAIL})
    b = _make_stub("domain_src", {Mode.FOOTPRINT}, {InputType.DOMAIN})
    register(a)
    register(b)
    email_sources = {s.name for s in get_sources(input_type=InputType.EMAIL)}
    assert "email_src" in email_sources
    assert "domain_src" not in email_sources


def test_get_sources_filter_by_both():
    multi = _make_stub("multi", {Mode.FOOTPRINT, Mode.THREAT}, {InputType.DOMAIN, InputType.EMAIL})
    register(multi)
    result = get_sources(mode=Mode.FOOTPRINT, input_type=InputType.DOMAIN)
    assert any(s.name == "multi" for s in result)


def test_get_sources_no_match_returns_empty():
    a = _make_stub("fp_email", {Mode.FOOTPRINT}, {InputType.EMAIL})
    register(a)
    result = get_sources(mode=Mode.THREAT, input_type=InputType.IP)
    assert not any(s.name == "fp_email" for s in result)


# ---------------------------------------------------------------------------
# get_source
# ---------------------------------------------------------------------------


def test_get_source_returns_instance():
    cls = _make_stub("lookup_me", {Mode.FOOTPRINT}, {InputType.EMAIL})
    register(cls)
    src = get_source("lookup_me")
    assert src is not None
    assert src.name == "lookup_me"


def test_get_source_missing_returns_none():
    assert get_source("nonexistent_xyz") is None
