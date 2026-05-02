# SCOUT — Unified OSINT Toolkit

> **Working name:** SCOUT (Self-audit & Cyber Observation Unified Toolkit)
> **Tagline:** Local-first OSINT for two workflows: auditing your own digital footprint, and investigating threat indicators.

---

## 1. Project Overview

### Goal
A local-first Python + React application that unifies two legitimate OSINT workflows behind one interface:

1. **Footprint mode** — User enters identifiers they own (email, username, domain, IP) and SCOUT shows what's publicly exposed about them across breach databases, certificate transparency logs, GitHub, archived web content, etc.
2. **Threat mode** — User enters indicators-of-compromise (IPs, domains, file hashes, URLs) and SCOUT enriches them with reputation data, WHOIS/DNS, passive DNS, and threat intel feeds.

Both modes share the same architectural backbone — pluggable source registry, async fetch pipeline, normalized graph model, visualization, optional AI summarization — but expose different source sets and UX flows depending on mode.

### Why this design
- **Legal and ethical**: every source is either public-by-design (cert transparency, WHOIS), self-authorized (your own breaches, your own GitHub repos), or scoped to non-personal indicators (IPs, hashes).
- **Portfolio-worthy**: demonstrates security awareness, async Python, plugin architecture, graph data modeling, and React visualization in one project.
- **Reusable skills**: the source-plugin pattern is reusable for any aggregation tool you build later.

### Tech stack (consistent with existing projects)
- **Backend**: FastAPI + SQLite + SQLAlchemy + `httpx` (async) + `aiolimiter` (rate limiting)
- **Frontend**: React + Vite + TypeScript + Tailwind + Cytoscape.js (graph) + TanStack Query
- **AI summarization (optional, Phase 4)**: Local LLM via Ollama (matches your home-lab setup), with optional Anthropic API fallback
- **Aesthetic**: Dark terminal theme — green-on-black accents in footprint mode, amber accents in threat mode
- **Distribution**: Single `uv`-installable CLI that launches the backend and serves the frontend

---

## 2. Core Architectural Decisions

### Mode-aware source registry
Every data source is a plugin implementing a common interface, tagged with which modes it supports and which input types it accepts:

```python
class Source(Protocol):
    name: str                         # "haveibeenpwned"
    modes: set[Mode]                  # {Mode.FOOTPRINT}
    accepts: set[InputType]           # {InputType.EMAIL}
    auth_required: bool
    rate_limit: RateLimit             # requests per window

    async def fetch(self, target: str, ctx: FetchContext) -> SourceResult: ...
```

This means adding a new source is one file. The orchestrator queries the registry for sources matching `(mode, input_type)`, fans out fetches in parallel, and merges results into the graph model.

### Normalized graph model
All sources produce nodes and edges in a common shape:

```python
Node:  id, type (email|domain|ip|hash|url|breach|cert|repo|account), label, attrs, source
Edge:  src_id, dst_id, relation (exposed_in|resolves_to|owns|references|...), source
```

This is what makes the visualization work — Cytoscape doesn't care whether a node came from HIBP or Shodan, it just renders the typed graph.

### Local-first, single-user
- SQLite database at `~/.scout/scout.db`
- API keys stored in `~/.scout/config.toml` (with chmod 600), never in code
- No multi-tenant complexity, no auth layer in v1
- Server binds to `127.0.0.1` only by default

### Caching by default
Every source response is cached in SQLite with a TTL (configurable per source — breach data: 24h, WHOIS: 7d, DNS: 1h). This is critical because:
- Free-tier API quotas are tiny
- Re-running an investigation shouldn't burn quota
- You want to develop without hitting live APIs every reload

### Outbound rate limiting
Each source declares its rate limit and the orchestrator enforces it via `aiolimiter`. This protects you from getting your API keys revoked, which is the actual rate-limiting concern for OSINT tools.

---

## 3. Sources (MVP and beyond)

### Footprint mode

| Source | Input | What it returns | Auth | Phase |
|---|---|---|---|---|
| HaveIBeenPwned | email | Breach exposures | API key (~$4/mo) | MVP |
| Gravatar | email | Public profile linked to email | None | MVP |
| GitHub user API | username | Public repos, gists, social links | PAT (free) | MVP |
| crt.sh | domain | SSL certs (reveals subdomains) | None | MVP |
| WHOIS/RDAP | domain | Registration metadata | None | Phase 2 |
| DNS resolver | domain | A/AAAA/MX/TXT/NS records | None | Phase 2 |
| Wayback Machine CDX | domain/url | Historical snapshots | None | Phase 2 |
| Hunter.io | domain | Emails published on the domain | API key (free tier) | Phase 2 |
| GitHub code search | username/email | Leaked secrets in your repos | PAT | Phase 3 |

### Threat mode

| Source | Input | What it returns | Auth | Phase |
|---|---|---|---|---|
| AbuseIPDB | ip | IP reputation, abuse reports | API key (free) | MVP |
| VirusTotal | ip/domain/hash/url | Reputation across AV engines | API key (free) | MVP |
| WHOIS/RDAP | domain/ip | Registration / network ownership | None | MVP |
| DNS resolver | domain | Resolution chain | None | MVP |
| crt.sh | domain | Cert history | None | Phase 2 |
| URLhaus | url/domain | Known malware URLs | None | Phase 2 |
| ThreatFox | ip/domain/hash | IOC database (abuse.ch) | None | Phase 2 |
| Shodan InternetDB | ip | Open ports, vulns (free, no key) | None | Phase 2 |
| OTX AlienVault | ip/domain/hash | Pulse subscriptions, related IOCs | API key (free) | Phase 3 |
| MalwareBazaar | hash | Malware sample metadata | None | Phase 3 |

### Shared utilities
- IP geolocation (ipapi.co or local MaxMind GeoLite2)
- ASN lookup (Team Cymru or local data)

---

## 4. Project Structure

```
scout/
├── pyproject.toml                  # uv-managed, exposes `scout` CLI
├── README.md
├── CLAUDE.md                       # Claude Code working notes
├── backend/
│   ├── scout/
│   │   ├── __init__.py
│   │   ├── main.py                 # FastAPI app + Vite dist mount
│   │   ├── cli.py                  # Typer CLI: `scout serve`, `scout query`, `scout config`
│   │   ├── config.py               # Pydantic Settings, loads ~/.scout/config.toml
│   │   ├── models/
│   │   │   ├── domain.py           # Node, Edge, SourceResult, Mode, InputType
│   │   │   └── db.py               # SQLAlchemy models: Investigation, CachedResponse
│   │   ├── db.py                   # Engine, session factory, migrations
│   │   ├── sources/
│   │   │   ├── base.py             # Source protocol, registry, decorators
│   │   │   ├── footprint/
│   │   │   │   ├── hibp.py
│   │   │   │   ├── gravatar.py
│   │   │   │   ├── github_user.py
│   │   │   │   └── crtsh.py
│   │   │   └── threat/
│   │   │       ├── abuseipdb.py
│   │   │       ├── virustotal.py
│   │   │       ├── whois_rdap.py
│   │   │       └── dns_resolver.py
│   │   ├── orchestrator.py         # Fan-out, rate limiting, caching, graph merge
│   │   ├── cache.py                # TTL-aware response cache backed by SQLite
│   │   ├── rate_limit.py           # aiolimiter wrapper per source
│   │   └── api/
│   │       ├── routes_investigate.py   # POST /investigate, GET /investigations/{id}
│   │       ├── routes_sources.py       # GET /sources (lists registered, filtered by mode)
│   │       └── routes_health.py
│   └── tests/
│       ├── test_sources/           # one test file per source, with recorded fixtures
│       ├── test_orchestrator.py
│       └── test_cache.py
└── frontend/
    ├── package.json                # vite, react, typescript, tailwind, cytoscape, tanstack-query
    ├── vite.config.ts              # proxy /api -> http://127.0.0.1:8765
    ├── index.html
    └── src/
        ├── main.tsx
        ├── App.tsx
        ├── theme.css               # CSS vars for footprint (green) vs threat (amber)
        ├── components/
        │   ├── ModeToggle.tsx
        │   ├── InvestigationForm.tsx
        │   ├── ResultsGraph.tsx    # Cytoscape wrapper
        │   ├── ResultsList.tsx     # tabular fallback
        │   ├── SourceStatus.tsx    # which sources ran, hit/miss/error
        │   └── NodeDetailPanel.tsx
        ├── lib/
        │   ├── api.ts              # typed fetch wrapper
        │   └── graph.ts            # node/edge -> cytoscape elements
        └── types/
            └── api.ts              # mirrors backend Pydantic models
```

---

## 5. Database Schema

```sql
-- An investigation is one user-initiated run
CREATE TABLE investigations (
    id              TEXT PRIMARY KEY,           -- uuid7
    mode            TEXT NOT NULL,              -- 'footprint' | 'threat'
    target          TEXT NOT NULL,              -- the input value
    target_type     TEXT NOT NULL,              -- 'email' | 'domain' | ...
    created_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at    TIMESTAMP,
    status          TEXT NOT NULL DEFAULT 'running',   -- running|complete|failed
    note            TEXT
);

-- Each source's contribution to an investigation
CREATE TABLE source_runs (
    id              TEXT PRIMARY KEY,
    investigation_id TEXT NOT NULL REFERENCES investigations(id) ON DELETE CASCADE,
    source_name     TEXT NOT NULL,
    started_at      TIMESTAMP NOT NULL,
    finished_at     TIMESTAMP,
    status          TEXT NOT NULL,              -- ok|error|skipped|cache_hit
    error_message   TEXT,
    cache_hit       BOOLEAN NOT NULL DEFAULT 0
);

-- Normalized graph nodes (one row per node per investigation)
CREATE TABLE nodes (
    id              TEXT PRIMARY KEY,           -- "{type}:{canonical_value}"
    investigation_id TEXT NOT NULL REFERENCES investigations(id) ON DELETE CASCADE,
    type            TEXT NOT NULL,              -- email|domain|ip|hash|url|breach|cert|repo|account
    label           TEXT NOT NULL,
    attrs_json      TEXT NOT NULL DEFAULT '{}',
    discovered_by   TEXT NOT NULL               -- source name
);

CREATE TABLE edges (
    id              TEXT PRIMARY KEY,
    investigation_id TEXT NOT NULL REFERENCES investigations(id) ON DELETE CASCADE,
    src_node_id     TEXT NOT NULL,
    dst_node_id     TEXT NOT NULL,
    relation        TEXT NOT NULL,              -- exposed_in|resolves_to|owns|references|registered_by|...
    discovered_by   TEXT NOT NULL,
    UNIQUE(investigation_id, src_node_id, dst_node_id, relation)
);

-- TTL response cache keyed by (source, normalized request)
CREATE TABLE response_cache (
    id              TEXT PRIMARY KEY,           -- hash(source_name + request_key)
    source_name     TEXT NOT NULL,
    request_key     TEXT NOT NULL,              -- e.g., 'email:foo@bar.com'
    response_json   TEXT NOT NULL,
    fetched_at      TIMESTAMP NOT NULL,
    expires_at      TIMESTAMP NOT NULL
);
CREATE INDEX idx_cache_expires ON response_cache(expires_at);
CREATE INDEX idx_cache_lookup  ON response_cache(source_name, request_key);
```

---

## 6. Key API Endpoints

```
POST   /api/investigate
       body: { mode: "footprint"|"threat", target: str, target_type: str, sources?: [str] }
       returns: { investigation_id, status_url }

GET    /api/investigations/{id}
       returns: { investigation, source_runs, nodes, edges }

GET    /api/investigations/{id}/stream    (SSE)
       streams source_run updates as they complete — matches your existing SSE preference

GET    /api/investigations
       returns: paginated history

GET    /api/sources?mode=footprint
       returns: [{ name, accepts, auth_required, configured }]

GET    /api/health
```

---

## 7. Roadmap (Phased)

### Phase 1 — MVP (target: 1–2 weeks)
**Goal:** End-to-end vertical slice: type a target, see a graph.

- FastAPI skeleton with SQLite, SQLAlchemy models, Alembic-free migrations (raw SQL for now)
- Source plugin protocol + registry
- 3 footprint sources: HIBP, Gravatar, GitHub user
- 3 threat sources: AbuseIPDB, VirusTotal, DNS resolver
- Orchestrator: parallel fetch, cache hit/miss, rate limiting
- POST /investigate (synchronous return for MVP — SSE comes in Phase 2)
- React + Vite + Tailwind frontend with mode toggle, input form, Cytoscape graph, results list
- `scout serve` CLI command
- Config loader for `~/.scout/config.toml`

**Out of scope for MVP:** SSE streaming, AI summarization, export, history browser

### Phase 2 — Depth (target: +1 week)
- SSE streaming so the graph populates as sources complete
- Add sources: WHOIS/RDAP, Wayback CDX, Hunter.io, crt.sh (threat side), URLhaus, ThreatFox, Shodan InternetDB
- Investigation history browser
- Re-run investigation (uses cache where valid, refetches otherwise)
- "Pivot" action: right-click a node → start a new investigation on it

### Phase 3 — Polish (target: +1 week)
- More sources: GitHub code search, OTX AlienVault, MalwareBazaar
- Export: investigation as JSON, graph as PNG/SVG
- Per-source TTL configuration UI
- API key management UI (with chmod check warning)
- Source health dashboard (last successful call, error rate)

### Phase 4 — Intelligence (target: +1–2 weeks)
- Local LLM summarization via Ollama
  - "Summarize what's publicly known about this footprint"
  - "What's the threat assessment for this IOC?"
- Optional Anthropic API fallback (configurable)
- Diff view: re-run an investigation and highlight what changed

### Phase 5 — Extras (open-ended)
- Scheduled re-runs (cron-style) with email/webhook on diff
- Browser extension: right-click a domain/IP → "Investigate in SCOUT"
- Import IOCs from a STIX/TAXII feed (threat mode bulk operations)
- Export defensive-mode report as PDF for personal records

---

## 8. Security & Compliance Notes

- **Footprint mode is consent-by-design**: the UI should make clear it's intended for self-audit. Add a confirmation step the first time a user investigates an email/domain that's not in their config's "owned identifiers" list.
- **No PII storage beyond what the user inputs**: investigations table holds the target, but caches are keyed by request, not by person.
- **API keys live in `~/.scout/config.toml` only**, never in env vars by default (env vars leak into child processes), never in the repo.
- **Outbound rate limiting is enforced server-side** — sources can't be called faster than their declared limit even if a user spams the form.
- **Server binds to 127.0.0.1 by default**. Binding to 0.0.0.0 requires an explicit `--host` flag and prints a warning.
- **Respect robots.txt and ToS**: every source plugin includes a comment with its ToS URL and any usage caveats.

---

## 9. Testing Strategy

- **Source plugins**: each has a test file with recorded HTTP fixtures (use `pytest-recording` / VCR.py). No real API calls in CI.
- **Orchestrator**: tests with a fake source registry, verify fan-out, cache hit behavior, rate limit enforcement, graph merge.
- **API**: FastAPI `TestClient` against in-memory SQLite.
- **Frontend**: Vitest + React Testing Library for components; Playwright for one happy-path E2E (optional).

---

## 10. Open Questions to Decide Before Starting

1. **CLI framework**: Typer (Click-based, good defaults) vs argparse. Typer recommended — matches FastAPI's Pydantic ergonomics.
2. **Frontend graph library**: Cytoscape.js (recommended — better for typed graphs and large node counts) vs D3 force-directed (more flexible but more code). Cytoscape recommended for MVP.
3. **Distribution**: ship as a `uv tool install scout` package, or as a Docker image, or both? Recommend `uv tool install` for dev, Docker for Phase 3+.
4. **Anthropic API fallback in Phase 4**: do you want it, or strictly Ollama? Strictly local matches your stated preferences best.

---

## 11. Naming / Branding

Working name **SCOUT** (Self-audit & Cyber Observation Unified Toolkit) — open to alternatives. Other candidates:
- **TRACE** — Threat & Reconnaissance Aggregation for Citizen Engineers
- **LOOM** — Local OSINT Observation & Mapping
- **WATCHTOWER** — too SaaS-y, but evocative

---
