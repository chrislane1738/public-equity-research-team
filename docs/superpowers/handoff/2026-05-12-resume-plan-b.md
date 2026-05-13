# Handoff — Resume Plan B (Public Equity Research Team)

**Generated:** 2026-05-12
**Author:** Plan A execution session
**Audience:** Future Claude session picking up Plan B / C / D

---

## How to use this document

Open a fresh Claude Code session in `/Users/chrislane/Desktop/Claude_Code/public-equity-research-team/`. Paste this as the first message:

> "Read `docs/superpowers/handoff/2026-05-12-resume-plan-b.md` end-to-end, then write Plan B per the existing spec at `docs/superpowers/specs/2026-05-12-public-equity-research-team-design.md`. Use the `superpowers:writing-plans` skill. After Plan B is approved, execute it with `superpowers:subagent-driven-development`. I'll be working on `main` directly. The keys are already in `.env`."

That's enough context to resume cleanly. Everything below is reference material for the new session.

---

## 1. What this project is (60-second orientation)

A local-first, 10-agent equity research workstation modeled on Morgan Stanley / Goldman Sachs sellside desks. The user ("Chris", role: serious DIY finance/quant, see `~/.claude/.../memory/user_chris.md`) wants to produce institutional-grade investment research (pitch deck + memo + one-pager + Excel models) by typing a ticker into a local chat UI.

**Architecture (locked):** Next.js 16 frontend (`localhost:3000`) + FastAPI Python backend (`localhost:8000`) + SQLite + local filesystem under `~/Documents/equity-research/<TICKER>/`. Single user, no auth, no deploy.

**The full design spec lives at:** `docs/superpowers/specs/2026-05-12-public-equity-research-team-design.md`. Read it. It's the source of truth for product decisions.

## 2. Plan decomposition (4 plans)

| # | Plan | Status | Deliverable |
|---|---|---|---|
| **A** | Backend skeleton + MVP pipeline | **DONE** (29 tests green) | `curl POST /jobs` → real `memo.docx` on disk via stubbed pods |
| **B** | Full agent roster + production tier | **NOT STARTED** | 6 real research agents, deterministic toolkit, Deck Builder, one-pager, alternative workflows |
| **C** | Next.js workspace UI | **NOT STARTED** | Browser chat UI: tabs, sidebar, ticker-folder tree, file previews, WS streaming |
| **D** | CLI launchers + dev polish | **NOT STARTED** | `equity-research-setup`, `-backend`, `-frontend`, combined `equity-research` osascript |

Plan A's plan file is at `docs/superpowers/plans/2026-05-12-plan-a-backend-mvp-pipeline.md`. Use it as a template for Plan B's style (TDD, exact-code steps, frequent commits).

## 3. Plan A — what shipped

17 commits on `main`, latest is `cb19736`. Test suite: **29 passing in ~1 second**.

```
backend/
├── main.py                      # FastAPI app + uvicorn entrypoint with .env-guarded glue
├── orchestrator.py              # 4-stage Full Deep-Dive pipeline runner
├── config.py                    # Settings (env vars, path resolution) + get_settings() cached
├── agents/
│   ├── base.py                  # Agent class wrapping Anthropic SDK; AgentResult + cost calc
│   ├── md.py                    # MD synthesis (SECTION_ORDER export)
│   ├── fundamentals.py          # Real: FMP financials + EDGAR 10-K excerpt + LLM KPIs
│   ├── memo_builder.py          # Real: LLM writes memo markdown → write_memo() → docx
│   └── _stubs.py                # 6 stub research pods (PLAN B REPLACES THESE)
├── tools/
│   ├── fmp_client.py            # FMP HTTP client w/ daily TTL filesystem cache
│   ├── edgar_client.py          # SEC EDGAR client + Item 1/1A/7 text extractor
│   └── docx_writer.py           # python-docx wrapper: write_memo(path, title, sections)
├── db/
│   ├── schema.sql               # agents / chat_messages / jobs / tickers
│   └── sqlite_client.py         # async aiosqlite wrapper, dict rows
├── models/job.py                # CreateJobRequest, JobState pydantic
└── routes/jobs.py               # POST /jobs (synchronous in Plan A) + GET /jobs/:id
tests/
├── fixtures/
│   ├── edgar_nvda_10k.html
│   ├── fmp_nvda_financials.json
│   └── .gitkeep
└── test_*.py                    # 12 test files, 29 tests total
pytest.ini                       # AT REPO ROOT (not backend/!) — asyncio_mode=auto
.env / .env.example              # .env has real keys (gitignored)
```

## 4. ⚠️ Critical landmines from Plan A execution (don't re-step on these)

### 4.1 `pytest.ini` MUST be at repo root

The original plan had it at `backend/pytest.ini`. When pytest is invoked from repo root with `pytest tests/...`, the rootdir resolves to repo root and `backend/pytest.ini` is **NOT** discovered. The result: `asyncio: mode=Mode.STRICT` and every `async def test_*` silently fails. **The fix is in place** — `pytest.ini` is at the repo root. Don't move it back.

### 4.2 respx 0.21.1 + httpcore default mocker is broken for HTTP method matching

Bare `@respx.mock` with `respx.get(...)` calls fails because httpcore passes `b'GET'` (bytes) to the pattern matcher while patterns are compared against `'GET'` (str). The fix used throughout:

```python
@respx.mock(using="httpx")
async def test_foo(respx_mock):
    respx_mock.get("https://example.com/x").mock(return_value=Response(200, json={...}))
```

Note: `using="httpx"` parameter + `respx_mock` parameter fixture. The bare form will silently break. See `tests/test_fmp_client.py`, `tests/test_edgar_client.py` for the pattern.

### 4.3 respx + FastAPI TestClient conflict (only relevant if you mix them again)

`fastapi.testclient.TestClient` uses synchronous `httpx.Client` against an in-process ASGI app at `http://testserver/`. If respx tries to intercept all httpx calls, it also intercepts TestClient's internal calls and returns empty 200 responses, breaking your tests.

`tests/test_e2e.py` solves this by patching only `httpx.AsyncClient` (used by FmpClient/EdgarClient), leaving `httpx.Client` untouched. See the test for the exact pattern. Plan B/C tests that use both TestClient and respx should follow the same pattern.

### 4.4 Empty directories don't survive `git clone`

Add `.gitkeep` files (or commit a real file) to any directory the code expects to find. `tests/fixtures/` has one already.

### 4.5 `import re` was in Plan A's spec for `memo_builder.py` but isn't used

Harmless unused import. Plan B can clean it up if it touches `memo_builder.py` anyway.

## 5. ⚠️ Plan A → Plan B contract — read this before writing Plan B

These are intentional simplifications in Plan A that Plan B will replace. Don't break them silently.

### 5.1 Hard-coded ticker→CIK map in `backend/main.py`

```python
_CIK_MAP = {"NVDA": "0001045810", "AAPL": "0000320193", "MSFT": "0000789019"}
```

Plan B should replace this with an FMP-based lookup (FMP's `/v3/profile/{ticker}` returns `cik`). Update both `main.py` and the `Orchestrator(...)` constructor signature accordingly — the orchestrator currently takes `ticker_to_cik: dict[str, str]`.

### 5.2 Stub research pods at `backend/agents/_stubs.py`

The 6 stubs (industry, dcf, comps, macro, risk, technicals) each just write a placeholder section.md. Plan B replaces them with real agents:
- Move each to its own file: `backend/agents/industry.py`, `backend/agents/dcf.py`, etc.
- Update `backend/orchestrator.py` to import them individually and dispatch via `asyncio.gather`
- Delete `backend/agents/_stubs.py` and `tests/test_stubs.py` once the real agents exist
- The `Orchestrator` stage 2 currently dispatches all 6 in parallel. The spec calls for **Stage 2a (parallel)** = Industry, Comps, Macro, Risk, Technicals, and **Stage 2b (after Comps)** = DCF (DCF reads `comps/peer-multiples.json` for its exit-multiple anchor). Plan B must enforce this ordering.

### 5.3 Stages, workflow modes, in-memory job state

Plan A only implements `full-deep-dive`. The spec lists 4 more workflows: `earnings-update`, `morning-note`, `thesis-check`, `sector-sweep`. The `POST /jobs` route currently 400s on anything other than full-deep-dive.

Job state is an in-memory dict in `backend/routes/jobs.py`. Plan B should persist it via `backend.db.sqlite_client` (the schema table `jobs` already exists). This is also what Plan C's WebSocket streaming will need to read.

### 5.4 Production tier — only Memo Builder exists

Plan A produces `reports/memo.docx`. Plan B adds:
- **Deck Builder** (`backend/agents/deck_builder.py`) → `reports/pitch.pptx` + `reports/onepager.pdf`
- **Charts utility** (`backend/tools/charts.py`) — matplotlib renderers, transparent bg for deck embedding
- **pptx_writer** (`backend/tools/pptx_writer.py`) — python-pptx wrapper, 14-slide template
- **pdf_writer** (`backend/tools/pdf_writer.py`) — reportlab one-pager

### 5.5 Deterministic toolkit (not yet built)

Plan B needs to add:
- `backend/tools/multiples.py` — manual EV/EBITDA, P/E, EV/Sales, EV/cRPO (for SaaS), FFO multiples (for REITs)
- `backend/tools/dcf_engine.py` — WACC calc, FCF projection, GGM + Exit Multiple + Blend terminal value, sensitivity grids (WACC × g and WACC × exit multiple)
- `backend/tools/xlsx_writer.py` — openpyxl-based xlsx generator with the tabs defined in spec §4

### 5.6 Synchronous request lifecycle

`POST /jobs` blocks until the pipeline finishes (~7 min for full deep-dive). Plan C will move this to a background task + WebSocket. Plan B can keep it synchronous, but consider whether the rate-limit semaphore the spec mentions (`MAX_CONCURRENT_AGENTS`) needs to wrap the Anthropic calls.

### 5.7 Per-agent model assignment

Spec §9 has the per-agent Opus/Sonnet table. Plan A's orchestrator passes `opus_model` and `sonnet_model` strings into agents. Plan B should:
- Honor the table: Industry, DCF, Comps stay on Opus; Macro, Risk, Technicals, Deck Builder, Memo Builder go on Sonnet
- Support `ANTHROPIC_MODEL_<AGENT>` env var overrides per spec §11

### 5.8 The `tests/canonical/` reference fixtures

Spec §16 calls for `tests/canonical/{NVDA,AAPL,JPM,XOM}/` — Plan A's repo layout includes the directory but no fixtures live there yet. Plan B (or D) should populate them so canonical-ticker eval runs are reproducible without hitting live FMP.

## 6. Environment / secrets

`.env` is in place at the repo root with **real** keys. It's gitignored (`.gitignore` line 2). Do not echo the keys; do not commit `.env`.

Env vars present:
- `ANTHROPIC_API_KEY` (real)
- `FMP_API_KEY` (real)
- `FRED_API_KEY` (real — for Plan B Macro agent)
- `SEC_EDGAR_USER_AGENT=Chris Lane chrislane1738@gmail.com` (required by SEC fair-use policy)
- `RESEARCH_DIR=~/Documents/equity-research`
- `ANTHROPIC_MODEL=claude-opus-4-7`
- Plus `PORT_BACKEND`, `PORT_FRONTEND`, `MAX_CONCURRENT_AGENTS`, `DAILY_SPEND_WARN_USD`

`.env.example` lists all keys (with blanks for secrets) and is committed.

## 7. User's working preferences (from auto-memory)

These are observed in this project's execution; cross-reference with `~/.claude/projects/-Users-chrislane-Desktop-Claude-Code/memory/`.

- **Subagent-driven development.** Chris wants the controller to dispatch fresh subagents per task. See `feedback_subagent_manager.md`.
- **Work directly on main** for solo greenfield projects (explicitly approved for this repo).
- **TDD enforced** — every Plan A task wrote test before implementation.
- **Brief, terse responses preferred** — no trailing summaries unless asked.
- **Authorization is per-scope** — re-confirm before destructive ops; never amend commits unless asked.

## 8. How to verify current state in a fresh session

```bash
cd /Users/chrislane/Desktop/Claude_Code/public-equity-research-team
git log --oneline | head -20            # 19 commits, most recent cb19736
source backend/venv/bin/activate
pytest tests/                           # 29 passed
python -c "from backend.config import get_settings; s = get_settings(); print(s.anthropic_model, s.research_dir)"
```

Expected: 29 tests passing, Settings loads from `.env`.

## 9. Smoke-testing Plan A with real APIs (optional)

When you're ready to test Plan A against real Anthropic/FMP/EDGAR:

```bash
cd /Users/chrislane/Desktop/Claude_Code/public-equity-research-team
source backend/venv/bin/activate
uvicorn backend.main:app --port 8000   # one terminal

# another terminal
curl -X POST http://localhost:8000/jobs \
     -H "Content-Type: application/json" \
     -d '{"ticker":"NVDA","workflow":"full-deep-dive"}'
```

Expected: ~30 seconds (only one real Opus call for KPI ID, plus FMP + EDGAR), produces `~/Documents/equity-research/NVDA/reports/memo.docx`. Cost ~$0.05-0.15.

If it works, you've validated the plumbing end-to-end on live infrastructure. If it doesn't, the failure point will be in one of: FMP API auth, EDGAR User-Agent header, or Anthropic SDK kwargs. Log shows up in uvicorn output.

## 10. Suggested order for the next session

1. Read this handoff doc top-to-bottom.
2. Read the spec at `docs/superpowers/specs/2026-05-12-public-equity-research-team-design.md` (it's the long-form product spec; you'll need it for every Plan B decision).
3. Run `pytest tests/` to confirm green baseline.
4. Optionally run the smoke test (§9).
5. Use `superpowers:writing-plans` to draft Plan B. Reference Plan A's plan file at `docs/superpowers/plans/2026-05-12-plan-a-backend-mvp-pipeline.md` for style/format.
6. Ask Chris to approve Plan B before executing.
7. Use `superpowers:subagent-driven-development` to execute, same pattern as Plan A.

## 11. Open items / known issues to fix in Plan B

- 🟡 `backend/agents/memo_builder.py` has an unused `import re`. Remove when touching the file.
- 🟡 Plan A leaves a `lxml` DeprecationWarning in tests (BeautifulSoup internal — `strip_cdata` option deprecation). Cosmetic, not blocking.
- 🟡 The hard-coded `_CIK_MAP` in `backend/main.py` only knows 3 tickers. Replace with FMP-based lookup before any non-NVDA/AAPL/MSFT ticker is requested.
- 🟡 Job state lives in-memory in `backend/routes/jobs.py` — vanishes on process restart. Persist via `backend.db.sqlite_client` early in Plan B.
- 🟡 No rate-limit semaphore yet. `MAX_CONCURRENT_AGENTS` is in the Settings but not yet enforced anywhere.
- 🟢 The spec mentions `_logs/<job-id>.jsonl` per-job telemetry — Plan A doesn't write logs. Add in Plan B.
- 🟢 Pricing dict in `backend/agents/base.py` is placeholder. Re-verify the actual Opus 4.7 / Sonnet 4.6 prices when finalizing.

## 12. Final notes

- The 17-commit history on `main` is clean and chronological. Don't rewrite it.
- Plan B will be substantially larger than Plan A (~25-40 tasks). Consider breaking into two sub-plans: B1 = research agents + toolkit, B2 = production tier + alternative workflows.
- Plan C (frontend) should be planned only after Plan B's API surface stabilizes — the WebSocket contract depends on B's job-state model.
- Plan D (launchers) is small, ~5 tasks, can come last.

Good luck.
