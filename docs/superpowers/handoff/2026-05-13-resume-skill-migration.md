# Handoff — Resume Skill-Based Migration

**Generated:** 2026-05-13
**Author:** Brainstorming session for the skill-based migration
**Audience:** Future Claude session picking up the migration plan + execution

---

## How to use this document

Open a fresh Claude Code session in `/Users/chrislane/Desktop/Claude_Code/public-equity-research-team/`. Paste this as the first message:

> "Read `docs/superpowers/handoff/2026-05-13-resume-skill-migration.md` end-to-end. Then read the approved spec at `docs/superpowers/specs/2026-05-13-skill-based-migration-design.md`. Brainstorm is complete; spec is approved. Cut a branch `feat/skill-based-migration` from `main`, then invoke the `superpowers:writing-plans` skill to draft the implementation plan against that spec. After the plan is approved, execute it with `superpowers:subagent-driven-development`. Chris will be working from `main` (no worktree). The keys are already in `.env`."

That's enough context to resume cleanly.

---

## 1. Project orientation (60 seconds)

A local-first, multi-agent equity research workstation. Originally built as a FastAPI backend + Next.js workspace (Plans A/B/C, ~5000 lines, 175 backend tests + 15 frontend tests + 2 Playwright e2e, currently on `main` and working). The user (Chris) decided the FastAPI/Next.js architecture is overkill for his use case — he's a single user iterating in a terminal who's already paying for a Claude plan. The migration replaces the entire architecture with a **skill-based design that runs inside Claude Code**: Claude as MD orchestrator, skills for in-context discipline, the Agent tool for parallel sub-agent dispatch, single self-contained HTML deliverable per ticker.

**The migration is on a branch.** `main` keeps the working FastAPI/Next.js build until the migration reaches parity. If anything goes sideways, `git checkout main` is the fallback.

**Why migrate (Chris's reasoning):**
- Plan B/C costs $0.70-$1.50 per deep-dive in API tokens, on top of his Claude plan. Wasteful for personal use.
- The Next.js workspace is real engineering, but a solo analyst doesn't need a live-streaming WebSocket dashboard. He needs structured outputs to scroll, search, share.
- Off-the-shelf skills (`equity-research:earnings-analysis`, `financial-analysis:dcf-model`, `financial-analysis:comps-analysis`, etc.) are strictly better than several of the custom agents. Use them.
- Operational pain (port collisions, "uvicorn died and the sidebar is empty," 175-test suite, frontend build pipeline) goes away.

## 2. Where we are at the start of the migration

- **Branch:** `main`. Latest commit: `418599f` (the spec). 33 commits since the Plan B baseline.
- **Test suite:** `pytest tests/` → **175 passed**; `cd frontend && npm test` → 15 passed; `cd frontend && npm run e2e` → 2 passed.
- **Backend is feature-complete.** All 5 workflows route through `POST /jobs`, every agent runs, every artifact lands on disk, jobs persist in SQLite, per-job JSONL telemetry under `<TICKER>/_logs/<job-id>.jsonl`, fire-and-forget + WebSocket streaming.
- **Frontend is feature-complete.** Next.js 16 + Tailwind 4 + shadcn workspace, 3-column shell (TopBar with TickerPicker autocomplete + connectivity pill, Sidebar with grouped agents + recent tickers, TabBar, ChatPanel with WS bridge + per-tab workflow buttons, FolderTree with copy-path, FilePreviewPanel that opens as a tab — md/json/png/xlsx/docx/pdf/pptx renderers).
- **Brainstorm complete; spec approved.** The migration spec lives at `docs/superpowers/specs/2026-05-13-skill-based-migration-design.md`.
- **The current FastAPI/Next.js work will be DELETED on the migration branch.** Don't worry about preserving its tests — `main` has them.

## 3. Spec summary (read the full doc — this is the cliffs notes)

**Architecture:** Claude Code is the MD. Two primitives:
- **Skill (loads into Claude's own context, no fork):** `md-synthesis`, `synthesize-html`, `screen` (when interactive).
- **Agent (subagent in isolated context, parallel-safe):** every research and production agent.

**Workflow execution (deep-dive example):**
1. Claude dispatches `fundamentals` as a subagent (deep-research: FMP + EDGAR + WebSearch + WebFetch).
2. Claude dispatches `industry-moat`, `comps`, `macro`, `risk-upside`, `technicals` in parallel (5 Agent calls in one message).
3. After Comps writes `peer-multiples.json`, Claude dispatches `dcf` (wrapper around `financial-analysis:dcf-model`).
4. Claude reads section.md files, invokes `md-synthesis` skill into its own context, writes synthesis.
5. Claude dispatches `deck-builder` and `memo-builder` in parallel.
6. Claude invokes `synthesize-html` skill, writes `<TICKER>/report.html` (single self-contained file with embedded base64 charts).

**Skill inventory (12 total):**
- **Custom (preserve existing prompts + add WebSearch/WebFetch):** `fundamentals`, `industry-moat`, `macro`, `risk-upside`, `technicals`, `md-synthesis`.
- **Wrapper (thin custom layer over off-the-shelf):** `dcf` → `financial-analysis:dcf-model`; `comps` → `financial-analysis:comps-analysis`; `memo-builder` → `equity-research:earnings-analysis` (earnings) | custom (deep-dive); `deck-builder` → `financial-analysis:pptx-author`.
- **New:** `synthesize-html`, `screen` → wraps `equity-research:idea-generation`.

**7 workflows + /help slash command:**
- `/deep-dive <T>`, `/earnings <T>`, `/morning <T>`, `/thesis <T> "<q>"`, `/sector <T1> <T2> …`, `/screen "<criteria>"`, `/catalysts <T>`, `/help`.
- All also work as natural-language prompts. Slash commands live in `.claude/commands/`. Reference doc at `COMMANDS.md` at repo root.

**Data layer:**
- `tools/marketdata/` exposes a `MarketData` class.
- FMP primary, yfinance fallback (keyless Yahoo scraping; normalize shape to FMP's).
- FRED for macro, EDGAR for filings — separate dedicated clients (no abstraction needed).
- **No FactSet / Kensho / Daloopa / Moody's / LSEG / PitchBook.** Chris confirmed: TEEDUP (his May 2026 internship) is a different role and won't provide institutional data access. FMP + yfinance is the permanent answer.

**Comps auto-screening (3-tier):**
1. User pins via `--peers AMD,AVGO,ARM` (always included).
2. FMP curated via `/stable/stock-peers` (skipped if `--peers-only` flag).
3. FMP screener with default criteria (same SIC industry, market cap 0.25x-4x, major US exchange, positive revenue).
LLM-half of the agent prunes to 8-12 final peers and logs the rationale.

**Deliverable:** Single self-contained `<TICKER>/report.html` — embedded base64 PNG charts, inline CSS, no external assets, links to companion .xlsx/.pptx/.docx via relative paths. Print-friendly (`@media print`).

## 4. Critical context for the implementation plan

### 4.1 What survives the migration (KEEP — refactored locations)

- All system prompts in `backend/agents/{fundamentals,industry,dcf,comps,macro,risk,technicals,md,deck_builder,memo_builder}.py` — migrate verbatim into `.claude/skills/*.md` bodies. **The LLM-half prompt becomes the skill body; the deterministic-half code becomes Python helpers in `tools/` that the skill invokes via Bash/Python.**
- `backend/tools/{fmp_client,edgar_client,fred_client,multiples,dcf_engine,charts}.py` → move to `tools/`. `fmp_client.py` becomes part of the new `tools/marketdata/` package as `tools/marketdata/fmp.py`.
- `tests/canonical/` (NVDA/AAPL/JPM/XOM fixtures) — preserved verbatim.
- `tests/test_{edgar,fred,multiples,dcf_engine,charts}.py` — preserved.
- `.env`, `.env.example`, `pytest.ini`.
- `scripts/seed_demo.py` — still useful for testing the HTML output.

### 4.2 What dies (DROP entirely on the migration branch)

- `backend/main.py`, `backend/routes/`, `backend/db/`, `backend/job_runner.py`, `backend/observability/` (event_bus, semaphore_client, JobLogger).
- `backend/cik_resolver.py`, `backend/orchestrator.py`, `backend/agents/base.py`.
- `backend/config.py` → simplified into a small `tools/settings.py` (just dotenv-loaded keys).
- `frontend/` (entire Next.js app).
- `tests/test_{routes,e2e,job_runner,job_logger,event_bus,jobs_routes,files_routes,tickers_search}.py` — these test the dropped infrastructure.

### 4.3 What's added

- `CLAUDE.md` at repo root (~50 lines) — frames Claude as MD when the user `cd`s in.
- `COMMANDS.md` at repo root — workflow reference.
- 12 skill files under `.claude/skills/`.
- 8 slash command files under `.claude/commands/`.
- `tools/marketdata/` package with FMP + yfinance + tests.
- `tools/html_writer.py` (~200 lines).

### 4.4 Open questions (deferred to plan, not blockers)

- SIC industry mapping for the auto-screen — FMP returns industry strings; confirm the screener accepts them or needs SIC codes.
- `synthesize-html` impl: deterministic Python templating (recommended) or LLM call.
- Canonical-eval test: mock the LLM, exercise the real Python helpers (recommended).
- Whether to keep `dcf_engine.py` at all, or drop it once the dcf skill defers to off-the-shelf for Excel. Recommendation: keep the WACC/FCF math, drop the Excel-writing parts.

### 4.5 Migration mechanics (don't deviate)

- Branch from `main`: `git checkout -b feat/skill-based-migration`.
- `git rm` dropped files in their own commit (reviewable + reversible).
- Each new skill file in its own commit — preserves prompt-engineering history per file.
- Final merge to `main` only after canonical eval passes AND a real-ticker smoke (one full deep-dive on NVDA via Claude Code, eyeball the HTML report).

## 5. Plan A/B/C → Skill Migration contracts

These are surfaces the migration WILL preserve so existing artifacts on disk aren't orphaned.

### 5.1 Filesystem layout under `~/Documents/equity-research/<TICKER>/`

UNCHANGED. Per spec §8 of the original design:
```
<TICKER>/
├── fundamentals/{financials.json, kpis.json, 10k-excerpt.txt, section.md}
├── industry/{section.md, peer-share-chart.png}
├── dcf/{dcf.xlsx, football-field.png, sensitivity.png, section.md}
├── comps/{comps.xlsx, peer-multiples.json, box-plot.png, section.md}
├── macro/{section.md, catalyst-timeline.png}
├── risk/{section.md}
├── technicals/{section.md, price-chart.png}
├── synthesis/{_synthesis.md}
├── reports/{pitch.pptx, onepager.pdf, memo.docx}
└── _logs/  (only populated if a future feature wants structured logs)
```
Plus the new addition: `<TICKER>/report.html` at the ticker root.

### 5.2 Existing on-disk tickers

Currently on Chris's machine: `~/Documents/equity-research/{NVDA, ANET, DEMO}/`. NVDA is a real Plan B run; ANET is an earnings-update; DEMO was seeded by `scripts/seed_demo.py` for UI testing. The migration must not destroy any of these — they remain valid inputs for testing the new skill pipeline (e.g., re-run `synthesize-html` against an existing NVDA folder).

### 5.3 What dies at the API layer

- `POST /jobs`, `GET /jobs/{id}`, `WS /jobs/{id}/stream`, `GET /tickers`, `GET /tickers/{t}/files`, `GET /files`, `GET /tickers/search`, `GET /tickers/{t}/path`, `GET /healthz` — all gone. Nothing in the new architecture exposes HTTP.

## 6. Environment / secrets

`.env` is in place at the repo root with **real** keys. Gitignored.

Required for skills to work:
- `FMP_API_KEY` — primary data source
- `FRED_API_KEY` — Macro skill will fail without it
- `SEC_EDGAR_USER_AGENT` — `Chris Lane chrislane1738@gmail.com` (SEC fair-use policy)

Optional / no longer needed:
- `ANTHROPIC_API_KEY` — was needed for the FastAPI backend's per-token API calls. **The new architecture doesn't make API calls** — Claude Code uses Chris's existing plan. If a skill needs to call Anthropic directly for some reason (it shouldn't, but allow), the key still exists.
- `SQLITE_PATH`, `PORT_BACKEND`, `PORT_FRONTEND`, `MAX_CONCURRENT_AGENTS`, `DAILY_SPEND_WARN_USD` — no longer relevant.

`.env.example` should be trimmed to the three required keys + the optional ANTHROPIC_API_KEY during the migration.

## 7. Chris's working preferences (carried from earlier handoff)

- **Subagent-driven development.** Controller dispatches a fresh subagent per task; spec review then code-quality review after each.
- **Work directly on the migration branch (`feat/skill-based-migration`).** Don't make a worktree — Chris will be working from his main checkout.
- **TDD enforced** — write the failing test first, see it fail, then implement. Applies to Python helpers; skill prompts themselves don't have unit tests beyond the canonical eval.
- **Brief, terse responses preferred.** No trailing summaries unless asked.
- **Per-scope authorization.** Confirm before destructive ops; never amend commits unless asked.
- **Live API smoke is opt-in.** Chris runs it himself when ready.

## 8. How to verify current state in a fresh session

```bash
cd /Users/chrislane/Desktop/Claude_Code/public-equity-research-team
git log --oneline | head -5            # latest commit 418599f (the spec)
git branch                              # currently on main
git status                              # clean

# Backend suite still passes (we haven't touched anything yet)
source backend/venv/bin/activate
pytest tests/                           # 175 passed

# Frontend suite still passes
cd frontend && npm test                 # 15/15
cd .. && ls ~/Documents/equity-research/  # NVDA, ANET, DEMO
```

Expected: 175 backend tests passing, 15 frontend tests passing, three on-disk tickers, no in-flight uncommitted work.

## 9. The opening prompt to paste in the next session

```
Read `docs/superpowers/handoff/2026-05-13-resume-skill-migration.md` end-to-end.
Then read the approved spec at `docs/superpowers/specs/2026-05-13-skill-based-migration-design.md`.
Brainstorm is complete; spec is approved.
Cut a branch `feat/skill-based-migration` from `main`, then invoke the
`superpowers:writing-plans` skill to draft the implementation plan against that spec.
After the plan is approved, execute it with `superpowers:subagent-driven-development`.
I'll be working from `main` (no worktree). The keys are already in `.env`.
```

## 10. Final notes

- **Don't re-brainstorm.** Every architectural decision in the spec was deliberate. If something seems wrong or missing, FLAG IT — don't silently change it.
- **Don't preserve FastAPI/Next.js code on the migration branch.** It's all on `main`. The whole point of the migration is to delete it.
- **The off-the-shelf skills (`financial-analysis:dcf-model`, etc.) are strictly better than the equivalent custom prompts for the wrapper agents.** Don't try to keep both — adopt the off-the-shelf, layer Chris's framing on top in a thin wrapper.
- **The deep-research stance for `fundamentals` and `industry-moat` is critical.** Those skills are the highest-value qualitative work. They MUST use WebSearch + WebFetch in addition to FMP + EDGAR. They are not template-fill exercises.
- **The HTML deliverable is the canonical output.** Companion .xlsx / .pptx / .docx still get written, but the HTML is what Chris reads and shares.
- **Cost target: $0 net new vs. Chris's existing Claude plan + FMP subscription.** If a design choice would re-introduce per-token API spend (e.g., having a skill call `anthropic.messages.create` directly), reject it — Claude Code is the only LLM caller in the new architecture.

Good luck.
