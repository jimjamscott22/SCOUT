"""Tests for the AbuseIPDB source plugin."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from scout.models.domain import InputType, Mode, NodeType
from scout.sources.base import _REGISTRY, FetchContext, get_sources
from scout.sources.threat.abuseipdb import AbuseIpDbSource

_IP = "198.51.100.1"

_FAKE_RESPONSE = {
    "data": {
        "ipAddress": _IP,
        "isPublic": True,
        "ipVersion": 4,
        "isWhitelisted": False,
        "abuseConfidenceScore": 87,
        "countryCode": "US",
        "usageType": "Data Center/Web Hosting/Transit",
        "isp": "Example ISP",
        "domain": "example.com",
        "isTor": False,
        "totalReports": 42,
        "numDistinctUsers": 10,
    }
}


@pytest.fixture()
def source() -> AbuseIpDbSource:
    return AbuseIpDbSource()


@pytest.fixture()
def ctx() -> FetchContext:
    http = AsyncMock()
    return FetchContext(http=http, api_keys={"abuseipdb": "test-api-key"})


def _mock_response(status: int, json_data: dict) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status
    resp.json.return_value = json_data
    resp.raise_for_status = MagicMock()
    return resp


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------


def test_abuseipdb_is_registered():
    assert "abuseipdb" in _REGISTRY


def test_abuseipdb_in_threat_ip_sources():
    sources = get_sources(mode=Mode.THREAT, input_type=InputType.IP)
    assert any(s.name == "abuseipdb" for s in sources)


def test_abuseipdb_is_auth_required(source):
    assert source.auth_required


# ---------------------------------------------------------------------------
# fetch() — IP data returned
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_returns_ip_node(source, ctx):
    ctx.http.get.return_value = _mock_response(200, _FAKE_RESPONSE)
    result = await source.fetch(_IP, ctx)

    ip_nodes = [n for n in result.nodes if n.type == NodeType.IP]
    assert len(ip_nodes) == 1
    assert ip_nodes[0].id == f"ip:{_IP}"
    assert ip_nodes[0].label == _IP


@pytest.mark.asyncio
async def test_fetch_ip_attrs_populated(source, ctx):
    ctx.http.get.return_value = _mock_response(200, _FAKE_RESPONSE)
    result = await source.fetch(_IP, ctx)

    ip_node = result.nodes[0]
    assert ip_node.attrs["abuse_confidence_score"] == 87
    assert ip_node.attrs["total_reports"] == 42
    assert ip_node.attrs["country_code"] == "US"
    assert ip_node.attrs["isp"] == "Example ISP"
    assert ip_node.attrs["is_tor"] is False


@pytest.mark.asyncio
async def test_fetch_no_edges_produced(source, ctx):
    ctx.http.get.return_value = _mock_response(200, _FAKE_RESPONSE)
    result = await source.fetch(_IP, ctx)
    assert result.edges == []


@pytest.mark.asyncio
async def test_fetch_sends_api_key_header(source, ctx):
    ctx.http.get.return_value = _mock_response(200, _FAKE_RESPONSE)
    await source.fetch(_IP, ctx)

    call_kwargs = ctx.http.get.call_args
    headers = call_kwargs.kwargs.get("headers", {})
    assert headers.get("Key") == "test-api-key"
