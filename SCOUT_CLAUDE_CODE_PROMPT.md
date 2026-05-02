# Claude Code Starter Prompt — SCOUT MVP

> Paste this into a fresh Claude Code session in an empty `scout/` directory. It's scoped to **Phase 1 (MVP)** only — do not implement Phase 2+ features.

---

## Context

You are bootstrapping **SCOUT**, a local-first unified OSINT toolkit. It serves two workflows behind one interface:

1. **Footprint mode** — user audits their own digital exposure (their email, their domain, their GitHub username)
2. **Threat mode** — user investigates indicators-of-compromise (IPs, domains, hashes) for security analysis

Both modes share one architecture: a pluggable async source registry, a normalized graph model (nodes + edges), and a Cytoscape-rendered frontend.

Read `PROJECT_PLAN.md` (in the repo root — I'll add it before you start) for the full spec. Your job for this session is **Phase 1 (MVP) only**.

## Tech stack (non-negotiable)

- **Backend**: Python 3.12+, FastAPI, SQLAlchemy 2.x, SQLite, `httpx` (async), `aiolimiter`, `pydantic-settings`, `typer`
- **Frontend**: Vite + React + TypeScript + Tailwind CSS + Cytoscape.js + TanStack Query
- **Package management**: `uv` for Python, `npm` for frontend
- **Dev environment**: macOS + Linux (Raspberry Pi compatible — no native deps that break on ARM)

## Aesthetic

Dark terminal theme. CSS variables for two accent palettes:
- Footprint mode: `--accent: #00ff88` (terminal green) on near-black background
- Threat mode: `--accent: #ffb000` (amber)

Mode toggle in the header swaps the active palette via a CSS class on `<body>`. Monospace headings (JetBrains Mono or Berkeley Mono fallback to ui-monospace), inter for body.

## Project structure to create

```
scout/
├── pyproject.toml
├── README.md
├── CLAUDE.md
├── PROJECT_PLAN.md          (I'll provide this)
├── .gitignore
├── .python-version          (3.12)
├── backend/
│   ├── scout/
│   │   ├── __init__.py
│   │   ├── main.py          # FastAPI app, mounts frontend dist in prod
│   │   ├── cli.py           # `scout serve`, `scout config show`
│   │   ├── config.py        # Pydantic Settings, loads ~/.scout/config.toml
│   │   ├── db.py            # Engine, session, init_db()
│   │   ├── models/
│   │   │   ├── __init__.py
│   │   │   ├── domain.py    # Mode, InputType, Node, Edge, SourceResult dataclasses
│   │   │   └── db.py        # SQLAlchemy: Investigation, SourceRun, NodeRow, EdgeRow, ResponseCache
│   │   ├── sources/
│   │   │   ├── __init__.py
│   │   │   ├── base.py      # Source protocol, @register decorator, REGISTRY
│   │   │   ├── footprint/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── hibp.py
│   │   │   │   ├── gravatar.py
│   │   │   │   └── github_user.py
│   │   │   └── threat/
│   │   │       ├── __init__.py
│   │   │       ├── abuseipdb.py
│   │   │       ├── virustotal.py
│   │   │       └── dns_resolver.py
│   │   ├── orchestrator.py  # run_investigation(): fan-out, cache, rate limit, graph merge
│   │   ├── cache.py         # get_cached / put_cached with TTL
│   │   ├── rate_limit.py    # per-source aiolimiter instances
│   │   └── api/
│   │       ├── __init__.py
│   │       ├── routes_investigate.py
│   │       ├── routes_sources.py
│   │       └── routes_health.py
│   └── tests/
│       ├── conftest.py
│       ├── test_orchestrator.py
│       ├── test_cache.py
│       └── test_sources/
│           └── test_gravatar.py    # one example source test with VCR
└── frontend/
    ├── package.json
    ├── tsconfig.json
    ├── vite.config.ts       # proxy /api -> http://127.0.0.1:8765
    ├── tailwind.config.js
    ├── postcss.config.js
    ├── index.html
    └── src/
        ├── main.tsx
        ├── App.tsx
        ├── theme.css        # dark terminal + mode palettes
        ├── components/
        │   ├── ModeToggle.tsx
        │   ├── InvestigationForm.tsx
        │   ├── ResultsGraph.tsx
        │   ├── ResultsList.tsx
        │   └── SourceStatus.tsx
        ├── lib/
        │   ├── api.ts
        │   └── graph.ts
        └── types/
            └── api.ts
```

## Domain model (implement exactly this)

```python
# backend/scout/models/domain.py
from dataclasses import dataclass, field
from enum import StrEnum

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

@dataclass(frozen=True)
class Node:
    id: str           # canonical: f"{type}:{value}"
    type: NodeType
    label: str
    attrs: dict = field(default_factory=dict)

@dataclass(frozen=True)
class Edge:
    src_id: str
    dst_id: str
    relation: str

@dataclass
class SourceResult:
    source_name: str
    nodes: list[Node]
    edges: list[Edge]
    raw: dict             # the raw API response, for debugging / cache
```

## Source protocol (implement exactly this)

```python
# backend/scout/sources/base.py
from typing import Protocol, runtime_checkable
from ..models.domain import Mode, InputType, SourceResult

@runtime_checkable
class Source(Protocol):
    name: str
    modes: set[Mode]
    accepts: set[InputType]
    auth_required: bool
    cache_ttl_seconds: int
    rate_limit_per_minute: int

    async def fetch(self, target: str, target_type: InputType) -> SourceResult: ...

REGISTRY: dict[str, Source] = {}

def register(source_cls):
    instance = source_cls()
    REGISTRY[instance.name] = instance
    return source_cls

def sources_for(mode: Mode, input_type: InputType) -> list[Source]:
    return [s for s in REGISTRY.values() if mode in s.modes and input_type in s.accepts]
```

## Orchestrator behavior (specify)

`run_investigation(mode, target, target_type, db, selected_sources=None)`:

1. Create an `Investigation` row with status='running'
2. Resolve sources via `sources_for(mode, target_type)`, intersected with `selected_sources` if given
3. For each source, in parallel via `asyncio.gather`:
   - Check cache via `(source.name, f"{target_type}:{target}")` — if hit and not expired, return cached `SourceResult`
   - Otherwise acquire rate-limit token, call `source.fetch()`, store in cache with TTL
   - Wrap each call in try/except — one source failing must not kill the investigation
   - Record a `SourceRun` row (ok / error / cache_hit)
4. Merge all `SourceResult.nodes` and `.edges` — dedupe nodes by id, dedupe edges by `(src, dst, relation)`
5. Persist nodes and edges
6. Mark investigation status='complete', return assembled response

## API contract (MVP)

```
POST /api/investigate
  body: { "mode": "footprint", "target": "user@example.com", "target_type": "email", "sources": null }
  returns: {
    "investigation": { id, mode, target, target_type, status, created_at, completed_at },
    "source_runs":   [{ source_name, status, error_message, cache_hit, started_at, finished_at }],
    "nodes":         [{ id, type, label, attrs, discovered_by }],
    "edges":         [{ src_id, dst_id, relation, discovered_by }]
  }

GET /api/investigations/{id}     -> same shape as above
GET /api/sources?mode=footprint  -> [{ name, accepts, auth_required, configured }]
GET /api/health                  -> { "status": "ok", "db": "ok" }
```

MVP returns synchronously (no SSE — that's Phase 2). The frontend shows a spinner during the request.

## Source implementations for MVP

Implement these six. **For any source requiring an API key that isn't configured, the source must return an empty SourceResult and the SourceRun records status='skipped' with a clear error message — never crash the investigation.**

### Footprint
- **`hibp.py`** — `https://haveibeenpwned.com/api/v3/breachedaccount/{email}?truncateResponse=false`. Header `hibp-api-key`, `user-agent: scout-osint`. 429-aware. Each breach → `BREACH` node, edge `email --exposed_in--> breach`.
- **`gravatar.py`** — md5 the email lowercased, GET `https://en.gravatar.com/{hash}.json`. 404 means no profile (return empty, not error). Profile → `ACCOUNT` node with display name + linked URLs.
- **`github_user.py`** — `https://api.github.com/users/{username}` and `/users/{username}/repos?per_page=30`. Token via `Authorization: Bearer`. User → `ACCOUNT` node. Each repo → `REPO` node, edge `username --owns--> repo`.

### Threat
- **`abuseipdb.py`** — `https://api.abuseipdb.com/api/v2/check?ipAddress={ip}&maxAgeInDays=90`. Header `Key`. Returns `IP` node with attrs `{abuseConfidenceScore, countryCode, isp, totalReports}`.
- **`virustotal.py`** — `https://www.virustotal.com/api/v3/ip_addresses/{ip}` (and `/domains/{domain}` if target_type is domain). Header `x-apikey`. Adds attrs to the IP/domain node: `{malicious_count, suspicious_count, harmless_count, reputation}`.
- **`dns_resolver.py`** — Use `dnspython` (async via `dns.asyncresolver`). Resolve A, AAAA, MX, NS, TXT for a domain. Each unique IP → `IP` node, edge `domain --resolves_to--> ip`. Each MX → `DOMAIN` node, edge `domain --mx--> domain`. **No API key needed** — this one always works in tests.

## Configuration

`~/.scout/config.toml`:

```toml
[scout]
db_path = "~/.scout/scout.db"
host = "127.0.0.1"
port = 8765

[sources.hibp]
api_key = ""

[sources.virustotal]
api_key = ""

[sources.abuseipdb]
api_key = ""

[sources.github]
token = ""
```

`scout config show` prints the loaded config with API keys redacted. `scout config init` writes a template if the file doesn't exist.

## Frontend MVP

- Header: app name "SCOUT" in monospace, mode toggle (segmented control: Footprint | Threat), settings icon (no-op for MVP)
- Main view: input form (target type dropdown filtered by mode, target input, "Investigate" button)
- On submit: POST to `/api/investigate`, show spinner, render results
- Results view, two-pane:
  - Left: Cytoscape graph. Color nodes by type. Click a node to highlight its edges and show attrs in a side panel.
  - Right: Source status (which sources ran, hit/miss/skipped/error) and a flat list of nodes
- All API calls via TanStack Query

Keep components small. Don't pull in a UI library — Tailwind primitives only. No shadcn for MVP.

## Quality bar

- All backend code is async where it touches I/O
- All Pydantic models on the API boundary; never expose SQLAlchemy models directly
- Type hints everywhere (`from __future__ import annotations` at the top of every Python file)
- One pytest test per source plus orchestrator + cache tests; use VCR/`pytest-recording` for HTTP fixtures so tests are offline
- `ruff check` and `ruff format` clean; `mypy --strict` on the `scout` package
- README has: install steps (`uv tool install .`), `scout config init`, `scout serve`, then visit `http://127.0.0.1:8765`

## What NOT to do in this session

- No SSE streaming (Phase 2)
- No AI/LLM integration (Phase 4)
- No additional sources beyond the 6 listed
- No authentication, no multi-user
- No Docker, no CI workflows
- No export functionality
- No investigation history UI (the data is stored, just no browser yet)

## Suggested order of work

1. Scaffold structure, `pyproject.toml`, `.gitignore`, `CLAUDE.md`
2. Domain models + DB models + migrations (raw SQL `init_db()` is fine — no Alembic)
3. Source protocol + registry
4. Cache + rate limit modules with tests
5. `dns_resolver` source first (no API key, easy to test)
6. Orchestrator with tests against `dns_resolver` + a fake source
7. Remaining 5 sources, each with a test
8. FastAPI routes
9. CLI (`scout serve`, `scout config show`, `scout config init`)
10. Frontend scaffold, mode toggle, form
11. Cytoscape graph component
12. Source status panel + results list
13. README

After each major step, run tests and confirm before moving on. When you finish the MVP, summarize what's built and what Phase 2 would tackle next.

---
