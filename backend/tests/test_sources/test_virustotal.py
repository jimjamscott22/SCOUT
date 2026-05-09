"""Tests for the VirusTotal source plugin."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from scout.models.domain import InputType, Mode, NodeType
from scout.sources.base import _REGISTRY, FetchContext, get_sources
from scout.sources.threat.virustotal import VirusTotalSource

_IP = "8.8.8.8"
_DOMAIN = "example.com"

_FAKE_IP_RESPONSE = {
    "data": {
        "id": _IP,
        "type": "ip_address",
        "attributes": {
            "last_analysis_stats": {
                "malicious": 3,
                "suspicious": 1,
                "harmless": 70,
                "undetected": 10,
            },
            "reputation": -5,
            "country": "US",
            "as_owner": "GOOGLE",
        },
    }
}

_FAKE_DOMAIN_RESPONSE = {
    "data": {
        "id": _DOMAIN,
        "type": "domain",
        "attributes": {
            "last_analysis_stats": {
                "malicious": 0,
                "suspicious": 0,
                "harmless": 80,
                "undetected": 5,
            },
            "reputation": 10,
            "country": "",
            "as_owner": "",
        },
    }
}


@pytest.fixture()
def source() -> VirusTotalSource:
    return VirusTotalSource()


@pytest.fixture()
def ctx() -> FetchContext:
    http = AsyncMock()
    return FetchContext(http=http, api_keys={"virustotal": "test-api-key"})


def _mock_response(status: int, json_data: dict) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status
    resp.json.return_value = json_data
    resp.raise_for_status = MagicMock()
    return resp


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------


def test_virustotal_is_registered():
    assert "virustotal" in _REGISTRY


def test_virustotal_in_threat_ip_sources():
    sources = get_sources(mode=Mode.THREAT, input_type=InputType.IP)
    assert any(s.name == "virustotal" for s in sources)


def test_virustotal_in_threat_domain_sources():
    sources = get_sources(mode=Mode.THREAT, input_type=InputType.DOMAIN)
    assert any(s.name == "virustotal" for s in sources)


def test_virustotal_is_auth_required(source):
    assert source.auth_required


# ---------------------------------------------------------------------------
# fetch() — IP target
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_ip_returns_ip_node(source, ctx):
    ctx.http.get.return_value = _mock_response(200, _FAKE_IP_RESPONSE)
    result = await source.fetch(_IP, ctx)

    ip_nodes = [n for n in result.nodes if n.type == NodeType.IP]
    assert len(ip_nodes) == 1
    assert ip_nodes[0].id == f"ip:{_IP}"


@pytest.mark.asyncio
async def test_fetch_ip_attrs_populated(source, ctx):
    ctx.http.get.return_value = _mock_response(200, _FAKE_IP_RESPONSE)
    result = await source.fetch(_IP, ctx)

    node = result.nodes[0]
    assert node.attrs["malicious"] == 3
    assert node.attrs["suspicious"] == 1
    assert node.attrs["reputation"] == -5
    assert node.attrs["as_owner"] == "GOOGLE"


# ---------------------------------------------------------------------------
# fetch() — domain target
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_domain_returns_domain_node(source, ctx):
    ctx.http.get.return_value = _mock_response(200, _FAKE_DOMAIN_RESPONSE)
    result = await source.fetch(_DOMAIN, ctx)

    domain_nodes = [n for n in result.nodes if n.type == NodeType.DOMAIN]
    assert len(domain_nodes) == 1
    assert domain_nodes[0].id == f"domain:{_DOMAIN}"


@pytest.mark.asyncio
async def test_fetch_domain_attrs_populated(source, ctx):
    ctx.http.get.return_value = _mock_response(200, _FAKE_DOMAIN_RESPONSE)
    result = await source.fetch(_DOMAIN, ctx)

    node = result.nodes[0]
    assert node.attrs["malicious"] == 0
    assert node.attrs["harmless"] == 80


# ---------------------------------------------------------------------------
# fetch() — 404 (unknown target)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_not_found_returns_empty(source, ctx):
    ctx.http.get.return_value = _mock_response(404, {})
    result = await source.fetch(_IP, ctx)

    assert result.nodes == []
    assert result.edges == []


@pytest.mark.asyncio
async def test_fetch_sends_api_key_header(source, ctx):
    ctx.http.get.return_value = _mock_response(200, _FAKE_IP_RESPONSE)
    await source.fetch(_IP, ctx)

    call_kwargs = ctx.http.get.call_args
    headers = call_kwargs.kwargs.get("headers", {})
    assert headers.get("x-apikey") == "test-api-key"
