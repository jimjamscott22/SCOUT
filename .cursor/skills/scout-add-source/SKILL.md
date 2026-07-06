---
name: scout-add-source
description: >-
  Adds a new OSINT data source plugin to SCOUT following the @register protocol,
  graph model, cache TTL, config, and test patterns. Use when the user wants to
  add a source, integrate a new API, extend footprint or threat mode, or
  implement HIBP/VirusTotal-style fetch logic for another provider.
disable-model-invocation: true
---

# SCOUT Add Source

Adding a source = **one module file** + config + TTL + tests. The orchestrator handles parallel fetch, rate limiting, caching, and skip-on-missing-key.

## Before coding

Gather (ask if missing):

| Field | Example |
|-------|---------|
| Source name | `shodan` (registry key, lowercase) |
| Mode | `FOOTPRINT` / `THREAT` |
| Input type(s) | `InputType.IP`, `DOMAIN`, etc. |
| Auth | API key required? Header/query param name |
| Rate limit | requests per 60s (match provider ToS) |
| API docs URL | for response parsing |

Read a similar existing source:
- Footprint + auth: `backend/scout/sources/footprint/hibp.py`
- Footprint + no auth: `backend/scout/sources/footprint/gravatar.py`
- Threat + auth: `backend/scout/sources/threat/virustotal.py`
- Threat + no auth: `backend/scout/sources/threat/dns_resolver.py`

## Implementation checklist

```
- [ ] Create `backend/scout/sources/{footprint|threat}/<name>.py`
- [ ] `@register` class with name, modes, accepts, auth_required, rate_limit
- [ ] `async def fetch(self, target, ctx) -> SourceResult`
- [ ] Use `ctx.http` only — never create a new httpx client
- [ ] Build `Node` / `Edge` with stable ids (`type:value`) and correct `NodeType` / relations
- [ ] Return empty result on expected "not found" — don't treat as error
- [ ] Import module in `sources/footprint/__init__.py` or `sources/threat/__init__.py`
- [ ] Add config key in `config.py` + document in README config example
- [ ] Add TTL in `orchestrator.py` `_DEFAULT_TTL` (breach-like: 86400, DNS-like: 3600)
- [ ] Add `backend/tests/test_sources/test_<name>.py` with httpx mocking
- [ ] Run `uv run pytest backend/tests/test_sources/test_<name>.py -v`
```

## fetch() patterns

```python
@register
class ExampleSource:
    name = "example"
    modes = {Mode.THREAT}
    accepts = {InputType.DOMAIN}
    auth_required = True
    rate_limit = RateLimit(requests=4, window_seconds=60)

    async def fetch(self, target: str, ctx: FetchContext) -> SourceResult:
        result = SourceResult(source_name=self.name)
        # Seed anchor node for the target input type
        # Call API via ctx.http.get/post(...)
        # Map JSON → Node/Edge; set result.raw for debugging
        # 404 / empty → return result (status ok, zero extra nodes)
        # Unexpected errors → let raise or catch and attach to result per peer sources
        return result
```

**Auth:** If `auth_required`, read `ctx.api_keys.get(self.name, "")`. Missing key → orchestrator skips with `status=skipped` (do not crash the investigation).

**Ids:** Follow peers — `email:user@x.com`, `domain:example.com`, `breach:adobe`, etc.

## Testing

Mirror `backend/tests/test_sources/test_hibp.py`:
- Mock `httpx` responses with `respx` or project convention
- Assert nodes, edges, relations, and empty/not-found behavior
- Test skipped path only if logic lives in source (usually orchestrator handles skip)

## Frontend

Usually **no changes** — Cytoscape renders typed nodes automatically. Only touch frontend if new `NodeType` needs styling in `frontend/src/lib/graph.ts` or `NodeDetailPanel.tsx`.

## Done criteria

- Source appears in registry (`get_sources(mode=..., input_type=...)`)
- Investigation returns graph nodes without API key configured (skipped, not error)
- With key configured, live or mocked fetch produces expected graph
- `uv run pytest` and `uv run ruff check backend/` pass

For full feature specs (UI + API + multi-source), use `scout-feature-planning` first.
