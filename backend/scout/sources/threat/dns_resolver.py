"""
DNS resolver source — resolves A, AAAA, MX, NS, TXT records for a domain.

ToS / usage notes:
  - Uses Python's standard ``dnspython`` library against system resolvers.
  - No third-party API; no auth required.
  - Rate limit is conservative to avoid hammering upstream resolvers.
"""

from __future__ import annotations

import asyncio

import dns.asyncresolver
import dns.exception
import dns.rdatatype

from scout.models.domain import Edge, InputType, Mode, Node, NodeType, SourceResult
from scout.sources.base import FetchContext, RateLimit, register

_RECORD_TYPES = ("A", "AAAA", "MX", "NS", "TXT")

# Timeout per record-type query (seconds)
_QUERY_TIMEOUT = 5.0


async def _query(domain: str, rtype: str) -> list[str]:
    """Return string representations of all records of *rtype* for *domain*.

    Returns an empty list on NXDOMAIN, NoAnswer, or timeout — callers treat
    any absence of records as a normal (non-error) result.
    """
    try:
        resolver = dns.asyncresolver.Resolver()
        resolver.lifetime = _QUERY_TIMEOUT
        answer = await resolver.resolve(domain, rtype)
        return [str(r) for r in answer]
    except (TimeoutError, dns.exception.DNSException):
        return []


def _make_record_node(domain: str, rtype: str, value: str) -> Node:
    node_id = f"dns_record:{rtype}:{domain}:{value}"
    return Node(
        id=node_id,
        type=NodeType.DNS_RECORD,
        label=f"{rtype} {value}",
        source_name="dns_resolver",
        attrs={"record_type": rtype, "value": value, "domain": domain},
    )


@register
class DnsResolverSource:
    """Resolve common DNS record types for a domain target."""

    name = "dns_resolver"
    modes = {Mode.THREAT, Mode.FOOTPRINT}
    accepts = {InputType.DOMAIN}
    auth_required = False
    rate_limit = RateLimit(requests=30, window_seconds=60)

    async def fetch(self, target: str, ctx: FetchContext) -> SourceResult:
        result = SourceResult(source_name=self.name)

        domain_node = Node(
            id=f"domain:{target}",
            type=NodeType.DOMAIN,
            label=target,
            source_name=self.name,
        )
        result.nodes.append(domain_node)

        records: dict[str, list[str]] = {}
        tasks = {rtype: _query(target, rtype) for rtype in _RECORD_TYPES}
        resolved = await asyncio.gather(*tasks.values(), return_exceptions=False)
        for rtype, values in zip(tasks.keys(), resolved, strict=True):
            records[rtype] = values

        result.raw = records

        for rtype, values in records.items():
            for value in values:
                record_node = _make_record_node(target, rtype, value)
                result.nodes.append(record_node)
                result.edges.append(
                    Edge(
                        src_id=domain_node.id,
                        dst_id=record_node.id,
                        relation="resolves_to",
                        source_name=self.name,
                    )
                )

                # Promote A/AAAA values to first-class IP nodes with an extra edge
                if rtype in ("A", "AAAA"):
                    ip_node = Node(
                        id=f"ip:{value}",
                        type=NodeType.IP,
                        label=value,
                        source_name=self.name,
                    )
                    result.nodes.append(ip_node)
                    result.edges.append(
                        Edge(
                            src_id=domain_node.id,
                            dst_id=ip_node.id,
                            relation="resolves_to",
                            source_name=self.name,
                        )
                    )

        return result
