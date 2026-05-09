"""Tests for the crt.sh source plugin."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from scout.models.domain import InputType, Mode, NodeType
from scout.sources.base import _REGISTRY, FetchContext, get_sources
from scout.sources.footprint.crt_sh import CrtShSource

_DOMAIN = "example.com"

_FAKE_ENTRIES = [
    {
        "issuer_name": "C=US, O=Let's Encrypt, CN=R3",
        "common_name": "example.com",
        "name_value": "example.com\nwww.example.com",
        "not_before": "2024-01-01",
        "not_after": "2024-04-01",
    },
    {
        "issuer_name": "C=US, O=DigiCert",
        "common_name": "mail.example.com",
        "name_value": "mail.example.com",
        "not_before": "2024-02-01",
        "not_after": "2024-05-01",
    },
]


@pytest.fixture()
def source() -> CrtShSource:
    return CrtShSource()


@pytest.fixture()
def ctx() -> FetchContext:
    http = AsyncMock()
    return FetchContext(http=http, api_keys={})


def _mock_response(entries: list) -> MagicMock:
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = entries
    resp.raise_for_status = MagicMock()
    return resp


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------


def test_crt_sh_is_registered():
    assert "crt_sh" in _REGISTRY


def test_crt_sh_in_footprint_domain_sources():
    sources = get_sources(mode=Mode.FOOTPRINT, input_type=InputType.DOMAIN)
    assert any(s.name == "crt_sh" for s in sources)


def test_crt_sh_not_auth_required(source):
    assert not source.auth_required


# ---------------------------------------------------------------------------
# fetch() — entries found
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_returns_domain_node(source, ctx):
    ctx.http.get.return_value = _mock_response(_FAKE_ENTRIES)
    result = await source.fetch(_DOMAIN, ctx)

    domain_nodes = [n for n in result.nodes if n.type == NodeType.DOMAIN]
    assert len(domain_nodes) == 1
    assert domain_nodes[0].id == f"domain:{_DOMAIN}"


@pytest.mark.asyncio
async def test_fetch_returns_cert_nodes(source, ctx):
    ctx.http.get.return_value = _mock_response(_FAKE_ENTRIES)
    result = await source.fetch(_DOMAIN, ctx)

    cert_nodes = [n for n in result.nodes if n.type == NodeType.CERT]
    # 3 unique CNs: example.com, www.example.com, mail.example.com
    assert len(cert_nodes) == 3


@pytest.mark.asyncio
async def test_fetch_deduplicates_cns(source, ctx):
    # Duplicate CN across two entries
    entries = [
        {"name_value": "dupe.example.com", "issuer_name": "A", "not_before": "", "not_after": ""},
        {"name_value": "dupe.example.com", "issuer_name": "B", "not_before": "", "not_after": ""},
    ]
    ctx.http.get.return_value = _mock_response(entries)
    result = await source.fetch(_DOMAIN, ctx)

    cert_nodes = [n for n in result.nodes if n.type == NodeType.CERT]
    assert len(cert_nodes) == 1


@pytest.mark.asyncio
async def test_fetch_edges_use_has_cert_relation(source, ctx):
    ctx.http.get.return_value = _mock_response(_FAKE_ENTRIES)
    result = await source.fetch(_DOMAIN, ctx)

    relations = {e.relation for e in result.edges}
    assert relations == {"has_cert"}


@pytest.mark.asyncio
async def test_fetch_all_edges_originate_from_domain(source, ctx):
    ctx.http.get.return_value = _mock_response(_FAKE_ENTRIES)
    result = await source.fetch(_DOMAIN, ctx)

    for edge in result.edges:
        assert edge.src_id == f"domain:{_DOMAIN}"


# ---------------------------------------------------------------------------
# fetch() — empty response
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_no_entries_returns_domain_node_only(source, ctx):
    ctx.http.get.return_value = _mock_response([])
    result = await source.fetch(_DOMAIN, ctx)

    assert len(result.nodes) == 1
    assert result.nodes[0].type == NodeType.DOMAIN
    assert result.edges == []
