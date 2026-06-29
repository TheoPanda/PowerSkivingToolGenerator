# Domain Docs

How the engineering skills should consume this repo's domain documentation when exploring the codebase.

## Before exploring, read these

- **`CONTEXT-MAP.md`** at the repo root — it points at one `CONTEXT.md` per context. Read each one relevant to the topic.
- **`docs/adr/`** — system-wide architectural decisions.
- **`src/CONTEXT.md`** — frontend domain (Electron, Vue 3, Three.js).
- **`src/docs/adr/`** — frontend-specific ADRs.
- **`backend/CONTEXT.md`** — backend domain (Python, Flask/FastAPI, OCCT).
- **`backend/docs/adr/`** — backend-specific ADRs.

If any of these files don't exist, **proceed silently**. Don't flag their absence; don't suggest creating them upfront. The producer skill (`/grill-with-docs`) creates them lazily when terms or decisions actually get resolved.

## File structure

This is a multi-context repo:

```
/
├── CONTEXT-MAP.md              ← maps contexts
├── docs/adr/                   ← system-wide decisions
├── src/
│   ├── CONTEXT.md              ← frontend domain
│   └── docs/adr/               ← frontend-specific decisions
└── backend/
    ├── CONTEXT.md              ← backend domain
    └── docs/adr/               ← backend-specific decisions
```

## Use the glossary's vocabulary

When your output names a domain concept (in an issue title, a refactor proposal, a hypothesis, a test name), use the term as defined in `CONTEXT.md`. Don't drift to synonyms the glossary explicitly avoids.

If the concept you need isn't in the glossary yet, that's a signal — either you're inventing language the project doesn't use (reconsider) or there's a real gap (note it for `/grill-with-docs`).

## Flag ADR conflicts

If your output contradicts an existing ADR, surface it explicitly rather than silently overriding:

> _Contradicts ADR-0007 (event-sourced orders) — but worth reopening because…_
