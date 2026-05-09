"""
crt.sh — Certificate Transparency log lookup.

Queries crt.sh for all certificates that include the target domain as a
Subject Alternative Name (SAN) or Common Name (CN).

ToS / usage notes:
  - Public API run by Sectigo; no authentication required.
  - Returns an array of certificate entries in JSON when ?output=json is set.
  - Rate limit is conservative; crt.sh is a community resource.
"""

from __future__ import annotations

from scout.models.domain import Edge, InputType, Mode, Node, NodeType, SourceResult
from scout.sources.base import FetchContext, RateLimit, register


@register
class CrtShSource:
    """Look up Certificate Transparency log entries for a domain."""

    name = "crt_sh"
    modes = {Mode.FOOTPRINT}
    accepts = {InputType.DOMAIN}
    auth_required = False
    rate_limit = RateLimit(requests=10, window_seconds=60)

    async def fetch(self, target: str, ctx: FetchContext) -> SourceResult:
        result = SourceResult(source_name=self.name)

        domain_node = Node(
            id=f"domain:{target}",
            type=NodeType.DOMAIN,
            label=target,
            source_name=self.name,
        )
        result.nodes.append(domain_node)

        resp = await ctx.http.get(
            "https://crt.sh/",
            params={"q": target, "output": "json"},
        )
        resp.raise_for_status()
        entries = resp.json()
        result.raw = {"entries": entries}

        # Each entry's name_value may contain newline-separated SANs; deduplicate.
        seen: set[str] = set()
        for entry in entries:
            for cn in entry.get("name_value", "").splitlines():
                cn = cn.strip()
                if not cn or cn in seen:
                    continue
                seen.add(cn)

                cert_node = Node(
                    id=f"cert:{cn}",
                    type=NodeType.CERT,
                    label=cn,
                    source_name=self.name,
                    attrs={
                        "common_name": cn,
                        "issuer": entry.get("issuer_name", ""),
                        "not_before": entry.get("not_before", ""),
                        "not_after": entry.get("not_after", ""),
                    },
                )
                result.nodes.append(cert_node)
                result.edges.append(
                    Edge(
                        src_id=domain_node.id,
                        dst_id=cert_node.id,
                        relation="has_cert",
                        source_name=self.name,
                    )
                )

        return result
