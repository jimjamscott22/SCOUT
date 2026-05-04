"""Tests for the orchestrator — fan-out, cache, rate limiting, graph merge."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from scout.cache import ResponseCache
from scout.db import get_engine, get_session_factory, init_db
from scout.models.domain import Edge, InputType, Mode, Node, NodeType, SourceResult
from scout.orchestrator import Orchestrator, OrchestratorResult, _merge, _serialize, _deserialize
from scout.rate_limit import reset_limiters
from scout.sources.base import FetchContext, RateLimit, Source, _REGISTRY


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_source(
    name: str,
    modes: set[Mode],
    accepts: set[InputType],
    result: SourceResult,
    *,
    auth_required: bool = False,
    fail: bool = False,
) -> Source:
    """Return a minimal fake Source instance (not registered)."""

    class _Fake:
        pass

    _Fake.name = name  # type: ignore[attr-defined]
    _Fake.modes = modes  # type: ignore[attr-defined]
    _Fake.accepts = accepts  # type: ignore[attr-defined]
    _Fake.auth_required = auth_required  # type: ignore[attr-defined]
    _Fake.rate_limit = RateLimit(requests=100, window_seconds=1)  # type: ignore[attr-defined]

    async def fetch(self: _Fake, target: str, ctx: FetchContext) -> SourceResult:
        if fail:
            raise RuntimeError("simulated fetch failure")
        return result

    _Fake.fetch = fetch  # type: ignore[attr-defined]
    return _Fake()  # type: ignore[return-value]


def _simple_result(source_name: str, domain: str = "example.com") -> SourceResult:
    sr = SourceResult(source_name=source_name)
    sr.nodes.append(Node(id=f"domain:{domain}", type=NodeType.DOMAIN, label=domain, source_name=source_name))
    sr.edges.append(Edge(src_id=f"domain:{domain}", dst_id="ip:1.2.3.4", relation="resolves_to", source_name=source_name))
    return sr


@pytest.fixture()
def cache() -> ResponseCache:
    engine = get_engine(Path(":memory:"))
    init_db(engine)
    return ResponseCache(get_session_factory(engine))


@pytest.fixture(autouse=True)
def _clean_limiters():
    reset_limiters()
    yield
    reset_limiters()


@pytest.fixture()
def http_client() -> httpx.AsyncClient:
    return httpx.AsyncClient()


# ---------------------------------------------------------------------------
# _merge
# ---------------------------------------------------------------------------


def test_merge_deduplicates_nodes():
    from scout.orchestrator import SourceRunResult

    node = Node(id="domain:x.com", type=NodeType.DOMAIN, label="x.com", source_name="a")
    run_a = SourceRunResult("a", "ok", False, None, [node], [])
    run_b = SourceRunResult("b", "ok", False, None, [node], [])
    nodes, _ = _merge([run_a, run_b])
    assert len(nodes) == 1


def test_merge_deduplicates_edges():
    from scout.orchestrator import SourceRunResult

    edge = Edge(src_id="domain:x.com", dst_id="ip:1.2.3.4", relation="resolves_to", source_name="a")
    run_a = SourceRunResult("a", "ok", False, None, [], [edge])
    run_b = SourceRunResult("b", "ok", False, None, [], [edge])
    _, edges = _merge([run_a, run_b])
    assert len(edges) == 1


def test_merge_skips_error_runs():
    from scout.orchestrator import SourceRunResult

    node = Node(id="domain:x.com", type=NodeType.DOMAIN, label="x.com", source_name="err")
    bad = SourceRunResult("err", "error", False, "boom", [node], [])
    nodes, edges = _merge([bad])
    assert nodes == []
    assert edges == []


def test_merge_includes_cache_hit_runs():
    from scout.orchestrator import SourceRunResult

    node = Node(id="domain:x.com", type=NodeType.DOMAIN, label="x.com", source_name="src")
    run = SourceRunResult("src", "cache_hit", True, None, [node], [])
    nodes, _ = _merge([run])
    assert len(nodes) == 1


# ---------------------------------------------------------------------------
# Serialization round-trip
# ---------------------------------------------------------------------------


def test_serialize_deserialize_round_trip():
    sr = _simple_result("dns_resolver")
    data = _serialize(sr)
    restored = _deserialize("dns_resolver", data)
    assert len(restored.nodes) == len(sr.nodes)
    assert restored.nodes[0].id == sr.nodes[0].id
    assert len(restored.edges) == len(sr.edges)
    assert restored.edges[0].relation == sr.edges[0].relation


# ---------------------------------------------------------------------------
# Orchestrator.run — fan-out
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_calls_all_matching_sources(http_client):
    src_a = _make_source("orch_a", {Mode.THREAT}, {InputType.DOMAIN}, _simple_result("orch_a"))
    src_b = _make_source("orch_b", {Mode.THREAT}, {InputType.DOMAIN}, _simple_result("orch_b"))

    orch = Orchestrator()
    with patch("scout.orchestrator.get_sources", return_value=[src_a, src_b]):
        result = await orch.run(Mode.THREAT, "example.com", InputType.DOMAIN, http=http_client)

    names = {r.source_name for r in result.source_runs}
    assert names == {"orch_a", "orch_b"}


@pytest.mark.asyncio
async def test_run_filters_by_source_names(http_client):
    src_a = _make_source("filter_a", {Mode.THREAT}, {InputType.DOMAIN}, _simple_result("filter_a"))
    src_b = _make_source("filter_b", {Mode.THREAT}, {InputType.DOMAIN}, _simple_result("filter_b"))

    orch = Orchestrator()
    with patch("scout.orchestrator.get_sources", return_value=[src_a, src_b]):
        result = await orch.run(
            Mode.THREAT, "example.com", InputType.DOMAIN,
            http=http_client, source_names=["filter_a"],
        )

    names = {r.source_name for r in result.source_runs}
    assert names == {"filter_a"}


@pytest.mark.asyncio
async def test_run_merges_nodes_across_sources(http_client):
    sr_a = _simple_result("src_a")
    sr_b = _simple_result("src_b")  # produces same domain node → dedup
    src_a = _make_source("src_a", {Mode.THREAT}, {InputType.DOMAIN}, sr_a)
    src_b = _make_source("src_b", {Mode.THREAT}, {InputType.DOMAIN}, sr_b)

    orch = Orchestrator()
    with patch("scout.orchestrator.get_sources", return_value=[src_a, src_b]):
        result = await orch.run(Mode.THREAT, "example.com", InputType.DOMAIN, http=http_client)

    node_ids = {n.id for n in result.nodes}
    assert "domain:example.com" in node_ids
    assert len([n for n in result.nodes if n.id == "domain:example.com"]) == 1


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_captures_source_errors(http_client):
    failing = _make_source("bad_src", {Mode.THREAT}, {InputType.DOMAIN}, _simple_result("bad_src"), fail=True)

    orch = Orchestrator()
    with patch("scout.orchestrator.get_sources", return_value=[failing]):
        result = await orch.run(Mode.THREAT, "example.com", InputType.DOMAIN, http=http_client)

    run = result.source_runs[0]
    assert run.status == "error"
    assert run.error_message is not None
    assert result.nodes == []


@pytest.mark.asyncio
async def test_run_skips_auth_required_without_key(http_client):
    auth_src = _make_source(
        "needs_key", {Mode.THREAT}, {InputType.DOMAIN},
        _simple_result("needs_key"), auth_required=True,
    )

    orch = Orchestrator()
    with patch("scout.orchestrator.get_sources", return_value=[auth_src]):
        result = await orch.run(
            Mode.THREAT, "example.com", InputType.DOMAIN,
            http=http_client, api_keys={},
        )

    run = result.source_runs[0]
    assert run.status == "skipped"
    assert result.nodes == []


@pytest.mark.asyncio
async def test_run_uses_auth_required_source_when_key_present(http_client):
    auth_src = _make_source(
        "keyed_src", {Mode.THREAT}, {InputType.DOMAIN},
        _simple_result("keyed_src"), auth_required=True,
    )

    orch = Orchestrator()
    with patch("scout.orchestrator.get_sources", return_value=[auth_src]):
        result = await orch.run(
            Mode.THREAT, "example.com", InputType.DOMAIN,
            http=http_client, api_keys={"keyed_src": "secret"},
        )

    run = result.source_runs[0]
    assert run.status == "ok"


# ---------------------------------------------------------------------------
# Cache integration
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_populates_cache_on_first_call(http_client, cache):
    src = _make_source("cache_src", {Mode.THREAT}, {InputType.DOMAIN}, _simple_result("cache_src"))

    orch = Orchestrator(cache=cache)
    with patch("scout.orchestrator.get_sources", return_value=[src]):
        await orch.run(Mode.THREAT, "example.com", InputType.DOMAIN, http=http_client)

    cached = cache.get("cache_src", "domain:example.com")
    assert cached is not None


@pytest.mark.asyncio
async def test_run_returns_cache_hit_on_second_call(http_client, cache):
    sr = _simple_result("hit_src")
    src = _make_source("hit_src", {Mode.THREAT}, {InputType.DOMAIN}, sr)

    orch = Orchestrator(cache=cache)
    with patch("scout.orchestrator.get_sources", return_value=[src]):
        await orch.run(Mode.THREAT, "example.com", InputType.DOMAIN, http=http_client)

    # Second call — source.fetch should NOT be called again
    fetch_mock = AsyncMock(return_value=sr)
    src.fetch = fetch_mock  # type: ignore[method-assign]

    with patch("scout.orchestrator.get_sources", return_value=[src]):
        result2 = await orch.run(Mode.THREAT, "example.com", InputType.DOMAIN, http=http_client)

    run = result2.source_runs[0]
    assert run.cache_hit is True
    assert run.status == "cache_hit"
    fetch_mock.assert_not_called()


@pytest.mark.asyncio
async def test_run_without_cache_always_fetches(http_client):
    sr = _simple_result("nocache_src")
    fetch_mock = AsyncMock(return_value=sr)

    src = _make_source("nocache_src", {Mode.THREAT}, {InputType.DOMAIN}, sr)
    src.fetch = fetch_mock  # type: ignore[method-assign]

    orch = Orchestrator(cache=None)
    with patch("scout.orchestrator.get_sources", return_value=[src]):
        await orch.run(Mode.THREAT, "example.com", InputType.DOMAIN, http=http_client)
        await orch.run(Mode.THREAT, "example.com", InputType.DOMAIN, http=http_client)

    assert fetch_mock.call_count == 2
