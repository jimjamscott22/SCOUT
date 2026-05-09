"""Tests for the Have I Been Pwned source plugin."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from scout.models.domain import InputType, Mode, NodeType
from scout.sources.base import _REGISTRY, FetchContext, get_sources
from scout.sources.footprint.hibp import HibpSource

_EMAIL = "test@example.com"

_FAKE_BREACHES = [
    {
        "Name": "Adobe",
        "Title": "Adobe",
        "BreachDate": "2013-10-04",
        "PwnCount": 152445165,
        "DataClasses": ["Email addresses", "Password hints", "Passwords", "Usernames"],
        "Domain": "adobe.com",
        "Description": "In October 2013...",
    },
    {
        "Name": "LinkedIn",
        "Title": "LinkedIn",
        "BreachDate": "2012-05-05",
        "PwnCount": 164611595,
        "DataClasses": ["Email addresses", "Passwords"],
        "Domain": "linkedin.com",
        "Description": "In May 2016...",
    },
]


@pytest.fixture()
def source() -> HibpSource:
    return HibpSource()


@pytest.fixture()
def ctx() -> FetchContext:
    http = AsyncMock()
    return FetchContext(http=http, api_keys={"haveibeenpwned": "test-api-key"})


def _mock_response(status: int, json_data) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status
    resp.json.return_value = json_data
    resp.raise_for_status = MagicMock()
    return resp


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------


def test_hibp_is_registered():
    assert "haveibeenpwned" in _REGISTRY


def test_hibp_in_footprint_email_sources():
    sources = get_sources(mode=Mode.FOOTPRINT, input_type=InputType.EMAIL)
    assert any(s.name == "haveibeenpwned" for s in sources)


def test_hibp_is_auth_required(source):
    assert source.auth_required


# ---------------------------------------------------------------------------
# fetch() — breaches found
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_found_returns_email_and_breach_nodes(source, ctx):
    ctx.http.get.return_value = _mock_response(200, _FAKE_BREACHES)
    result = await source.fetch(_EMAIL, ctx)

    email_nodes = [n for n in result.nodes if n.type == NodeType.EMAIL]
    breach_nodes = [n for n in result.nodes if n.type == NodeType.BREACH]
    assert len(email_nodes) == 1
    assert len(breach_nodes) == 2


@pytest.mark.asyncio
async def test_fetch_breach_node_ids(source, ctx):
    ctx.http.get.return_value = _mock_response(200, _FAKE_BREACHES)
    result = await source.fetch(_EMAIL, ctx)

    breach_ids = {n.id for n in result.nodes if n.type == NodeType.BREACH}
    assert breach_ids == {"breach:adobe", "breach:linkedin"}


@pytest.mark.asyncio
async def test_fetch_exposed_in_edges(source, ctx):
    ctx.http.get.return_value = _mock_response(200, _FAKE_BREACHES)
    result = await source.fetch(_EMAIL, ctx)

    assert len(result.edges) == 2
    for edge in result.edges:
        assert edge.relation == "exposed_in"
        assert edge.src_id == f"email:{_EMAIL}"


@pytest.mark.asyncio
async def test_fetch_breach_attrs_populated(source, ctx):
    ctx.http.get.return_value = _mock_response(200, _FAKE_BREACHES)
    result = await source.fetch(_EMAIL, ctx)

    adobe = next(n for n in result.nodes if n.id == "breach:adobe")
    assert adobe.attrs["pwn_count"] == 152445165
    assert "Email addresses" in adobe.attrs["data_classes"]


# ---------------------------------------------------------------------------
# fetch() — 404 (no breaches)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_not_found_returns_email_node_only(source, ctx):
    ctx.http.get.return_value = _mock_response(404, None)
    result = await source.fetch(_EMAIL, ctx)

    assert len(result.nodes) == 1
    assert result.nodes[0].type == NodeType.EMAIL
    assert result.edges == []


@pytest.mark.asyncio
async def test_fetch_sends_api_key_header(source, ctx):
    ctx.http.get.return_value = _mock_response(404, None)
    await source.fetch(_EMAIL, ctx)

    call_kwargs = ctx.http.get.call_args
    headers = call_kwargs.kwargs.get("headers", {})
    assert headers.get("hibp-api-key") == "test-api-key"
