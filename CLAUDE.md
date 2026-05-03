# SCOUT — Claude Code Working Notes

## Project
**SCOUT** (Self-audit & Cyber Observation Unified Toolkit) — a local-first OSINT toolkit for two workflows: auditing your own digital footprint, and investigating threat indicators.

## Branch
`feature/mvp-phase1` (worktree at `.worktrees/mvp-phase1/`)

## Tech Stack

### Backend
- Python 3.12+, managed via `uv`
- FastAPI + Uvicorn (async HTTP)
- SQLAlchemy 2.x + SQLite (`~/.scout/scout.db`)
- `httpx` for async outbound requests
- `aiolimiter` for per-source rate limiting
- `pydantic-settings` for config (`~/.scout/config.toml`)
- `typer` for the CLI (`scout serve`, `scout config show`, etc.)

### Frontend
- React + Vite + TypeScript
- Tailwind CSS (dark terminal theme)
- Cytoscape.js for graph visualization
- TanStack Query for data fetching

## Package Layout
```
backend/
  scout/              # installable Python package
    cli.py            # typer app — entry point: scout.cli:app
    main.py           # FastAPI app
    config.py         # pydantic-settings, loads ~/.scout/config.toml
    db.py             # SQLAlchemy engine, session, init_db()
    models/           # domain dataclasses + SQLAlchemy ORM models
    sources/          # plugin registry + source implementations
      footprint/      # HIBP, Gravatar, GitHub, crt.sh, ...
      threat/         # VirusTotal, Shodan, WHOIS, passive DNS, ...
    api/              # FastAPI routers
  tests/
frontend/             # Vite + React app
```

## Key Architectural Decisions

### Plugin Registry
Every data source implements the `Source` protocol and registers via `@register`. The orchestrator queries the registry by `(mode, input_type)` and fans out fetches in parallel. Adding a new source = one file.

### Graph Model
All sources produce `Node` and `Edge` objects in a common normalized shape. Node types: `email`, `domain`, `ip`, `hash`, `url`, `breach`, `cert`, `repo`, `account`. Edge relations: `exposed_in`, `resolves_to`, `owns`, `references`, etc. Cytoscape renders the typed graph directly.

### TTL Cache
Every source response is cached in SQLite with a configurable TTL (breach data: 24h, WHOIS: 7d, DNS: 1h). This is the primary mechanism for protecting free-tier API quotas during development.

### Local-First
- Server binds to `127.0.0.1` only by default
- No auth layer in v1 (single-user)
- API keys in `~/.scout/config.toml` (chmod 600), never committed

## Dev Commands
```bash
uv sync --extra dev          # install deps
uv run scout serve           # start dev server
uv run pytest                # run tests
uv run ruff check .          # lint
uv run mypy backend/         # type check
```

## Phase Scope
This branch covers **Phase 1 (MVP)** only:
- Project scaffold and package structure
- Domain models and SQLAlchemy ORM
- Source registry and base protocol
- 2-3 footprint sources (HIBP, Gravatar, crt.sh)
- 2-3 threat sources (VirusTotal, WHOIS, DNS)
- FastAPI REST API with investigation endpoints
- React frontend with graph visualization (basic)
- CLI with `serve` and `config` commands

Do NOT implement Phase 2+ features (AI summarization, advanced sources, export, etc.).
