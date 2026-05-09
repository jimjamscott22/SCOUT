"""Tests for the Gravatar source plugin."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from scout.models.domain import InputType, Mode, NodeType
from scout.sources.base import _REGISTRY, FetchContext, get_sources
from scout.sources.footprint.gravatar import GravatarSource

_EMAIL = "test@example.com"
_HASH = "55502f40dc8b7c769880b10874abc9d0"  # md5("test@example.com")


@pytest.fixture()
def source() -> GravatarSource:
    return GravatarSource()


@pytest.fixture()
def ctx() -> FetchContext:
    http = AsyncMock()
    return FetchContext(http=http, api_keys={})


def _mock_response(status: int, json_data: dict) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status
    resp.json.return_value = json_data
    resp.raise_for_status = MagicMock()
    return resp


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------


def test_gravatar_is_registered():
    assert "gravatar" in _REGISTRY


def test_gravatar_in_footprint_email_sources():
    sources = get_sources(mode=Mode.FOOTPRINT, input_type=InputType.EMAIL)
    assert any(s.name == "gravatar" for s in sources)


def test_gravatar_not_auth_required(source):
    assert not source.auth_required


# ---------------------------------------------------------------------------
# fetch() — profile found
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_found_returns_email_and_account_nodes(source, ctx):
    ctx.http.get.return_value = _mock_response(
        200,
        {"entry": [{"displayName": "Jamie", "profileUrl": "https://gravatar.com/jamie"}]},
    )
    result = await source.fetch(_EMAIL, ctx)

    email_nodes = [n for n in result.nodes if n.type == NodeType.EMAIL]
    account_nodes = [n for n in result.nodes if n.type == NodeType.ACCOUNT]
    assert len(email_nodes) == 1
    assert len(account_nodes) == 1


@pytest.mark.asyncio
async def test_fetch_found_email_node_id(source, ctx):
    ctx.http.get.return_value = _mock_response(200, {"entry": [{"displayName": "Jamie"}]})
    result = await source.fetch(_EMAIL, ctx)
    email_node = next(n for n in result.nodes if n.type == NodeType.EMAIL)
    assert email_node.id == f"email:{_EMAIL}"


@pytest.mark.asyncio
async def test_fetch_found_account_node_has_platform_attr(source, ctx):
    ctx.http.get.return_value = _mock_response(200, {"entry": [{"displayName": "Jamie"}]})
    result = await source.fetch(_EMAIL, ctx)
    account_node = next(n for n in result.nodes if n.type == NodeType.ACCOUNT)
    assert account_node.attrs["platform"] == "gravatar"
    assert account_node.attrs["hash"] == _HASH


@pytest.mark.asyncio
async def test_fetch_found_owns_edge(source, ctx):
    ctx.http.get.return_value = _mock_response(200, {"entry": [{"displayName": "Jamie"}]})
    result = await source.fetch(_EMAIL, ctx)
    assert len(result.edges) == 1
    assert result.edges[0].relation == "owns"
    assert result.edges[0].src_id == f"email:{_EMAIL}"


# ---------------------------------------------------------------------------
# fetch() — 404 (no account)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_not_found_returns_email_node_only(source, ctx):
    ctx.http.get.return_value = _mock_response(404, {})
    result = await source.fetch(_EMAIL, ctx)

    assert len(result.nodes) == 1
    assert result.nodes[0].type == NodeType.EMAIL
    assert result.edges == []
