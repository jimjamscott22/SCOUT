"""
VirusTotal — IP address and domain reputation lookup.

ToS / usage notes:
  - Requires a free API key. Header: ``x-apikey: {api_key}``.
  - Free tier: 4 lookups/minute, 500/day.
  - See https://developers.virustotal.com/reference/overview for API docs.
"""

from __future__ import annotations

import ipaddress

from scout.models.domain import InputType, Mode, Node, NodeType, SourceResult
from scout.sources.base import FetchContext, RateLimit, register

_API_BASE = "https://www.virustotal.com/api/v3"


def _is_ip(target: str) -> bool:
    try:
        ipaddress.ip_address(target)
        return True
    except ValueError:
        return False


@register
class VirusTotalSource:
    """Look up threat intelligence for an IP address or domain via VirusTotal."""

    name = "virustotal"
    modes = {Mode.THREAT}
    accepts = {InputType.IP, InputType.DOMAIN}
    auth_required = True
    rate_limit = RateLimit(requests=4, window_seconds=60)

    async def fetch(self, target: str, ctx: FetchContext) -> SourceResult:
        result = SourceResult(source_name=self.name)
        api_key = ctx.api_keys.get(self.name, "")

        if _is_ip(target):
            url = f"{_API_BASE}/ip_addresses/{target}"
            node_type = NodeType.IP
            node_id = f"ip:{target}"
        else:
            url = f"{_API_BASE}/domains/{target}"
            node_type = NodeType.DOMAIN
            node_id = f"domain:{target}"

        resp = await ctx.http.get(url, headers={"x-apikey": api_key})
        if resp.status_code == 404:
            return result
        resp.raise_for_status()

        data = resp.json()
        result.raw = data

        attrs_data = data.get("data", {}).get("attributes", {})
        stats = attrs_data.get("last_analysis_stats", {})

        node = Node(
            id=node_id,
            type=node_type,
            label=target,
            source_name=self.name,
            attrs={
                "malicious": stats.get("malicious", 0),
                "suspicious": stats.get("suspicious", 0),
                "harmless": stats.get("harmless", 0),
                "undetected": stats.get("undetected", 0),
                "reputation": attrs_data.get("reputation", 0),
                "country": attrs_data.get("country", ""),
                "as_owner": attrs_data.get("as_owner", ""),
            },
        )
        result.nodes.append(node)

        return result
