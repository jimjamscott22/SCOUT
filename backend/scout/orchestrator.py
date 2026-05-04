"""
Orchestrator — fans out fetches across registered sources in parallel,
integrates the cache and rate limiter, and merges results into a unified
deduplicated graph.

Usage::

    import httpx
    from scout.orchestrator import Orchestrator, OrchestratorResult
    from scout.cache import ResponseCache
    from scout.models.domain import Mode, InputType

    async with httpx.AsyncClient() as http:
        orch = Orchestrator(cache=cache)
        result = await orch.run(
            mode=Mode.THREAT,
            target="example.com",
            input_type=InputType.DOMAIN,
            http=http,
            api_keys={"virustotal": "abc123"},
        )
"""

from __future__ import annotations

import asyncio
import dataclasses
import json
from typing import Sequence

import httpx

from scout.cache import ResponseCache
from scout.models.domain import Edge, InputType, Mode, Node, SourceResult
from scout.rate_limit import get_limiter
from scout.sources.base import FetchContext, Source, get_sources

# TTL defaults per mode (seconds).  Callers can override via ttl_override.
_DEFAULT_TTL: dict[str, float] = {
    "dns_resolver": 3_600,       # 1 h
    "haveibeenpwned": 86_400,    # 24 h
    "gravatar": 86_400,
    "github_user": 3_600,
    "crt_sh": 86_400,
    "abuseipdb": 3_600,
    "virustotal": 3_600,
}
_FALLBACK_TTL: float = 3_600


@dataclasses.dataclass
class SourceRunResult:
    """Outcome of running one source against one target."""

    source_name: str
    status: str          # "ok" | "error" | "skipped" | "cache_hit"
    cache_hit: bool
    error_message: str | None
    nodes: list[Node]
    edges: list[Edge]


@dataclasses.dataclass
class OrchestratorResult:
    """Merged result of all source runs for a single investigation."""

    source_runs: list[SourceRunResult]
    nodes: list[Node]    # deduplicated by Node.id
    edges: list[Edge]    # deduplicated by (src_id, dst_id, relation)


def _request_key(input_type: InputType, target: str) -> str:
    return f"{input_type}:{target}"


def _merge(runs: list[SourceRunResult]) -> tuple[list[Node], list[Edge]]:
    """Deduplicate nodes and edges from all successful runs."""
    seen_nodes: dict[str, Node] = {}
    seen_edges: set[Edge] = set()

    for run in runs:
        if run.status not in ("ok", "cache_hit"):
            continue
        for node in run.nodes:
            if node.id not in seen_nodes:
                seen_nodes[node.id] = node
        for edge in run.edges:
            seen_edges.add(edge)

    return list(seen_nodes.values()), list(seen_edges)


class Orchestrator:
    """Coordinates parallel source fetches with caching and rate limiting."""

    def __init__(
        self,
        cache: ResponseCache | None = None,
        ttl_override: dict[str, float] | None = None,
    ) -> None:
        self._cache = cache
        self._ttl = {**_DEFAULT_TTL, **(ttl_override or {})}

    async def run(
        self,
        mode: Mode,
        target: str,
        input_type: InputType,
        http: httpx.AsyncClient,
        api_keys: dict[str, str] | None = None,
        source_names: Sequence[str] | None = None,
    ) -> OrchestratorResult:
        """Run all applicable sources and return the merged graph.

        Args:
            mode: Investigation mode (footprint or threat).
            target: The value to investigate (email, domain, IP, …).
            input_type: Declared type of *target*.
            http: Shared async HTTP client.
            api_keys: Flat dict ``{source_name: key}`` for auth-required sources.
            source_names: If provided, only run sources whose name is in this list.
        """
        sources = get_sources(mode=mode, input_type=input_type)
        if source_names is not None:
            name_set = set(source_names)
            sources = [s for s in sources if s.name in name_set]

        ctx = FetchContext(http=http, api_keys=api_keys or {})
        tasks = [self._run_one(src, target, input_type, ctx) for src in sources]
        runs: list[SourceRunResult] = await asyncio.gather(*tasks)

        nodes, edges = _merge(runs)
        return OrchestratorResult(source_runs=list(runs), nodes=nodes, edges=edges)

    async def _run_one(
        self,
        source: Source,
        target: str,
        input_type: InputType,
        ctx: FetchContext,
    ) -> SourceRunResult:
        # Skip auth-required sources with no key configured
        if source.auth_required and not ctx.api_keys.get(source.name):
            return SourceRunResult(
                source_name=source.name,
                status="skipped",
                cache_hit=False,
                error_message="api key not configured",
                nodes=[],
                edges=[],
            )

        req_key = _request_key(input_type, target)

        # Cache read
        if self._cache is not None:
            cached = self._cache.get(source.name, req_key)
            if cached is not None:
                sr = _deserialize(source.name, cached)
                return SourceRunResult(
                    source_name=source.name,
                    status="cache_hit",
                    cache_hit=True,
                    error_message=None,
                    nodes=sr.nodes,
                    edges=sr.edges,
                )

        # Live fetch (rate-limited)
        limiter = get_limiter(source.name, source.rate_limit)
        try:
            async with limiter:
                sr = await source.fetch(target, ctx)
        except Exception as exc:
            return SourceRunResult(
                source_name=source.name,
                status="error",
                cache_hit=False,
                error_message=str(exc),
                nodes=[],
                edges=[],
            )

        # Cache write
        if self._cache is not None:
            ttl = self._ttl.get(source.name, _FALLBACK_TTL)
            self._cache.set(source.name, req_key, _serialize(sr), ttl_seconds=ttl)

        return SourceRunResult(
            source_name=source.name,
            status="ok",
            cache_hit=False,
            error_message=None,
            nodes=sr.nodes,
            edges=sr.edges,
        )


# ---------------------------------------------------------------------------
# Serialization helpers for cache storage
# ---------------------------------------------------------------------------


def _serialize(sr: SourceResult) -> dict:
    return {
        "nodes": [
            {
                "id": n.id,
                "type": n.type,
                "label": n.label,
                "source_name": n.source_name,
                "attrs": n.attrs,
            }
            for n in sr.nodes
        ],
        "edges": [
            {
                "src_id": e.src_id,
                "dst_id": e.dst_id,
                "relation": e.relation,
                "source_name": e.source_name,
            }
            for e in sr.edges
        ],
    }


def _deserialize(source_name: str, data: dict) -> SourceResult:
    from scout.models.domain import Edge, Node, NodeType

    sr = SourceResult(source_name=source_name)
    for nd in data.get("nodes", []):
        sr.nodes.append(
            Node(
                id=nd["id"],
                type=NodeType(nd["type"]),
                label=nd["label"],
                source_name=nd.get("source_name", source_name),
                attrs=nd.get("attrs", {}),
            )
        )
    for ed in data.get("edges", []):
        sr.edges.append(
            Edge(
                src_id=ed["src_id"],
                dst_id=ed["dst_id"],
                relation=ed["relation"],
                source_name=ed.get("source_name", source_name),
            )
        )
    return sr
