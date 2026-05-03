"""
Domain models for SCOUT.

All source plugins produce Node and Edge objects in this common normalized
shape. The orchestrator merges results by deduplicating on Node.id, which
is canonical: f"{type}:{value}".
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class Mode(StrEnum):
    FOOTPRINT = "footprint"
    THREAT = "threat"


class InputType(StrEnum):
    EMAIL = "email"
    USERNAME = "username"
    DOMAIN = "domain"
    IP = "ip"
    HASH = "hash"
    URL = "url"


class NodeType(StrEnum):
    EMAIL = "email"
    USERNAME = "username"
    DOMAIN = "domain"
    IP = "ip"
    HASH = "hash"
    URL = "url"
    BREACH = "breach"
    ACCOUNT = "account"
    REPO = "repo"
    CERT = "cert"
    DNS_RECORD = "dns_record"


@dataclass(frozen=True)
class Node:
    """An immutable, hashable graph node.

    id is canonical: f"{type}:{value}", e.g. "email:jamie@example.com",
    "breach:adobe", "ip:1.2.3.4".  Two sources discovering the same entity
    produce equal ids and will be merged by the orchestrator.
    """

    id: str
    type: NodeType
    label: str
    attrs: dict = field(default_factory=dict)


@dataclass(frozen=True)
class Edge:
    """An immutable, hashable directed graph edge between two nodes.

    Common relation values: exposed_in | owns | resolves_to | mx |
    registered_by | references | hosted_on | member_of
    """

    src_id: str
    dst_id: str
    relation: str


@dataclass
class SourceResult:
    """Mutable accumulator for the output of a single source plugin."""

    source_name: str
    nodes: list[Node] = field(default_factory=list)
    edges: list[Edge] = field(default_factory=list)
    raw: dict = field(default_factory=dict)
