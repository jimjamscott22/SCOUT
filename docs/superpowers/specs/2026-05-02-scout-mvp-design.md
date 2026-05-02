# SCOUT MVP — Design Spec

**Date:** 2026-05-02
**Status:** Approved
**Scope:** Phase 1 (MVP) only — no SSE streaming, no AI summarization, no export, no history UI

---

## 1. Overview

SCOUT is a local-first OSINT toolkit serving two workflows behind one interface:

- **Footprint mode** — user audits their own digital exposure (email, username, domain)
- **Threat mode** — user investigates indicators-of-compromise (IPs, domains) for security analysis

Both modes share one architecture: a pluggable async source registry, a normalized graph model (nodes + edges), and a Cytoscape-rendered React frontend.

**Package name:** `scout-toolkit` (PyPI-safe). CLI entry point: `scout`.
**Target platforms:** Windows, macOS, Linux (cross-platform from day one).

---

## 2. Architecture

Four layers:

1. **Browser** — React SPA.
   - Dev: Vite on `:5173`, proxies `/api/*` to FastAPI on `:8765` (HMR enabled)
   - Prod: FastAPI serves built `dist/` as static files from `:8765`

2. **FastAPI** — thin routing layer. Three route modules. All responses use Pydantic schemas — SQLAlchemy models are never exposed directly.

3. **Orchestrator** — core engine. Resolves sources for `(mode, input_type)`, fans out with `asyncio.gather`, checks cache, acquires rate-limit tokens, merges and deduplicates results, persists to DB.

4. **Shared infrastructure** — TTL cache (SQLite), per-source rate limiter (aiolimiter), config loader (pydantic-settings), DB engine + session factory.

**Cross-platform path handling:** all file paths use `pathlib.Path.home() / ".scout"`. The `chmod 600` advisory on `config.toml` is attempted on POSIX and silently skipped on Windows.

---

## 3. Domain Model

File: `backend/scout/models/domain.py`

```python
class Mode(StrEnum):       FOOTPRINT | THREAT
class InputType(StrEnum):  EMAIL | USERNAME | DOMAIN | IP | HASH | URL
class NodeType(StrEnum):   EMAIL | USERNAME | DOMAIN | IP | HASH | URL |
                           BREACH | ACCOUNT | REPO | CERT | DNS_RECORD

@dataclass(frozen=True)
class Node:
    id: str          # canonical: f"{type}:{value}"
    type: NodeType
    label: str
    attrs: dict

@dataclass(frozen=True)
class Edge:
    src_id: str
    dst_id: str
    relation: str    # exposed_in | owns | resolves_to | mx | registered_by | ...

@dataclass
class SourceResult:
    source_name: str
    nodes: list[Node]
    edges: list[Edge]
    raw: dict        # raw API response, used for caching
```

Node IDs are canonical and dedup-friendly: `"email:jamie@example.com"`, `"breach:adobe"`, `"ip:1.2.3.4"`.

---

## 4. Source Plugin Contract

File: `backend/scout/sources/base.py`

```python
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

def register(source_cls): ...          # decorator — instantiates and adds to REGISTRY
def sources_for(mode, input_type): ... # returns matching Source instances
```

**Skipping rule:** if `auth_required=True` and the API key is absent from config, `fetch()` returns an empty `SourceResult`. The orchestrator records `SourceRun.status = 'skipped'`. A skipped or erroring source never aborts the investigation.

---

## 5. MVP Sources (7)

| Source | Mode | Accepts | Key needed | Notes |
|---|---|---|---|---|
| `dns_resolver` | Threat | domain | No | Built first — vertical slice anchor |
| `hibp` | Footprint | email | Yes (~$4/mo) | 429-aware; `hibp-api-key` header |
| `gravatar` | Footprint | email | No | md5(email) → JSON; 404 → empty |
| `github_user` | Footprint | username | Yes (free PAT) | User node + repo nodes |
| `crt_sh` | Footprint | domain | No | CT log JSON endpoint |
| `abuseipdb` | Threat | ip | Yes (free) | `Key` header |
| `virustotal` | Threat | ip, domain | Yes (free) | `x-apikey` header |

---

## 6. Orchestrator

Function: `run_investigation(mode, target, target_type, db, selected_sources=None)`

1. Create `Investigation` row with `status='running'`
2. Resolve sources via `sources_for(mode, target_type)`, intersect with `selected_sources` if provided
3. `asyncio.gather` across all sources, each in a try/except:
   - Check cache by `(source_name, f"{target_type}:{target}")` — if hit and not expired, return cached `SourceResult`
   - Otherwise: acquire rate-limit token, call `source.fetch()`, write to cache with source's TTL
   - Record `SourceRun` row: `ok` / `error` / `skipped` / `cache_hit`
4. Merge all nodes (dedupe by `id`) and edges (dedupe by `(src_id, dst_id, relation)`)
5. Persist nodes + edges to DB
6. Mark investigation `status='complete'`, return assembled response

---

## 7. API (MVP — synchronous)

```
POST /api/investigate
  body:    { mode, target, target_type, sources?: [str] }
  returns: { investigation, source_runs, nodes, edges }

GET  /api/investigations/{id}
  returns: same shape as above

GET  /api/sources?mode=footprint|threat
  returns: [{ name, accepts, auth_required, configured }]

GET  /api/health
  returns: { status: "ok", db: "ok" }
```

All response models are Pydantic schemas. `POST /api/investigate` is synchronous for MVP — the frontend shows a spinner and waits. SSE streaming is Phase 2.

---

## 8. CLI

Framework: `typer`

- `scout serve [--host HOST] [--port PORT]` — starts uvicorn; default `127.0.0.1:8765`; binding to `0.0.0.0` prints a warning
- `scout config init` — writes template `~/.scout/config.toml` if absent; attempts `chmod 600` on POSIX, skips on Windows
- `scout config show` — prints loaded config with all API key values redacted as `***`

---

## 9. Database Schema

Raw SQL `init_db()` — no Alembic for MVP.

```sql
CREATE TABLE investigations (
    id              TEXT PRIMARY KEY,       -- uuid
    mode            TEXT NOT NULL,          -- footprint | threat
    target          TEXT NOT NULL,
    target_type     TEXT NOT NULL,
    created_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at    TIMESTAMP,
    status          TEXT NOT NULL DEFAULT 'running',  -- running|complete|failed
    note            TEXT
);

CREATE TABLE source_runs (
    id               TEXT PRIMARY KEY,
    investigation_id TEXT NOT NULL REFERENCES investigations(id) ON DELETE CASCADE,
    source_name      TEXT NOT NULL,
    started_at       TIMESTAMP NOT NULL,
    finished_at      TIMESTAMP,
    status           TEXT NOT NULL,         -- ok|error|skipped|cache_hit
    error_message    TEXT,
    cache_hit        BOOLEAN NOT NULL DEFAULT 0
);

CREATE TABLE nodes (
    id               TEXT NOT NULL,         -- "{type}:{value}"
    investigation_id TEXT NOT NULL REFERENCES investigations(id) ON DELETE CASCADE,
    type             TEXT NOT NULL,
    label            TEXT NOT NULL,
    attrs_json       TEXT NOT NULL DEFAULT '{}',
    discovered_by    TEXT NOT NULL,
    PRIMARY KEY (id, investigation_id)
);

CREATE TABLE edges (
    id               TEXT PRIMARY KEY,       -- uuid generated at persist time
    investigation_id TEXT NOT NULL REFERENCES investigations(id) ON DELETE CASCADE,
    src_node_id      TEXT NOT NULL,
    dst_node_id      TEXT NOT NULL,
    relation         TEXT NOT NULL,
    discovered_by    TEXT NOT NULL,
    UNIQUE(investigation_id, src_node_id, dst_node_id, relation)
);

CREATE TABLE response_cache (
    id            TEXT PRIMARY KEY,         -- hash(source_name + request_key)
    source_name   TEXT NOT NULL,
    request_key   TEXT NOT NULL,
    response_json TEXT NOT NULL,
    fetched_at    TIMESTAMP NOT NULL,
    expires_at    TIMESTAMP NOT NULL
);
CREATE INDEX idx_cache_expires ON response_cache(expires_at);
CREATE INDEX idx_cache_lookup  ON response_cache(source_name, request_key);
```

---

## 10. Configuration

File: `~/.scout/config.toml` (path resolved via `pathlib.Path.home()`):

```toml
[scout]
db_path = "~/.scout/scout.db"
host    = "127.0.0.1"
port    = 8765

[sources.hibp]
api_key = ""

[sources.virustotal]
api_key = ""

[sources.abuseipdb]
api_key = ""

[sources.github]
token = ""
```

Loaded by `pydantic-settings`. Missing keys → sources return `status='skipped'`.

---

## 11. Frontend

**Stack:** Vite + React + TypeScript + Tailwind CSS + Cytoscape.js + TanStack Query. Tailwind primitives only — no component library.

**Layout:**
- Header: `SCOUT` wordmark · mode toggle (segmented control: Footprint | Threat) · settings icon (no-op in MVP)
- Input bar: target-type dropdown (filtered by mode) · target input · Investigate button
- Results: two-pane layout

**Left pane — Cytoscape graph:**
- Nodes colored by type: breach=red, account/repo=blue, email=green accent, ip=amber accent
- Click a node → `NodeDetailPanel` overlay shows `attrs`
- Edges labeled by relation

**Right pane — Source status + node list:**
- Per-source status badge: `ok` / `skipped` / `cache` / `error`
- Flat scrollable node list, colored by type

**Theme:** `theme.css` defines CSS custom properties. `body.footprint` → `--accent: #00ff88`. `body.threat` → `--accent: #ffb000`. `ModeToggle` swaps the body class.

**State:** TanStack Query manages all API calls. On submit the form disables and shows a spinner; on success both panes populate simultaneously.

**5 components:** `ModeToggle`, `InvestigationForm`, `ResultsGraph`, `ResultsList`, `NodeDetailPanel`

---

## 12. Testing Strategy

- **Source tests:** one file per source in `tests/test_sources/`. HTTP fixtures recorded via `pytest-recording` (VCR.py), cassettes committed — tests run fully offline. Each test covers: correct node/edge types, `skipped` behavior when key absent, graceful 404/empty response.
- **Orchestrator tests:** fake source registry, no real HTTP. Covers: parallel fan-out, cache hit skips `fetch()`, source exception records `error` without aborting, node/edge deduplication, `selected_sources` filtering.
- **Cache tests:** in-memory SQLite. Covers: TTL expiry, fresh entry retrieval.
- **API tests:** FastAPI `TestClient` with in-memory SQLite + injected fake source registry.
- **Lint/types:** `ruff check`, `ruff format`, `mypy --strict` on the `scout` package.

No frontend tests in MVP.

---

## 13. Project Structure

```
scout/
├── pyproject.toml              # name: scout-toolkit, scripts: { scout = "scout.cli:app" }
├── README.md
├── CLAUDE.md
├── .gitignore
├── .python-version             # 3.12
├── backend/
│   ├── scout/
│   │   ├── __init__.py
│   │   ├── main.py             # FastAPI app, mounts frontend dist in prod
│   │   ├── cli.py              # typer: scout serve | config init | config show
│   │   ├── config.py           # pydantic-settings, Path.home() / ".scout"
│   │   ├── db.py               # engine, session factory, init_db()
│   │   ├── models/
│   │   │   ├── domain.py       # Mode, InputType, NodeType, Node, Edge, SourceResult
│   │   │   └── db.py           # SQLAlchemy: Investigation, SourceRun, NodeRow, EdgeRow, ResponseCache
│   │   ├── sources/
│   │   │   ├── base.py         # Source protocol, @register, REGISTRY, sources_for()
│   │   │   ├── footprint/
│   │   │   │   ├── hibp.py
│   │   │   │   ├── gravatar.py
│   │   │   │   ├── github_user.py
│   │   │   │   └── crt_sh.py
│   │   │   └── threat/
│   │   │       ├── abuseipdb.py
│   │   │       ├── virustotal.py
│   │   │       └── dns_resolver.py
│   │   ├── orchestrator.py
│   │   ├── cache.py
│   │   ├── rate_limit.py
│   │   └── api/
│   │       ├── routes_investigate.py
│   │       ├── routes_sources.py
│   │       └── routes_health.py
│   └── tests/
│       ├── conftest.py
│       ├── test_orchestrator.py
│       ├── test_cache.py
│       └── test_sources/
│           ├── test_dns_resolver.py
│           ├── test_gravatar.py
│           ├── test_hibp.py
│           ├── test_github_user.py
│           ├── test_crt_sh.py
│           ├── test_abuseipdb.py
│           └── test_virustotal.py
└── frontend/
    ├── package.json
    ├── tsconfig.json
    ├── vite.config.ts          # proxy /api → http://127.0.0.1:8765
    ├── tailwind.config.js
    ├── postcss.config.js
    ├── index.html
    └── src/
        ├── main.tsx
        ├── App.tsx
        ├── theme.css
        ├── components/
        │   ├── ModeToggle.tsx
        │   ├── InvestigationForm.tsx
        │   ├── ResultsGraph.tsx
        │   ├── ResultsList.tsx
        │   └── NodeDetailPanel.tsx
        ├── lib/
        │   ├── api.ts
        │   └── graph.ts        # nodes/edges → Cytoscape elements
        └── types/
            └── api.ts          # mirrors backend Pydantic schemas
```

---

## 14. Implementation Order

**Phase A — Foundation**
1. Scaffold: `pyproject.toml`, `.gitignore`, `.python-version`, `CLAUDE.md`
2. Domain models (`models/domain.py`)
3. DB models + `init_db()`
4. Config loader
5. Source protocol + registry
6. `cache.py` + `rate_limit.py` + tests

**Phase B — Vertical Slice (full stack, one source)**
7. `dns_resolver` + test
8. Orchestrator + tests
9. FastAPI routes (all 4 endpoints)
10. CLI (`scout serve`, `scout config init`, `scout config show`)
11. Frontend scaffold + theme
12. `ModeToggle` + `InvestigationForm`
13. `ResultsGraph` + `NodeDetailPanel`
14. `ResultsList` + source status

**Phase C — Expand to all 7 sources**
15–20. One source + test each: `gravatar`, `hibp`, `github_user`, `crt_sh`, `abuseipdb`, `virustotal`

**Phase D — Polish**
21. README
22. `ruff` + `mypy` final pass

---

## 15. Out of Scope (MVP)

- SSE streaming (Phase 2)
- AI/LLM summarization (Phase 4)
- Additional sources beyond the 7 listed
- Authentication or multi-user support
- Docker / CI configuration
- Export functionality
- Investigation history UI
- Frontend tests
