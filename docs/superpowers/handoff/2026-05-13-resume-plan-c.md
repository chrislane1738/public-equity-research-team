# Handoff — Resume Plan C (Public Equity Research Team)

**Generated:** 2026-05-13
**Author:** Plan B execution session
**Audience:** Future Claude session picking up Plan C / D

---

## How to use this document

Open a fresh Claude Code session in `/Users/chrislane/Desktop/Claude_Code/public-equity-research-team/`. Paste this as the first message:

> "Read `docs/superpowers/handoff/2026-05-13-resume-plan-c.md` end-to-end. Then write Plan C (Next.js workspace UI) per the existing spec at `docs/superpowers/specs/2026-05-12-public-equity-research-team-design.md` §7. Use the `superpowers:writing-plans` skill. After Plan C is approved, execute it with `superpowers:subagent-driven-development`. I'll be working on `main` directly. The keys are already in `.env`."

That's enough context to resume cleanly.

---

## 1. Project orientation (60 seconds)

A local-first, 10-agent equity research workstation. Backend + frontend on `localhost`. Single user, no auth, no deploy. Spec: `docs/superpowers/specs/2026-05-12-public-equity-research-team-design.md`.

**Plans:**

| # | Plan | Status | Deliverable |
|---|---|---|---|
| **A** | Backend skeleton + MVP pipeline | **DONE** | `curl POST /jobs` → `memo.docx` via stub research pods |
| **B** | Full agent roster + production tier + alt workflows | **DONE** (137 tests) | 6 real research agents, deck + onepager + memo, 5 workflows, SQLite persistence, JSONL telemetry |
| **C** | Next.js workspace UI | **NOT STARTED** | Browser chat UI: tabs, sidebar, ticker-folder tree, file previews, WS streaming |
| **D** | CLI launchers + dev polish | **NOT STARTED** | `equity-research-setup`, `-backend`, `-frontend`, combined `equity-research` osascript |

Plan A's plan: `docs/superpowers/plans/2026-05-12-plan-a-backend-mvp-pipeline.md`.
Plan B's plan: `docs/superpowers/plans/2026-05-12-plan-b-research-roster-production-tier.md`.

## 2. Where we are at the start of Plan C

- **Branch:** `main`. Latest commit: `eb17319` (Plan B canonical eval). 43 commits since Plan B baseline.
- **Test suite:** `pytest tests/` → **137 passed** in ~5s, 31 cosmetic warnings.
- **Backend is feature-complete for v1.** All 5 workflows route through `POST /jobs`, every agent runs, every artifact lands on disk, jobs persist in SQLite, per-job JSONL telemetry under `<TICKER>/_logs/<job-id>.jsonl`.
- **Live infrastructure not yet smoke-tested for Plan B.** Plan A's smoke test (handoff §9) was validated. Plan B added a lot — recommend running the smoke test against real APIs before kicking off Plan C, to catch any FMP endpoint shape drift early.

## 3. What Plan B shipped

**Toolkit (`backend/tools/`):**
- `fmp_client.py` — extended with `get_profile`, `get_quote`, `get_historical_prices`, `get_peers`, `get_key_metrics`, `get_ratios`, `get_estimates`, `get_10y_treasury_rate`. Daily TTL cache at `~/Documents/equity-research/_fmp_cache/`.
- `fred_client.py` — `get_series(series_id, limit)`. Daily TTL cache.
- `multiples.py` — manual EV/EBITDA, P/E, EV/Sales, EV/cRPO, P/FFO + `aggregate_peer_multiples` (median/p25/p75).
- `dcf_engine.py` — WACC (CAPM), FCF projection, GGM/Exit/Blend terminal value with growth cap + multiple haircut + sector p75 cap, sensitivity grids.
- `charts.py` — matplotlib renderers (transparent bg): peer_share_chart, box_plot, football_field, sensitivity_heatmap, catalyst_timeline, price_chart.
- `xlsx_writer.py` — `write_dcf_xlsx` (10 tabs) + `write_comps_xlsx` (3 tabs).
- `pptx_writer.py` — `write_pitch_deck` (14 slides, optional charts on right).
- `pdf_writer.py` — `write_one_pager` (LETTER, 0.5" margins, single-page guard).

**Real research agents (`backend/agents/`):**
- `industry.py` — Industry & Moat. FMP profile + peers. Opus.
- `comps.py` — Comps. Manual multiples per peer; writes `peer-multiples.json` (consumed by DCF). Opus.
- `dcf.py` — DCF. Two LLM calls (assumptions JSON + prose). Reads `comps/peer-multiples.json`. Writes xlsx + 2 PNGs. Opus.
- `macro.py` — Macro. FRED indicators (DGS10, CPIAUCSL, UNRATE) + catalyst timeline. Sonnet.
- `risk.py` — Risk & Upside. Reads `fundamentals/10k-excerpt.txt`. Sonnet.
- `technicals.py` — Technicals (sidecar — never sets rating). FMP historical prices + price chart. Sonnet.
- `deck_builder.py` — Deck Builder. Single LLM call → `pitch.pptx` + `onepager.pdf`. Sonnet.
- `_stubs.py` is **deleted**.

**Orchestrator (`backend/orchestrator.py`):**
- `run(workflow, **kwargs)` dispatcher routes to one of 5 workflow methods.
- `run_full_deep_dive` — Stage 1 (Fundamentals) → Stage 2a parallel (Industry/Comps/Macro/Risk/Technicals) → Stage 2b (DCF, gated on Comps) → Stage 3 (MD synth) → Stage 4 parallel (Memo + Deck).
- `run_earnings_update` — Fundamentals → DCF + Risk parallel → MD → Memo only (no deck).
- `run_morning_note` — Fundamentals → bare LLM call with `MORNING_NOTE_PROMPT` → `reports/morning-note.md`.
- `run_thesis_check` — LLM routing call picks 2-3 pods → Fundamentals + chosen pods → focused memo to `reports/thesis-check.md`.
- `run_sector_sweep` — Per ticker: Fundamentals + Industry/Comps/Macro parallel; then sector overview to `_sector/<slug>/sector-overview.md`.
- All Anthropic calls wrapped in `SemaphoredAnthropicClient` (capacity = `MAX_CONCURRENT_AGENTS`).
- Per-agent model from `Settings.model_for(agent_name)` honoring `ANTHROPIC_MODEL_<AGENT>` env vars.

**Persistence + telemetry:**
- `backend/db/job_repo.py` — async SQLite-backed `JobRepo` (replaces Plan A's in-memory dict). Jobs survive process restart.
- `backend/observability/job_logger.py` — per-job JSONL writer at `<TICKER>/_logs/<job-id>.jsonl`. Aggregates cost via `total_cost_usd()`.
- `backend/observability/semaphore_client.py` — `SemaphoredAnthropicClient` wraps `messages.create` in an `asyncio.Semaphore`.

**Other:**
- `backend/cik_resolver.py` — `FmpProfileCikResolver` replaces Plan A's hard-coded 3-ticker map.
- `backend/config.py` — `Settings.model_for(agent)` + `fred_api_key` field. SQLite path repo-anchored (regression caught + fixed).
- `routes/jobs.py` — accepts all 5 workflows. POST validates per-workflow required fields (`ticker` for most, `tickers` for sector-sweep, `question` for thesis-check). Returns 501 if a workflow points to an unimplemented method.

**Canonical eval:**
- `tests/canonical/{NVDA,AAPL,JPM,XOM}/` — 8 fixture files per ticker (financials, profile, quote, peers, historical, treasury, fred, 10k.html).
- `tests/conftest_canonical.py` — helpers to build mock FMP/EDGAR/FRED clients backed by the fixtures.
- `tests/test_canonical_eval.py` — parameterized e2e test runs full deep-dive against each ticker. Confirms 11 output artifacts per run without hitting live APIs.

## 4. Critical landmines from Plan B execution (don't re-step on these)

### 4.1 Stage 2a `asyncio.gather` mock-ordering subtlety

When `mock_anthropic.messages.create.side_effect = [...]` lists Stage 2a responses in submission order `[industry, comps, macro, risk, technicals]`, the **actual call order** is governed by how many pre-LLM awaits each agent does. Approximate order: `risk (0 awaits) → technicals (1) → industry (2) → macro (3) → comps (~7)`.

This is harmless today because all 5 Stage 2a responses are interchangeable markdown strings. If you ever add structural validation to a Stage 2a agent's LLM response, the mock will silently break. The caveat is documented inline in `tests/test_orchestrator.py` and `tests/test_e2e.py`. Don't strip the comment.

### 4.2 SQLite path must be repo-anchored

`backend/config.py` defines `_REPO_ROOT = Path(__file__).resolve().parent.parent` and uses it as the `sqlite_path` default. This was a regression caught during Plan B Task 1 review — the spec accidentally replaced the absolute anchor with a CWD-relative path. **Don't re-introduce CWD-relative paths.**

### 4.3 `datetime.utcnow()` is deprecated

Use `datetime.now(timezone.utc)` instead. Already fixed in `job_repo.py` during Task 21 review. Watch for new occurrences.

### 4.4 matplotlib `boxplot(labels=...)` was renamed to `tick_labels=` in 3.9

Already fixed in `charts.py::box_plot`. The pinned version is matplotlib 3.9.2; if you bump it to 3.10+, also fix `boxplot(vert=True, ...)` → `boxplot(orientation="vertical", ...)` (currently emits `PendingDeprecationWarning` only on 3.10+, silent on 3.9.2).

### 4.5 lxml deprecation suppressed in `edgar_client._extract_sections`

Wrapped in `warnings.catch_warnings()` with `simplefilter("ignore", DeprecationWarning)`. `tests/test_no_lingering_warnings.py` locks this in. Don't unwrap.

### 4.6 FastAPI `on_event("startup")` is deprecated (pre-existing)

`backend/main.py` uses `@app.on_event("startup")` and `@app.on_event("shutdown")`. FastAPI now prefers a `lifespan` context manager. Not in Plan B scope but emits a deprecation warning every test run. Plan D could clean this up.

### 4.7 FMP /stable endpoint shapes (carried from Plan A)

- `/stable/profile` returns a list — extract `[0]`.
- `/stable/quote` returns a list — extract `[0]`.
- `/stable/historical-price-eod/full` returns `{symbol, historical: [...]}` envelope — extract `historical`.
- `/stable/stock-peers` returns `[{symbol, peers: [...]}]` — extract `[0].peers` and filter out self.
- `/stable/treasury-rates` takes no symbol param — uses its own cache key.

All handled in `FmpClient` — but if FMP changes shapes again, this is where to look.

### 4.8 Docker on Chris's machine binds `:::8000` (IPv6)

Use port 8001 or `127.0.0.1` explicitly when smoke-testing the backend. macOS prefers IPv6 when resolving `localhost`, so `curl http://localhost:8000/` may hit a stranded Docker container instead of uvicorn.

## 5. ⚠️ Plan B → Plan C contract

These are the surfaces Plan C will consume. Don't break them silently.

### 5.1 REST API

- `POST /jobs` — request body matches `backend/models/job.py::CreateJobRequest`:
  - `ticker: Optional[str]` (required for full-deep-dive, earnings-update, morning-note, thesis-check)
  - `tickers: Optional[list[str]]` (required for sector-sweep)
  - `workflow: str` (one of `full-deep-dive`, `earnings-update`, `morning-note`, `thesis-check`, `sector-sweep`)
  - `question: Optional[str]` (required for thesis-check)
  - Returns `JobState` synchronously when the orchestrator finishes.
- `GET /jobs/{job_id}` — returns persisted `JobState`.
- `GET /healthz` — returns `{"status": "ok"}`.

### 5.2 Job state shape (`backend/models/job.py::JobState`)

```python
{
  "id": str,                       # uuid
  "ticker": str,                   # uppercased; for sector-sweep, the first ticker
  "workflow": str,
  "status": "running" | "complete" | "failed",
  "current_stage": str | None,
  "stages": dict[str, str],        # per-agent: "complete" | "failed" | "skipped"
  "rating": "Buy" | "Hold" | "Sell" | None,
  "error": str | None,
  "created_at": datetime,
  "completed_at": datetime | None,
}
```

### 5.3 Synchronous request lifecycle (will need WebSocket in Plan C)

`POST /jobs` blocks until the pipeline finishes. For full-deep-dive that's ~7 minutes wall-clock. The browser client cannot keep an HTTP connection open that long — Plan C will need to:
- Convert `POST /jobs` to fire-and-forget (return job_id immediately, run pipeline in background).
- Add `GET /jobs/{id}/stream` WebSocket endpoint streaming agent tokens + state transitions.
- The orchestrator already calls `JobLogger.log_agent` per agent — Plan C could pipe that into the WS stream.

### 5.4 Filesystem layout (Plan C will read these)

Per spec §8, every ticker has:
```
<TICKER>/
├── fundamentals/{financials.json, kpis.json, 10k-excerpt.txt, section.md}
├── industry/{section.md, peer-share-chart.png}        # peer-share-chart NOT yet generated
├── dcf/{dcf.xlsx, football-field.png, sensitivity.png, section.md}
├── comps/{comps.xlsx, peer-multiples.json, box-plot.png, section.md}
├── macro/{section.md, catalyst-timeline.png}
├── risk/{section.md}
├── technicals/{section.md, price-chart.png}
├── synthesis/{_synthesis.md}
├── reports/{pitch.pptx, onepager.pdf, memo.docx}
└── _logs/{<job-id>.jsonl}
```

Plan C's `FolderTree` component should walk this exact structure.

### 5.5 Per-agent model overrides (informational for Plan C)

Plan C might surface a model picker in the UI. The env-var convention is:
```
ANTHROPIC_MODEL=claude-opus-4-7              # default
ANTHROPIC_MODEL_MACRO=claude-sonnet-4-6      # per-agent override
ANTHROPIC_MODEL_RISK=claude-sonnet-4-6
ANTHROPIC_MODEL_TECHNICALS=claude-sonnet-4-6
ANTHROPIC_MODEL_DECK_BUILDER=claude-sonnet-4-6
ANTHROPIC_MODEL_MEMO_BUILDER=claude-sonnet-4-6
```
`Settings.model_for("<agent>")` reads these.

## 6. Environment / secrets

`.env` is in place at the repo root with **real** keys. Gitignored.

Required:
- `ANTHROPIC_API_KEY`
- `FMP_API_KEY`
- `FRED_API_KEY` (Macro agent will fail without it)
- `SEC_EDGAR_USER_AGENT=Chris Lane chrislane1738@gmail.com` (SEC fair-use policy)

Optional:
- `RESEARCH_DIR=~/Documents/equity-research` (default)
- `ANTHROPIC_MODEL=claude-opus-4-7` (default)
- `ANTHROPIC_MODEL_<AGENT>` overrides (see §5.5)
- `SQLITE_PATH=./backend/db/research.sqlite` (default repo-anchored)
- `PORT_BACKEND=8000`, `PORT_FRONTEND=3000`
- `MAX_CONCURRENT_AGENTS=5`
- `DAILY_SPEND_WARN_USD=10`

`.env.example` lists all keys (with blanks for secrets) and is committed.

## 7. Chris's working preferences (from auto-memory + Plan B execution)

- **Subagent-driven development.** Controller dispatches a fresh subagent per task; spec review then code-quality review after each.
- **Work directly on main** for solo greenfield projects (explicitly approved for this repo).
- **TDD enforced** — write the failing test first, see it fail, then implement.
- **Brief, terse responses preferred.** No trailing summaries unless asked.
- **Per-scope authorization.** Confirm before destructive ops; never amend commits unless asked.
- **Smoke-test against real APIs is opt-in.** Chris runs it himself when ready.

## 8. How to verify current state in a fresh session

```bash
cd /Users/chrislane/Desktop/Claude_Code/public-equity-research-team
git log --oneline | head -5            # latest commit eb17319
source backend/venv/bin/activate
pytest tests/                           # 137 passed
python -c "from backend.config import get_settings; s = get_settings(); print(s.anthropic_model, s.research_dir, s.fred_api_key[:6] if s.fred_api_key else 'MISSING')"
```

Expected: 137 tests passing, Settings loads with FRED key non-empty.

## 9. Smoke-testing Plan B with real APIs (recommended before Plan C)

Plan A was smoke-tested live; Plan B has not been. Recommend running once before Plan C to catch any FMP/EDGAR drift.

```bash
cd /Users/chrislane/Desktop/Claude_Code/public-equity-research-team
source backend/venv/bin/activate
uvicorn backend.main:app --port 8001     # one terminal (8000 is the docker collision — see §4.8)

# another terminal
curl -X POST http://localhost:8001/jobs \
     -H "Content-Type: application/json" \
     -d '{"ticker":"NVDA","workflow":"full-deep-dive"}'
```

Expected: ~5-7 minutes wall-clock. Produces under `~/Documents/equity-research/NVDA/`:
- `reports/memo.docx`, `reports/pitch.pptx`, `reports/onepager.pdf`
- `dcf/dcf.xlsx`, `dcf/football-field.png`, `dcf/sensitivity.png`
- `comps/comps.xlsx`, `comps/box-plot.png`, `comps/peer-multiples.json`
- `industry/section.md`, `macro/section.md`, `risk/section.md`, `technicals/section.md`, `technicals/price-chart.png`, `macro/catalyst-timeline.png`
- `synthesis/_synthesis.md`
- `_logs/<job-id>.jsonl` (token + cost per agent)

Estimated cost ~$0.70-$1.50 per spec §15.

If anything breaks, the failure point will be one of:
1. FMP endpoint shape drift — error in `FmpClient` or downstream agent.
2. EDGAR rate limit / User-Agent rejection — error in `EdgarClient`.
3. Anthropic SDK kwargs — error in `Agent.run()`.
4. matplotlib backend issue — but `Agg` is set explicitly so unlikely.

## 10. Plan C scope (Next.js workspace UI)

Per spec §7. Greenfield — no frontend code exists yet beyond the directory placeholder Plan A scaffolded.

**Top bar:**
- Ticker picker (autocomplete from FMP `/stable/stock-list`, daily-cached locally).
- Quick-action buttons (right): `Full Deep-Dive`, `Earnings Update`, `Morning Note`, `Thesis Check`, `Sector Sweep`. Each pre-fills the MD chat with the appropriate prompt.

**Left sidebar:**
- Active: MD (pinned).
- Research: Fundamentals · Industry & Moat · DCF · Comps · Macro · Risk · Technicals.
- Production: Deck Builder · Memo Builder.
- Recent tickers: last 5.

**Tab bar:** One tab per open chat. MD pinned first. Closeable except MD.

**Center chat panel:**
- WebSocket streaming tokens from the active agent.
- MD tab: orchestration status (running agents, ETA, progress bar).
- Code/JSON collapsible.
- Artifact chips inline (`📊 dcf.xlsx — click to preview`).
- Unified history per agent (MD-dispatched runs + direct user follow-ups in one thread).

**Right panel — folder tree:**
- Tree view of `~/Documents/equity-research/<SELECTED_TICKER>/`.
- Click any file to preview in modal: xlsx → table preview, pptx → slide thumbnails, docx → rendered prose, png → image, json → syntax-highlighted, md → rendered markdown.
- Per-file download. "Open folder" opens macOS Finder.

**Notifications:** Toast (bottom-right) on long-job completion. Red toast on agent failure with retry.

**Theming:** Dark mode only for v1.

**Backend changes Plan C will need:**
- Convert `POST /jobs` to fire-and-forget (return job_id immediately).
- Add `GET /jobs/{id}/stream` WebSocket streaming `JobLogger` events + agent tokens.
- Add `GET /tickers` endpoint reading `~/Documents/equity-research/` directory.
- Add `GET /tickers/{ticker}/files` endpoint walking the ticker folder.
- Add file-preview endpoints (or have the frontend read directly via a static-mount).

**Tech stack (per spec §9):** Next.js 16 App Router · TypeScript · Tailwind · shadcn/ui · AI SDK `useChat` adapted for FastAPI WS · `react-pdf` · `mammoth` (docx preview) · `xlsx` (xlsx preview).

## 11. Plan D scope (CLI launchers)

Per spec §12. Small task (~5 tasks):
- `scripts/equity-research-setup` — Python venv, `pip install`, `npm install`, copy `.env.example` → `.env` if missing, create `~/Documents/equity-research/`, init SQLite. Idempotent.
- `scripts/equity-research-backend` — activate venv, `uvicorn backend.main:app --reload --port 8001` (8001 to dodge the docker collision).
- `scripts/equity-research-frontend` — `npm run dev` (auto-install if needed).
- `scripts/equity-research` — opens a new Terminal window with two tabs via `osascript`; runs both launchers.

All four symlinked into `~/.local/bin/`.

## 12. Open items / known issues

- 🟡 **`DAILY_SPEND_WARN_USD` env var read but not enforced.** Spec §15 calls this out as a v1 deferral. A future task (Plan C or a small follow-up) could wrap `JobLogger.total_cost_usd()` to emit a warning when daily aggregate crosses the threshold.
- 🟡 **matplotlib `boxplot(vert=True, ...)` will warn on 3.10+** (silent on pinned 3.9.2). One-line fix when matplotlib is bumped.
- 🟡 **FastAPI `@app.on_event("startup"/"shutdown")` is deprecated.** Pre-existing from Plan A. Migration to `lifespan` context manager is small but cross-cutting.
- 🟡 **Stage 3 (MD synth) and Stage 4 (Memo + Deck) currently propagate exceptions unhandled.** Stage 1, 2a, 2b all wrap in try/except and record to `state["errors"]`. Stage 3+4 inconsistency could leave a job in zombie "running" state if MD or production raises. Low-likelihood with mocked tests but worth tightening once we have real-API runs to learn from.
- 🟢 **Plan A's `industry/peer-share-chart.png` is referenced in `CHART_MAP` (deck_builder) but not yet generated by IndustryAgent.** The Deck Builder gracefully skips missing charts (Plan B Task 9 fix), so this is non-blocking — but a small enhancement to IndustryAgent to render the chart would polish slide 4 (Industry & Moat).
- 🟢 **No automated quality eval.** Per spec §16, v1 ships without it. Manual checklist in spec §16. The canonical eval (Task 28) only proves the pipeline runs; doesn't grade output quality.

## 13. Final notes

- 60 commits on `main` total (17 Plan A + 43 Plan B). Clean linear history. Don't rewrite.
- **Plan C will be substantially larger than Plan B** (~30-50 tasks) given full Next.js app + WebSocket plumbing + 6 file-preview integrations. Consider breaking into sub-plans: C1 = backend WS + preview endpoints, C2 = chrome (top bar + sidebar + tab bar + folder tree), C3 = chat panel + artifact previews, C4 = quick actions + ticker picker.
- **Plan D is small** (~5 tasks). Comes last.
- After Plan D, the project is feature-complete for v1. Per spec §17, multi-user / cloud / fixed-income / options are explicit non-goals.

Good luck.
