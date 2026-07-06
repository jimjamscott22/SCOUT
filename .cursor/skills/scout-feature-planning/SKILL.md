---
name: scout-feature-planning
description: >-
  Scopes and plans new SCOUT features or improvements into an implementable spec
  aligned with the plugin architecture and phase roadmap. Use when the user wants
  to add a feature, plan an enhancement, scope Phase 2 work, brainstorm what to
  build next, or turn a vague idea into a concrete task list for SCOUT.
disable-model-invocation: true
---

# SCOUT Feature Planning

Turn a feature idea into a scoped spec an agent (or developer) can implement without guessing architecture.

## Before planning

1. Read `CLAUDE.md`, `README.md` roadmap, and `docs/SCOUT_PROJECT_PLAN.md` for phase boundaries.
2. Clarify with the user if missing:
   - Which mode(s): Footprint, Threat, or both
   - Input type(s): email, domain, ip, hash, url, username
   - MVP now vs. later phase
3. **Default:** stay within Phase 1 unless the user explicitly expands scope.

## Classify the feature

| Type | Typical touch points | Example |
|------|---------------------|---------|
| **New source** | `sources/*`, `config.py`, orchestrator TTL, tests | Add Shodan |
| **API endpoint** | `api/routes_*.py`, orchestrator, Pydantic schemas | Investigation history |
| **Frontend UX** | `frontend/src/components/`, `lib/api.ts`, types | Node detail panel |
| **Infrastructure** | `cache.py`, `orchestrator.py`, `cli.py` | SSE streaming (Phase 2) |
| **Cross-cutting** | Multiple layers | Export graph as PNG |

If the feature is **New source**, also read `.cursor/skills/scout-add-source/SKILL.md` and reference it in the spec.

## Spec template

Produce markdown using this structure:

```markdown
# Feature: [name]

## Summary
One paragraph: what the user gets and which mode(s) it serves.

## Phase & scope
- Phase: 1 (MVP) | 2 | 3 | ...
- In scope: ...
- Out of scope (defer): ...

## User flow
1. User does X
2. System does Y
3. User sees Z

## Architecture fit
- Reuses: [registry / orchestrator / graph model / cache / ...]
- New concepts (if any): ...

## Files to create or modify
| Path | Change |
|------|--------|
| ... | ... |

## Data model
- New Node/Edge types or relations (if any)
- Cache TTL recommendation
- Config keys (`[sources.name]` in config.toml)

## API changes (if any)
- Method, path, request/response shape

## Frontend changes (if any)
- Components, graph styling, new TanStack Query keys

## Acceptance criteria
- [ ] Testable criterion 1
- [ ] Testable criterion 2

## Risks & mitigations
- API quota, rate limits, legal/ethical (footprint = own data only)

## Implementation order
1. Backend / source first (with tests)
2. API wiring
3. Frontend
4. Docs / README if user-facing

## Effort estimate
S / M / L with brief rationale
```

## Quality bar

- Every file path must be real or explicitly marked **(new file)**
- Acceptance criteria must be verifiable (`pytest`, manual UI step, or API curl)
- Call out dependencies on API keys or external services
- If the idea duplicates an existing source or UI, say so and suggest extending instead

## Output rules

- Deliver the spec only — **do not implement** unless the user asks
- If the idea is too large, split into Phase-1 slice + follow-ups
- End with **"Suggested first PR"**: the smallest shippable increment
