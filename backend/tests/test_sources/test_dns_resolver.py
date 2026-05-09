"""Tests for the dns_resolver source plugin."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from scout.models.domain import InputType, Mode, NodeType
from scout.sources.base import _REGISTRY, get_sources
from scout.sources.threat import dns_resolver as _mod
from scout.sources.threat.dns_resolver import DnsResolverSource

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def source() -> DnsResolverSource:
    return DnsResolverSource()


@pytest.fixture()
def fake_records() -> dict[str, list[str]]:
    return {
        "A": ["93.184.216.34"],
        "AAAA": ["2606:2800:220:1:248:1893:25c8:1946"],
        "MX": ["0 ."],
        "NS": ["a.iana-servers.net.", "b.iana-servers.net."],
        "TXT": ['"v=spf1 -all"'],
    }


def _make_query_mock(records: dict[str, list[str]]):
    async def _mock_query(domain: str, rtype: str) -> list[str]:
        return records.get(rtype, [])

    return _mock_query


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------


def test_dns_resolver_is_registered():
    assert "dns_resolver" in _REGISTRY


def test_dns_resolver_in_threat_sources():
    threat_domain = get_sources(mode=Mode.THREAT, input_type=InputType.DOMAIN)
    names = {s.name for s in threat_domain}
    assert "dns_resolver" in names


def test_dns_resolver_in_footprint_sources():
    footprint_domain = get_sources(mode=Mode.FOOTPRINT, input_type=InputType.DOMAIN)
    names = {s.name for s in footprint_domain}
    assert "dns_resolver" in names


def test_dns_resolver_not_for_email():
    email_sources = get_sources(input_type=InputType.EMAIL)
    names = {s.name for s in email_sources}
    assert "dns_resolver" not in names


# ---------------------------------------------------------------------------
# fetch() — structure
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_returns_source_result(source, fake_records):
    with patch.object(_mod, "_query", side_effect=_make_query_mock(fake_records)):
        result = await source.fetch("example.com", ctx=None)  # type: ignore[arg-type]
    assert result.source_name == "dns_resolver"


@pytest.mark.asyncio
async def test_fetch_includes_domain_node(source, fake_records):
    with patch.object(_mod, "_query", side_effect=_make_query_mock(fake_records)):
        result = await source.fetch("example.com", ctx=None)  # type: ignore[arg-type]
    domain_nodes = [n for n in result.nodes if n.type == NodeType.DOMAIN]
    assert len(domain_nodes) == 1
    assert domain_nodes[0].id == "domain:example.com"
    assert domain_nodes[0].label == "example.com"


@pytest.mark.asyncio
async def test_fetch_includes_dns_record_nodes(source, fake_records):
    with patch.object(_mod, "_query", side_effect=_make_query_mock(fake_records)):
        result = await source.fetch("example.com", ctx=None)  # type: ignore[arg-type]
    record_nodes = [n for n in result.nodes if n.type == NodeType.DNS_RECORD]
    record_types = {n.attrs["record_type"] for n in record_nodes}
    assert {"A", "AAAA", "MX", "NS", "TXT"}.issubset(record_types)


@pytest.mark.asyncio
async def test_fetch_promotes_a_records_to_ip_nodes(source, fake_records):
    with patch.object(_mod, "_query", side_effect=_make_query_mock(fake_records)):
        result = await source.fetch("example.com", ctx=None)  # type: ignore[arg-type]
    ip_nodes = [n for n in result.nodes if n.type == NodeType.IP]
    ip_values = {n.label for n in ip_nodes}
    assert "93.184.216.34" in ip_values
    assert "2606:2800:220:1:248:1893:25c8:1946" in ip_values


@pytest.mark.asyncio
async def test_fetch_edges_use_resolves_to_relation(source, fake_records):
    with patch.object(_mod, "_query", side_effect=_make_query_mock(fake_records)):
        result = await source.fetch("example.com", ctx=None)  # type: ignore[arg-type]
    relations = {e.relation for e in result.edges}
    assert relations == {"resolves_to"}


@pytest.mark.asyncio
async def test_fetch_all_edges_originate_from_domain(source, fake_records):
    with patch.object(_mod, "_query", side_effect=_make_query_mock(fake_records)):
        result = await source.fetch("example.com", ctx=None)  # type: ignore[arg-type]
    for edge in result.edges:
        assert edge.src_id == "domain:example.com"


@pytest.mark.asyncio
async def test_fetch_raw_contains_record_dict(source, fake_records):
    with patch.object(_mod, "_query", side_effect=_make_query_mock(fake_records)):
        result = await source.fetch("example.com", ctx=None)  # type: ignore[arg-type]
    assert result.raw["A"] == ["93.184.216.34"]
    assert "NS" in result.raw


# ---------------------------------------------------------------------------
# fetch() — graceful handling of empty / missing records
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_no_records_returns_domain_node_only(source):
    empty: dict[str, list[str]] = {"A": [], "AAAA": [], "MX": [], "NS": [], "TXT": []}
    with patch.object(_mod, "_query", side_effect=_make_query_mock(empty)):
        result = await source.fetch("empty.example.com", ctx=None)  # type: ignore[arg-type]
    assert len(result.nodes) == 1
    assert result.nodes[0].type == NodeType.DOMAIN
    assert result.edges == []


@pytest.mark.asyncio
async def test_fetch_partial_records(source):
    partial = {"A": ["1.2.3.4"], "AAAA": [], "MX": [], "NS": [], "TXT": ['"v=spf1 -all"']}
    with patch.object(_mod, "_query", side_effect=_make_query_mock(partial)):
        result = await source.fetch("partial.example.com", ctx=None)  # type: ignore[arg-type]
    ip_nodes = [n for n in result.nodes if n.type == NodeType.IP]
    assert len(ip_nodes) == 1
    assert ip_nodes[0].label == "1.2.3.4"
