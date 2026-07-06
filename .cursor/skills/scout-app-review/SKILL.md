---
name: scout-app-review
description: >-
  Reviews the SCOUT OSINT toolkit (FastAPI backend + React/Cytoscape frontend)
  and suggests prioritized improvements or MVP-safe features. Use when the user
  asks for a SCOUT review, audit, improvement ideas, feature suggestions,
  "what's next for SCOUT," or codebase health check — even without naming SCOUT
  explicitly if the workspace is this project.
disable-model-invocation: true
---

# SCOUT App Review

Local-first OSINT toolkit: **Footprint mode** (own identifiers) and **Threat mode** (IOCs). Stack: Python 3.12 / FastAPI / SQLAlchemy / SQLite backend; React / Vite / Cytoscape frontend.

**Phase constraint:** This branch is **Phase 1 (MVP)** only. Do not recommend Phase 2+ items (SSE streaming, export, LLM summarization, etc.) unless the user explicitly asks to expand scope. See `CLAUDE.md` and `README.md` roadmap.

## Process

1. **Explore.** Use a code-explorer subagent to map:
   - Backend: `backend/scout/main.py`, `orchestrator.py`, `cache.py`, `sources/`, `api/`, `models/`
   - Frontend: `frontend/src/components/`, `lib/api.ts`, `lib/graph.ts`
   - Tests: `backend/tests/`
   - Config: `~/.scout/config.toml` pattern in `config.py`
2. **Review.** Use a code-reviewer subagent against the checklist below.
3. **Verify where cheap.** Run:
   ```bash
   uv run pytest
   uv run ruff check backend/
   cd frontend && npm run build
   ```
   Optionally hit `GET /health` if the server is running. Failures are top findings.

## SCOUT-specific checklist

- **Source plugins:** `@register` protocol in `sources/base.py`; skipped vs. error behavior; rate limits; cache TTLs in orchestrator
- **Graph model:** `Node`/`Edge` normalization; dedup in orchestrator; Cytoscape mapping in `frontend/src/lib/graph.ts`
- **Async pipeline:** parallel fetches, shared `httpx.AsyncClient`, no blocking in `fetch()`
- **Caching & quotas:** TTL per source; cache hits don't burn API keys; free-tier safety
- **Local-first security:** default `127.0.0.1` bind; API keys in config only; footprint consent model
- **Frontend:** mode toggle, investigation form validation, graph empty/error states, TanStack Query cache keys
- **CLI:** `scout serve`, `scout config init/show`

## Suggestion quality bar

Each suggestion must include:

- **What & where:** e.g. `orchestrator.py::_DEFAULT_TTL`, `ResultsGraph.tsx`
- **Why:** impact on investigations, API quota, UX, or maintainability
- **Effort:** S / M / L
- **Severity:** Critical / Recommended / Nice-to-have
- **Phase fit:** MVP-safe or explicitly out-of-scope (with phase label)

Prefer one-file source additions and incremental API/UI changes over architectural rewrites.

## Output

Markdown, grouped by category (Sources, Orchestrator/Cache, API, Frontend/Graph, Testing, Security):

- **3–5 suggestions** following the quality bar
- **Start here** list: impact vs. effort, MVP-safe items first

Do not implement unless asked.
