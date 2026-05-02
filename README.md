# SCOUT

**Self-audit & Cyber Observation Unified Toolkit**

A local-first OSINT toolkit that unifies two workflows behind one interface:

- **Footprint mode** — Audit your own digital exposure across breach databases, certificate transparency logs, GitHub, and more.
- **Threat mode** — Investigate indicators-of-compromise (IPs, domains, hashes) with reputation data, DNS resolution, and threat intel feeds.

Both modes share a pluggable async source registry, a normalized graph model, and a Cytoscape-rendered frontend.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.12+, FastAPI, SQLAlchemy 2.x, SQLite, `httpx`, `aiolimiter` |
| Frontend | Vite + React + TypeScript + Tailwind CSS + Cytoscape.js + TanStack Query |
| Python packaging | `uv` |
| Frontend packaging | `npm` |

---

## Installation

Requires [uv](https://docs.astral.sh/uv/) and Node.js 18+.

```bash
uv tool install .
```

---

## Configuration

Initialize a config file at `~/.scout/config.toml`:

```bash
scout config init
```

Edit `~/.scout/config.toml` to add your API keys:

```toml
[scout]
db_path = "~/.scout/scout.db"
host = "127.0.0.1"
port = 8765

[sources.hibp]
api_key = ""          # https://haveibeenpwned.com/API/Key

[sources.virustotal]
api_key = ""          # https://www.virustotal.com/gui/my-apikey

[sources.abuseipdb]
api_key = ""          # https://www.abuseipdb.com/account/api

[sources.github]
token = ""            # https://github.com/settings/tokens
```

To verify your loaded config (API keys are redacted):

```bash
scout config show
```

---

## Running

```bash
scout serve
```

Then open [http://127.0.0.1:8765](http://127.0.0.1:8765) in your browser.

To bind to a different host or port:

```bash
scout serve --host 0.0.0.0 --port 9000
```

> **Warning:** Binding to `0.0.0.0` exposes SCOUT on your network. Use with caution.

---

## Sources

### Footprint Mode

| Source | Input | Auth | Phase |
|---|---|---|---|
| HaveIBeenPwned | email | API key | MVP |
| Gravatar | email | None | MVP |
| GitHub user API | username | PAT (free) | MVP |

### Threat Mode

| Source | Input | Auth | Phase |
|---|---|---|---|
| AbuseIPDB | ip | API key (free tier) | MVP |
| VirusTotal | ip / domain | API key (free tier) | MVP |
| DNS resolver | domain | None | MVP |

Sources without a configured API key return an empty result and log `status=skipped` — they never crash an investigation.

---

## Development

### Backend

```bash
uv sync
uv run pytest
uv run ruff check backend/
uv run ruff format backend/
uv run mypy backend/scout
```

### Frontend

```bash
cd frontend
npm install
npm run dev      # Vite dev server with proxy to backend on :8765
npm run build    # Outputs to frontend/dist (served by FastAPI in prod)
```

---

## Roadmap

| Phase | Description |
|---|---|
| **1 — MVP** | 6 sources, sync investigation, Cytoscape graph, `scout serve` CLI |
| **2 — Depth** | SSE streaming, WHOIS/RDAP, Wayback, URLhaus, ThreatFox, Shodan, investigation history |
| **3 — Polish** | Export (JSON/PNG/SVG), API key management UI, more sources |
| **4 — Intelligence** | Local LLM summarization via Ollama, diff view on re-runs |
| **5 — Extras** | Scheduled re-runs, browser extension, STIX/TAXII import |

---

## Security Notes

- API keys are stored in `~/.scout/config.toml` only — never in environment variables or the repo.
- The server binds to `127.0.0.1` by default (single-user, local-only).
- Footprint mode is consent-by-design: intended for auditing identifiers you own.
- Outbound rate limiting is enforced server-side per source declaration.
