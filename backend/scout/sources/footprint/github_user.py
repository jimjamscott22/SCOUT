"""
GitHub user source — user profile and public (non-fork) repositories.

ToS / usage notes:
  - Requires a personal access token (PAT). Header: ``Authorization: Bearer {token}``.
  - Without a token the orchestrator skips this source.
  - 404 means the username does not exist.
  - Free-tier rate limit: 5,000 requests/hour authenticated.
  - See https://docs.github.com/en/rest/users/users for API docs.
"""

from __future__ import annotations

from scout.models.domain import Edge, InputType, Mode, Node, NodeType, SourceResult
from scout.sources.base import FetchContext, RateLimit, register

_API_BASE = "https://api.github.com"
_HEADERS = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}


@register
class GitHubUserSource:
    """Fetch a GitHub user's profile and public repositories."""

    name = "github_user"
    modes = {Mode.FOOTPRINT}
    accepts = {InputType.USERNAME}
    auth_required = True
    rate_limit = RateLimit(requests=30, window_seconds=60)

    async def fetch(self, target: str, ctx: FetchContext) -> SourceResult:
        result = SourceResult(source_name=self.name)
        token = ctx.api_keys.get(self.name, "")
        headers = {**_HEADERS, "Authorization": f"Bearer {token}"}

        user_resp = await ctx.http.get(f"{_API_BASE}/users/{target}", headers=headers)
        if user_resp.status_code == 404:
            return result
        user_resp.raise_for_status()
        user_data = user_resp.json()

        account_node = Node(
            id=f"account:github:{target.lower()}",
            type=NodeType.ACCOUNT,
            label=user_data.get("name") or target,
            source_name=self.name,
            attrs={
                "platform": "github",
                "username": target,
                "bio": user_data.get("bio") or "",
                "public_repos": user_data.get("public_repos", 0),
                "followers": user_data.get("followers", 0),
                "profile_url": user_data.get("html_url", ""),
            },
        )
        result.nodes.append(account_node)

        repos_resp = await ctx.http.get(
            f"{_API_BASE}/users/{target}/repos",
            headers=headers,
            params={"per_page": 30, "sort": "updated"},
        )
        repos_resp.raise_for_status()
        repos = repos_resp.json()
        result.raw = {"user": user_data, "repos": repos}

        for repo in repos:
            if repo.get("fork"):
                continue  # only show repos the user owns
            full_name = repo.get("full_name", repo.get("name", ""))
            repo_node = Node(
                id=f"repo:github:{full_name.lower()}",
                type=NodeType.REPO,
                label=full_name,
                source_name=self.name,
                attrs={
                    "description": repo.get("description") or "",
                    "language": repo.get("language") or "",
                    "stars": repo.get("stargazers_count", 0),
                    "url": repo.get("html_url", ""),
                },
            )
            result.nodes.append(repo_node)
            result.edges.append(
                Edge(
                    src_id=account_node.id,
                    dst_id=repo_node.id,
                    relation="owns",
                    source_name=self.name,
                )
            )

        return result
