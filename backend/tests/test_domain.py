"""Tests for scout.models.domain."""

import pytest

from scout.models.domain import Edge, InputType, Mode, Node, NodeType, SourceResult


# ---------------------------------------------------------------------------
# Node equality and hashing
# ---------------------------------------------------------------------------


def test_node_same_id_different_label_are_equal():
    """Two Nodes with the same id but different labels must compare equal."""
    n1 = Node(id="email:a@b.com", type=NodeType.EMAIL, label="a@b.com")
    n2 = Node(id="email:a@b.com", type=NodeType.EMAIL, label="A@B.COM")
    assert n1 == n2


def test_node_same_id_different_label_same_hash():
    """Two Nodes with the same id must produce the same hash."""
    n1 = Node(id="email:a@b.com", type=NodeType.EMAIL, label="a@b.com")
    n2 = Node(id="email:a@b.com", type=NodeType.EMAIL, label="A@B.COM")
    assert hash(n1) == hash(n2)


def test_node_set_deduplicates_same_id():
    """A set must deduplicate nodes with the same id."""
    n1 = Node(id="email:a@b.com", type=NodeType.EMAIL, label="a@b.com")
    n2 = Node(id="email:a@b.com", type=NodeType.EMAIL, label="Different Label")
    result = {n1, n2}
    assert len(result) == 1


def test_node_different_ids_not_equal():
    """Two Nodes with different ids must not compare equal."""
    n1 = Node(id="email:a@b.com", type=NodeType.EMAIL, label="a@b.com")
    n2 = Node(id="email:x@y.com", type=NodeType.EMAIL, label="x@y.com")
    assert n1 != n2


def test_node_usable_in_set():
    """Node must be usable as a set element without raising TypeError."""
    n = Node(id="ip:1.2.3.4", type=NodeType.IP, label="1.2.3.4")
    s: set[Node] = set()
    s.add(n)  # must not raise
    assert n in s


# ---------------------------------------------------------------------------
# Edge equality and hashing
# ---------------------------------------------------------------------------


def test_edge_usable_in_set():
    """Edge must be usable as a set element without raising TypeError."""
    e = Edge(src_id="email:a@b.com", dst_id="breach:adobe", relation="exposed_in")
    s: set[Edge] = set()
    s.add(e)
    assert e in s


def test_edge_same_src_dst_relation_different_source_deduplicate():
    """Two edges with same src/dst/relation but different source_name must deduplicate."""
    e1 = Edge(src_id="email:a@b.com", dst_id="breach:adobe", relation="exposed_in", source_name="hibp")
    e2 = Edge(src_id="email:a@b.com", dst_id="breach:adobe", relation="exposed_in", source_name="other")
    assert e1 == e2
    assert hash(e1) == hash(e2)
    assert len({e1, e2}) == 1


def test_edge_different_relation_not_equal():
    """Two edges with different relations must not compare equal."""
    e1 = Edge(src_id="a", dst_id="b", relation="owns")
    e2 = Edge(src_id="a", dst_id="b", relation="resolves_to")
    assert e1 != e2


# ---------------------------------------------------------------------------
# StrEnum string values
# ---------------------------------------------------------------------------


def test_mode_footprint_string_value():
    assert Mode.FOOTPRINT == "footprint"


def test_mode_threat_string_value():
    assert Mode.THREAT == "threat"


def test_input_type_string_values():
    assert InputType.EMAIL == "email"
    assert InputType.USERNAME == "username"
    assert InputType.DOMAIN == "domain"
    assert InputType.IP == "ip"
    assert InputType.HASH == "hash"
    assert InputType.URL == "url"


def test_node_type_string_values():
    assert NodeType.EMAIL == "email"
    assert NodeType.BREACH == "breach"
    assert NodeType.DNS_RECORD == "dns_record"


# ---------------------------------------------------------------------------
# SourceResult defaults
# ---------------------------------------------------------------------------


def test_source_result_defaults_to_empty_lists_and_dict():
    result = SourceResult(source_name="test_source")
    assert result.nodes == []
    assert result.edges == []
    assert result.raw == {}


def test_source_result_stores_source_name():
    result = SourceResult(source_name="hibp")
    assert result.source_name == "hibp"
