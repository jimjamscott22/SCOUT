"""
Gravatar profile lookup — hashes the email with MD5 and fetches the JSON profile.

ToS / usage notes:
  - Public JSON API, no authentication required.
  - 404 means no Gravatar account exists for this email — not an error.
  - Rate limit is conservative; Gravatar has no published limit but is CDN-backed.
"""

from __future__ import annotations

import hashlib

from scout.models.domain import Edge, InputType, Mode, Node, NodeType, SourceResult
from scout.sources.base import FetchContext, RateLimit, register


@register
class GravatarSource:
    """Look up a Gravatar profile for an email address."""

    name = "gravatar"
    modes = {Mode.FOOTPRINT}
    accepts = {InputType.EMAIL}
    auth_required = False
    rate_limit = RateLimit(requests=30, window_seconds=60)

    async def fetch(self, target: str, ctx: FetchContext) -> SourceResult:
        result = SourceResult(source_name=self.name)

        email_hash = hashlib.md5(target.strip().lower().encode()).hexdigest()

        email_node = Node(
            id=f"email:{target}",
            type=NodeType.EMAIL,
            label=target,
            source_name=self.name,
        )
        result.nodes.append(email_node)

        resp = await ctx.http.get(f"https://www.gravatar.com/{email_hash}.json")
        result.raw = {}

        if resp.status_code == 404:
            return result

        resp.raise_for_status()
        data = resp.json()
        result.raw = data

        entry = data.get("entry", [{}])[0]
        display_name = (
            entry.get("displayName")
            or entry.get("preferredUsername")
            or email_hash[:8]
        )

        account_node = Node(
            id=f"account:gravatar:{email_hash}",
            type=NodeType.ACCOUNT,
            label=display_name,
            source_name=self.name,
            attrs={
                "platform": "gravatar",
                "hash": email_hash,
                "profile_url": entry.get("profileUrl", ""),
                "about": entry.get("aboutMe", ""),
            },
        )
        result.nodes.append(account_node)
        result.edges.append(
            Edge(
                src_id=email_node.id,
                dst_id=account_node.id,
                relation="owns",
                source_name=self.name,
            )
        )

        return result
