# Public Equity Research Team

Local-first multi-agent equity research workstation. FastAPI backend orchestrates 10 specialized agents (MD · Fundamentals · Industry · DCF · Comps · Macro · Risk · Technicals · Deck Builder · Memo Builder) to produce institutional-quality research — pitch deck, written memo, one-pager, DCF model, comps table — for any US-listed equity. Next.js workspace UI on `localhost:3000` drives the orchestrator over REST + WebSocket.

## Run dev

Two terminals:

```bash
# Terminal 1 — backend (port 8001 to dodge a Docker collision on 8000)
source backend/venv/bin/activate
uvicorn backend.main:app --reload --port 8001

# Terminal 2 — frontend
cd frontend
npm install        # first time only
npm run dev
```

Open <http://localhost:3000>. Pick a ticker via the autocomplete, click a workflow button (Full Deep-Dive · Earnings Update · Morning Note · Thesis Check · Sector Sweep). Watch agents stream in the chat panel; preview every artifact in the right-hand folder tree.

## Tests

```bash
# Backend
source backend/venv/bin/activate
pytest tests/

# Frontend unit
cd frontend && npm test

# Frontend e2e (Playwright with mocked backend)
cd frontend && npm run e2e
```

## Workflows

| Workflow         | What it does                                                              | Wall-clock |
|------------------|---------------------------------------------------------------------------|------------|
| Full Deep-Dive   | All 10 agents → pitch deck + memo + one-pager + DCF + comps               | ~7 min     |
| Earnings Update  | Fundamentals + DCF + Risk → memo only (no deck)                           | ~3 min     |
| Morning Note     | Fundamentals → MD writes a brief note                                     | ~1 min     |
| Thesis Check     | LLM-routed 2-3 pods focused on a specific question                        | varies     |
| Sector Sweep     | Industry + Comps + Macro across N tickers → sector overview               | varies     |

Outputs land at `~/Documents/equity-research/<TICKER>/` (configurable via `RESEARCH_DIR`).

## Required env (`.env` at repo root)

| Var | Purpose |
|---|---|
| `ANTHROPIC_API_KEY` | LLM for every agent |
| `FMP_API_KEY` | Financial Modeling Prep — fundamentals, peers, prices |
| `FRED_API_KEY` | Macro indicators (10Y UST, CPI, unemployment) |
| `SEC_EDGAR_USER_AGENT` | SEC fair-use policy — `Your Name your@email.com` |

Optional overrides:

| Var | Default |
|---|---|
| `RESEARCH_DIR` | `~/Documents/equity-research` |
| `ANTHROPIC_MODEL` | `claude-opus-4-7` |
| `ANTHROPIC_MODEL_<AGENT>` | per-agent model override (e.g. `ANTHROPIC_MODEL_MACRO=claude-sonnet-4-6`) |
| `MAX_CONCURRENT_AGENTS` | `5` |
| `NEXT_PUBLIC_BACKEND_URL` | `http://127.0.0.1:8001` (frontend → backend) |

See `.env.example` for the full list.

## Repo layout

```
backend/                 FastAPI service (port 8001)
  agents/                10 agent classes (LLM half + deterministic half)
  tools/                 fmp_client, edgar_client, fred_client, dcf_engine, charts, xlsx/pptx/docx/pdf writers
  routes/                jobs (REST + WS), files, tickers_search
  observability/         JobLogger (JSONL) + JobEventBus (in-process pub/sub)
  db/                    SQLite + JobRepo
  job_runner.py          fire-and-forget orchestrator dispatch
  main.py                app factory + uvicorn entrypoint

frontend/                Next.js 16 workspace (port 3000)
  app/                   App Router root
  components/            TopBar, Sidebar, TabBar, ChatPanel, FolderTree, ArtifactPreviewModal, …
  components/preview/    md/json/png/xlsx/docx/pdf/pptx renderers
  lib/                   api.ts (REST), ws.ts (WebSocket), store.ts (Zustand), types.ts
  e2e/                   Playwright smoke

tests/                   pytest — 174 tests, including a canonical-fixture eval
docs/superpowers/        specs + plans + handoffs
```

## CLI launchers

Plan D (not yet implemented) will add `equity-research-{setup,backend,frontend}` plus a combined `equity-research` osascript that opens both processes in a single Terminal window.

## Known limitations (v1)

- Single user, no auth.
- Local only — no cloud deploy.
- Equity only (no fixed income, FX, options).
- Manual quality eval (no automated scoring).
- PDF preview pulls the pdfjs worker from cdnjs — no offline-only mode yet.
- **No direct chat input.** Workflows are dispatched via the top-bar quick-action buttons only. The chat panel is read-only (streams agent events). Spec §7 calls for per-agent direct follow-ups; that's planned but not in v1.
- **Single concurrent job.** `MdProgress` and `jobLog` track one active job; running a second job before the first completes will cross-contaminate the progress UI. Workaround: wait for the toast before dispatching another.
- **`@app.on_event` deprecation warnings** in pytest output — pre-existing from Plan A; will migrate to `lifespan` in Plan D.
