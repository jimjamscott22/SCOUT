"""Tests for FastAPI routes — health, sources, investigate."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from scout.cache import ResponseCache
from scout.db import get_engine, get_session_factory, init_db
from scout.main import app
from scout.models.domain import Edge, InputType, Mode, Node, NodeType, SourceResult
from scout.orchestrator import OrchestratorResult, SourceRunResult


# ---------------------------------------------------------------------------
# Shared in-memory DB + cache fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def db_engine():
    from sqlalchemy import create_engine
    from sqlalchemy.pool import StaticPool

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    init_db(engine)
    return engine


@pytest.fixture(scope="module")
def session_factory(db_engine):
    return get_session_factory(db_engine)


@pytest.fixture(scope="module")
def test_cache(session_factory):
    return ResponseCache(session_factory)


@pytest.fixture(scope="module")
def client(db_engine, session_factory, test_cache):
    from sqlalchemy.orm import Session

    def _override_session():
        with session_factory() as s:
            yield s

    def _override_cache():
        return test_cache

    from scout.api.routes_investigate import _get_cache, _get_session

    app.dependency_overrides[_get_session] = _override_session
    app.dependency_overrides[_get_cache] = _override_cache
    yield TestClient(app)
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


# ---------------------------------------------------------------------------
# Sources
# ---------------------------------------------------------------------------


def test_list_sources_returns_list(client):
    r = client.get("/api/sources")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_list_sources_includes_dns_resolver(client):
    r = client.get("/api/sources")
    names = [s["name"] for s in r.json()]
    assert "dns_resolver" in names


def test_list_sources_filter_by_mode(client):
    r = client.get("/api/sources?mode=threat")
    assert r.status_code == 200
    sources = r.json()
    for src in sources:
        assert "threat" in src["modes"]


def test_list_sources_invalid_mode(client):
    r = client.get("/api/sources?mode=bogus")
    assert r.status_code == 422


# ---------------------------------------------------------------------------
# Investigate — POST
# ---------------------------------------------------------------------------


def _mock_orch_result(domain: str = "example.com") -> OrchestratorResult:
    node = Node(id=f"domain:{domain}", type=NodeType.DOMAIN, label=domain, source_name="dns_resolver")
    run = SourceRunResult(
        source_name="dns_resolver",
        status="ok",
        cache_hit=False,
        error_message=None,
        nodes=[node],
        edges=[],
    )
    return OrchestratorResult(source_runs=[run], nodes=[node], edges=[])


def test_investigate_returns_200(client):
    mock_result = _mock_orch_result()
    with patch("scout.api.routes_investigate.Orchestrator") as MockOrch:
        instance = MockOrch.return_value
        instance.run = AsyncMock(return_value=mock_result)
        r = client.post("/api/investigate", json={
            "mode": "threat",
            "target": "example.com",
            "target_type": "domain",
        })
    assert r.status_code == 200


def test_investigate_response_shape(client):
    mock_result = _mock_orch_result()
    with patch("scout.api.routes_investigate.Orchestrator") as MockOrch:
        instance = MockOrch.return_value
        instance.run = AsyncMock(return_value=mock_result)
        r = client.post("/api/investigate", json={
            "mode": "threat",
            "target": "example.com",
            "target_type": "domain",
        })
    body = r.json()
    assert "id" in body
    assert body["mode"] == "threat"
    assert body["target"] == "example.com"
    assert body["status"] == "complete"
    assert isinstance(body["nodes"], list)
    assert isinstance(body["edges"], list)
    assert isinstance(body["source_runs"], list)


def test_investigate_invalid_mode(client):
    r = client.post("/api/investigate", json={
        "mode": "banana",
        "target": "example.com",
        "target_type": "domain",
    })
    assert r.status_code == 422


def test_investigate_invalid_target_type(client):
    r = client.post("/api/investigate", json={
        "mode": "threat",
        "target": "example.com",
        "target_type": "fridge",
    })
    assert r.status_code == 422


# ---------------------------------------------------------------------------
# Investigations — GET list and GET by id
# ---------------------------------------------------------------------------


def test_list_investigations_empty(client):
    # Fresh in-memory DB from module fixture — but other tests may have added rows.
    r = client.get("/api/investigations")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_get_investigation_not_found(client):
    r = client.get("/api/investigations/nonexistent-uuid")
    assert r.status_code == 404


def test_get_investigation_round_trip(client):
    """Create an investigation via POST then retrieve it by id."""
    mock_result = _mock_orch_result("roundtrip.com")
    with patch("scout.api.routes_investigate.Orchestrator") as MockOrch:
        instance = MockOrch.return_value
        instance.run = AsyncMock(return_value=mock_result)
        post_r = client.post("/api/investigate", json={
            "mode": "threat",
            "target": "roundtrip.com",
            "target_type": "domain",
        })
    assert post_r.status_code == 200
    inv_id = post_r.json()["id"]

    get_r = client.get(f"/api/investigations/{inv_id}")
    assert get_r.status_code == 200
    body = get_r.json()
    assert body["id"] == inv_id
    assert body["target"] == "roundtrip.com"
    assert body["status"] == "complete"


def test_list_investigations_shows_created(client):
    mock_result = _mock_orch_result("listed.com")
    with patch("scout.api.routes_investigate.Orchestrator") as MockOrch:
        instance = MockOrch.return_value
        instance.run = AsyncMock(return_value=mock_result)
        client.post("/api/investigate", json={
            "mode": "footprint",
            "target": "listed.com",
            "target_type": "domain",
        })

    r = client.get("/api/investigations")
    targets = [inv["target"] for inv in r.json()]
    assert "listed.com" in targets
