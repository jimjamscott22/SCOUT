# SCOUT — Claude Code Working Notes

## Project
**SCOUT** (Self-audit & Cyber Observation Unified Toolkit) — a local-first OSINT toolkit for two workflows: auditing your own digital footprint, and investigating threat indicators.

Full roadmap and design: `docs/SCOUT_PROJECT_PLAN.md`.

## Status (as of Oct 2026)
Work happens directly on `main` (the old `feature/mvp-phase1` branch and worktree no longer exist).

**Phase 1 (MVP) is mostly complete:**
- Done: scaffold, domain models, ORM, config loader, TTL cache, rate limiter, orchestrator, source registry, FastAPI API, CLI (`serve`, `config show`, `config init`), 7 sources, React frontend scaffold. 162 tests pass.
- Remaining to close out Phase 1:
  - `ruff check .` and `mypy backend/` report errors (mostly fixable lint issues and missing test annotations)
  - Frontend `SourceStatus.tsx` component (which sources ran / hit / missed / errored) not yet written
  - `whois_rdap` threat source (in the plan's MVP list) not yet written
  - End-to-end smoke test of frontend against backend not yet done
  - FastAPI does not yet serve the built frontend (`frontend/dist`); run Vite separately for now
- Not started: Phase 2+ (SSE streaming, history browser, pivot, extra sources, export, AI summarization)

## Tech Stack

### Backend
- Python 3.12+, managed via `uv`
- FastAPI + Uvicorn (async HTTP)
- SQLAlchemy 2.x + SQLite (`~/.scout/scout.db`)
- `httpx` for async outbound requests
- `aiolimiter` for per-source rate limiting
- `dnspython` for the DNS resolver source
- `pydantic-settings` for config (`~/.scout/config.toml`)
- `typer` for the CLI

### Frontend
- React + Vite + TypeScript
- Tailwind CSS (dark terminal theme)
- Cytoscape.js for graph visualization
- TanStack Query for data fetching
- Vite dev server proxies `/api` to `http://127.0.0.1:8765`

## Package Layout
```
backend/
  scout/              # installable Python package
    cli.py            # typer app — entry point: scout.cli:app
    main.py           # FastAPI app
    config.py         # pydantic-settings, loads ~/.scout/config.toml
    db.py             # SQLAlchemy engine, session, init_db()
    cache.py          # TTL response cache (SQLite)
    rate_limit.py     # per-source aiolimiter wrapper
    orchestrator.py   # fan-out, caching, rate limiting, graph merge
    models/           # domain.py (dataclasses) + db.py (SQLAlchemy ORM)
    sources/          # base.py (protocol + registry) + implementations
      footprint/      # hibp, gravatar, github_user, crt_sh
      threat/         # virustotal, abuseipdb, dns_resolver
    api/              # routes_health, routes_sources, routes_investigate
  tests/              # mirrors package layout; sources in tests/test_sources/
frontend/             # Vite + React app (src/components, src/lib, src/types)
docs/                 # project plan, original Claude Code prompt, API key guide
.cursor/skills/       # scout-add-source, scout-app-review, scout-feature-planning
```

## API Endpoints
- `GET  /api/health`
- `GET  /api/sources`
- `POST /api/investigate`
- `GET  /api/investigations`
- `GET  /api/investigations/{id}`

## Key Architectural Decisions

### Plugin Registry
Every data source implements the `Source` protocol and registers via `@register`. The orchestrator queries the registry by `(mode, input_type)` and fans out fetches in parallel. Adding a new source = one file (see `.cursor/skills/scout-add-source`).

### Graph Model
All sources produce `Node` and `Edge` objects in a common normalized shape. Node types: `email`, `domain`, `ip`, `hash`, `url`, `breach`, `cert`, `repo`, `account`. Edge relations: `exposed_in`, `resolves_to`, `owns`, `references`, etc. Cytoscape renders the typed graph directly.

### TTL Cache
Every source response is cached in SQLite with a configurable TTL (breach data: 24h, DNS: 1h). This is the primary mechanism for protecting free-tier API quotas during development.

### Local-First
- Server binds to `127.0.0.1` only by default
- No auth layer in v1 (single-user)
- API keys in `~/.scout/config.toml` (chmod 600), never committed

## Dev Commands
```bash
uv sync --extra dev          # install deps (re-run if imports fail, e.g. missing dns / pytest-asyncio)
uv run scout serve           # start backend (127.0.0.1:8765)
uv run scout config init     # create ~/.scout/config.toml
uv run scout config show     # show effective config
uv run pytest                # run tests
uv run ruff check .          # lint
uv run ruff format --check . # format check
uv run mypy backend/         # type check

cd frontend
npm install
npm run dev                  # Vite dev server (proxies /api to backend)
npm run build                # tsc -b && vite build
```

## Phase Scope
Current focus: finish **Phase 1 (MVP)** — see Status above. Do NOT start Phase 2+ features (SSE streaming, history browser, pivot, extra sources, export, AI summarization) until Phase 1 is closed out.
