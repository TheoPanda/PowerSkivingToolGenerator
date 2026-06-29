# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Desktop app for parametric design and 3D visualization of **power skiving tools** (车齿刀). Users input gear parameters → Python/OCCT computes tool geometry → glTF model rendered in Three.js.

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Desktop shell | Electron (latest) |
| Frontend | Vue 3 (Composition API + `<script setup>`), TypeScript strict mode, Vite |
| 3D rendering | Three.js |
| UI library | Element Plus |
| Backend | Python 3.13+, Flask or FastAPI |
| Geometry kernel | OpenCASCADE (OCCT) via `pythonocc-core` |
| Model format | glTF/GLB |

## Architecture & Communication

```
Renderer (Vue/Three.js)
    ↕ HTTP (primary)
Python backend (Flask/FastAPI + OCCT)
    ↕ child_process
Electron main process
    ↕ IPC (preload.js)
Renderer (file dialogs, system APIs)
```

- **HTTP first** for frontend↔backend — never use `fs` in renderer, so the app can migrate to web later.
- **IPC only** for native OS features (file dialogs, file read/write via main process).
- **`nodeIntegration: false`** in renderer; expose controlled APIs via `preload.js`.
- Python process lifecycle managed by Electron main process (`python-manager.js`).

## Directory Structure (target)

```
my-skiving-tool/
├── .env.development          # Vite env vars for dev
├── .env.production           # Vite env vars for prod
├── electron/
│   ├── main.js
│   ├── preload.js
│   └── python-manager.js
├── src/
│   ├── api/                  # HTTP client wrappers for backend
│   ├── assets/
│   ├── components/
│   │   ├── ToolParams.vue    # Parameter input form
│   │   └── ModelViewer.vue   # Three.js 3D viewport
│   ├── App.vue
│   └── main.ts
├── backend/
│   ├── app.py                # Flask/FastAPI entry point
│   ├── requirements.txt
│   └── core/                 # OCCT geometry computation
├── package.json
└── vite.config.ts
```

## Key Constraints

- **Never hardcode IPs or ports** — use `import.meta.env.VITE_...` via Vite env variables.
- All TypeScript functions must have explicit parameter and return types.
- Backend must enable CORS (`flask-cors` or FastAPI equivalent).
- Backend returns standard JSON errors: `{ "error": "description", "code": 400 }`.
- glTF/GLB is the only model format between backend and frontend.
- Avoid geometry creation inside Three.js render loops; manage resource disposal explicitly.
- Use `async/await` + `try/catch` for all async operations.

## Core Business Logic (Power Skiving Tool)

Key gear parameters: module (`模数`), tooth count (`齿数`), pressure angle (`压力角`), helix angle (`螺旋角`), profile shift coefficient (`变位系数`), rake angle (`前角`), relief angle (`后角`).

Computation pipeline: parameters → discrete points → curves → extrude/sweep → boolean operations → export glTF.

## Commands (once scaffolded)

```bash
# Install dependencies
npm install
cd backend && pip install -r requirements.txt

# Development (Vite dev server + Electron)
npm run dev

# Build for production
npm run build

# Lint
npm run lint

# Type check
npm run typecheck

# Run tests
npm test
```

## Agent skills

### Issue tracker

GitHub Issues via the `gh` CLI. See `docs/agents/issue-tracker.md`.

### Triage labels

Default vocabulary: `needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`. See `docs/agents/triage-labels.md`.

### Domain docs

Multi-context: `CONTEXT-MAP.md` at root, with `src/CONTEXT.md` (frontend) and `backend/CONTEXT.md` (backend). See `docs/agents/domain.md`.

## Others
所有对话采用中文。