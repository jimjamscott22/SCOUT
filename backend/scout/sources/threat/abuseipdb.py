"""
AbuseIPDB — IP address reputation and abuse report lookup.

ToS / usage notes:
  - Requires a free API key. Header: ``Key: {api_key}``.
  - Free tier: 1,000 checks/day.
  - See https://docs.abuseipdb.com/#check-endpoint for API docs.
"""

from __future__ import annotations

from scout.models.domain import InputType, Mode, Node, NodeType, SourceResult
from scout.sources.base import FetchContext, RateLimit, register

_API_BASE = "https://api.abuseipdb.com/api/v2"


@register
class AbuseIpDbSource:
    """Look up abuse reports and reputation score for an IP address."""

    name = "abuseipdb"
    modes = {Mode.THREAT}
    accepts = {InputType.IP}
    auth_required = True
    rate_limit = RateLimit(requests=60, window_seconds=60)

    async def fetch(self, target: str, ctx: FetchContext) -> SourceResult:
        result = SourceResult(source_name=self.name)
        api_key = ctx.api_keys.get(self.name, "")

        resp = await ctx.http.get(
            f"{_API_BASE}/check",
            headers={"Key": api_key, "Accept": "application/json"},
            params={"ipAddress": target, "maxAgeInDays": "90"},
        )
        resp.raise_for_status()
        data = resp.json()
        result.raw = data

        report = data.get("data", {})
        ip_node = Node(
            id=f"ip:{target}",
            type=NodeType.IP,
            label=target,
            source_name=self.name,
            attrs={
                "abuse_confidence_score": report.get("abuseConfidenceScore", 0),
                "total_reports": report.get("totalReports", 0),
                "country_code": report.get("countryCode", ""),
                "isp": report.get("isp", ""),
                "domain": report.get("domain", ""),
                "usage_type": report.get("usageType", ""),
                "is_tor": report.get("isTor", False),
                "is_public": report.get("isPublic", True),
            },
        )
        result.nodes.append(ip_node)

        return result
