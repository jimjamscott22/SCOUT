"""Tests for the GitHub user source plugin."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from scout.models.domain import InputType, Mode, NodeType
from scout.sources.base import _REGISTRY, FetchContext, get_sources
from scout.sources.footprint.github_user import GitHubUserSource

_USERNAME = "octocat"

_FAKE_USER = {
    "login": "octocat",
    "name": "The Octocat",
    "bio": "A mysterious octocat.",
    "public_repos": 8,
    "followers": 9000,
    "html_url": "https://github.com/octocat",
}

_FAKE_REPOS = [
    {
        "full_name": "octocat/Hello-World",
        "name": "Hello-World",
        "fork": False,
        "description": "My first repo!",
        "language": "Python",
        "stargazers_count": 42,
        "html_url": "https://github.com/octocat/Hello-World",
    },
    {
        "full_name": "octocat/forked-repo",
        "name": "forked-repo",
        "fork": True,  # should be excluded
        "description": "",
        "language": None,
        "stargazers_count": 0,
        "html_url": "https://github.com/octocat/forked-repo",
    },
]


@pytest.fixture()
def source() -> GitHubUserSource:
    return GitHubUserSource()


@pytest.fixture()
def ctx() -> FetchContext:
    http = AsyncMock()
    return FetchContext(http=http, api_keys={"github_user": "ghp_testtoken"})


def _mock_response(status: int, json_data) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status
    resp.json.return_value = json_data
    resp.raise_for_status = MagicMock()
    return resp


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------


def test_github_user_is_registered():
    assert "github_user" in _REGISTRY


def test_github_user_in_footprint_username_sources():
    sources = get_sources(mode=Mode.FOOTPRINT, input_type=InputType.USERNAME)
    assert any(s.name == "github_user" for s in sources)


def test_github_user_is_auth_required(source):
    assert source.auth_required


# ---------------------------------------------------------------------------
# fetch() — user and repos found
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_returns_account_node(source, ctx):
    ctx.http.get.side_effect = [
        _mock_response(200, _FAKE_USER),
        _mock_response(200, _FAKE_REPOS),
    ]
    result = await source.fetch(_USERNAME, ctx)

    account_nodes = [n for n in result.nodes if n.type == NodeType.ACCOUNT]
    assert len(account_nodes) == 1
    assert account_nodes[0].id == "account:github:octocat"
    assert account_nodes[0].label == "The Octocat"


@pytest.mark.asyncio
async def test_fetch_skips_forked_repos(source, ctx):
    ctx.http.get.side_effect = [
        _mock_response(200, _FAKE_USER),
        _mock_response(200, _FAKE_REPOS),
    ]
    result = await source.fetch(_USERNAME, ctx)

    repo_nodes = [n for n in result.nodes if n.type == NodeType.REPO]
    assert len(repo_nodes) == 1
    assert repo_nodes[0].id == "repo:github:octocat/hello-world"


@pytest.mark.asyncio
async def test_fetch_owns_edge_for_each_repo(source, ctx):
    ctx.http.get.side_effect = [
        _mock_response(200, _FAKE_USER),
        _mock_response(200, _FAKE_REPOS),
    ]
    result = await source.fetch(_USERNAME, ctx)

    assert len(result.edges) == 1
    assert result.edges[0].relation == "owns"
    assert result.edges[0].src_id == "account:github:octocat"


@pytest.mark.asyncio
async def test_fetch_account_attrs_populated(source, ctx):
    ctx.http.get.side_effect = [
        _mock_response(200, _FAKE_USER),
        _mock_response(200, _FAKE_REPOS),
    ]
    result = await source.fetch(_USERNAME, ctx)

    account = next(n for n in result.nodes if n.type == NodeType.ACCOUNT)
    assert account.attrs["platform"] == "github"
    assert account.attrs["followers"] == 9000


# ---------------------------------------------------------------------------
# fetch() — user not found
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_user_not_found_returns_empty(source, ctx):
    ctx.http.get.return_value = _mock_response(404, None)
    result = await source.fetch("nonexistent-user-xyz", ctx)

    assert result.nodes == []
    assert result.edges == []
