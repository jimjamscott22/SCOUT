"""
Domain models for SCOUT.

All source plugins produce Node and Edge objects in this common normalized
shape. The orchestrator merges results by deduplicating on Node.id, which
is canonical: f"{type}:{value}".
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


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


@dataclass(frozen=True, eq=False)
class Node:
    """An immutable, hashable graph node.

    id is canonical: f"{type}:{value}", e.g. "email:jamie@example.com",
    "breach:adobe", "ip:1.2.3.4".  Two sources discovering the same entity
    produce equal ids and will be merged by the orchestrator.

    Equality and hashing are id-only so that two Node objects with the same id
    but different labels (e.g. enriched by different sources) deduplicate
    correctly in sets and dict keys.
    """

    id: str
    type: NodeType
    label: str
    source_name: str = ""
    attrs: dict[str, Any] = field(default_factory=dict, hash=False, compare=False)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Node):
            return NotImplemented
        return self.id == other.id

    def __hash__(self) -> int:
        return hash(self.id)


@dataclass(frozen=True)
class Edge:
    """An immutable, hashable directed graph edge between two nodes.

    Common relation values: exposed_in | owns | resolves_to | mx |
    registered_by | references | hosted_on | member_of

    source_name is excluded from equality and hash so that two edges with the
    same src/dst/relation discovered by different sources deduplicate as one.
    """

    src_id: str
    dst_id: str
    relation: str
    source_name: str = field(default="", compare=False, hash=False)


@dataclass
class SourceResult:
    """Mutable accumulator for the output of a single source plugin."""

    source_name: str
    nodes: list[Node] = field(default_factory=list)
    edges: list[Edge] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)
