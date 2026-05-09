"""
Have I Been Pwned — breach lookup for an email address.

ToS / usage notes:
  - Requires a paid API key (~$4/month). Header: ``hibp-api-key``.
  - 404 means the email has not appeared in any known breach — not an error.
  - 429 means rate limited; the orchestrator's rate limiter should prevent this.
  - See https://haveibeenpwned.com/API/v3 for full docs.
"""

from __future__ import annotations

from scout.models.domain import Edge, InputType, Mode, Node, NodeType, SourceResult
from scout.sources.base import FetchContext, RateLimit, register

_API_BASE = "https://haveibeenpwned.com/api/v3"


@register
class HibpSource:
    """Look up data breaches for an email address via HIBP v3."""

    name = "haveibeenpwned"
    modes = {Mode.FOOTPRINT}
    accepts = {InputType.EMAIL}
    auth_required = True
    rate_limit = RateLimit(requests=10, window_seconds=60)

    async def fetch(self, target: str, ctx: FetchContext) -> SourceResult:
        result = SourceResult(source_name=self.name)
        api_key = ctx.api_keys.get(self.name, "")

        email_node = Node(
            id=f"email:{target}",
            type=NodeType.EMAIL,
            label=target,
            source_name=self.name,
        )
        result.nodes.append(email_node)

        resp = await ctx.http.get(
            f"{_API_BASE}/breachedaccount/{target}",
            headers={"hibp-api-key": api_key},
            params={"truncateResponse": "false"},
        )
        result.raw = {}

        if resp.status_code == 404:
            return result

        resp.raise_for_status()
        breaches = resp.json()
        result.raw = {"breaches": breaches}

        for breach in breaches:
            breach_name = breach.get("Name", "unknown").lower()
            breach_node = Node(
                id=f"breach:{breach_name}",
                type=NodeType.BREACH,
                label=breach.get("Title", breach_name),
                source_name=self.name,
                attrs={
                    "breach_date": breach.get("BreachDate", ""),
                    "pwn_count": breach.get("PwnCount", 0),
                    "data_classes": breach.get("DataClasses", []),
                    "domain": breach.get("Domain", ""),
                },
            )
            result.nodes.append(breach_node)
            result.edges.append(
                Edge(
                    src_id=email_node.id,
                    dst_id=breach_node.id,
                    relation="exposed_in",
                    source_name=self.name,
                )
            )

        return result
