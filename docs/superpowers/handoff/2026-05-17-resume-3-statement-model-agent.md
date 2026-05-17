# Resume — 3-Statement Model Agent (brainstorming in progress)

**Date:** 2026-05-17
**Repo:** `/Users/chrislane/Desktop/Claude_Code/public-equity-research-team` — branch `main`, all pushed to `github.com/chrislane1738/public-equity-research-team` (public). Working tree clean.
**Status:** Mid-brainstorm. Using the `superpowers:brainstorming` skill to design a new **3-statement model agent** for the equity-research desk. Stopped before auto-compaction.

## How to resume

Open a fresh Claude Code session in the repo. First message:

> Resume brainstorming the 3-statement model agent — see `docs/superpowers/handoff/2026-05-17-resume-3-statement-model-agent.md`. Continue the `superpowers:brainstorming` skill from the clarifying-questions step.

Re-invoke `superpowers:brainstorming` and continue from checklist step 3 (clarifying questions) — Q1 is already resolved (below).

## The idea

A new skill/agent for the `/deep-dive` pipeline, with **two firing points**:

- **Phase 1 — model build.** Fires after `accountant` + `fundamentals`, before the 5 research pods. Builds a linked 3-statement projection (income statement, balance sheet, cash flow) from the audited accountant/fundamentals data. Serves as the projection base for the rest of the desk.
- **Phase 2 — scenario analysis.** Fires after `md-synthesis`. Takes the MD synthesis, identifies the **top 3-5 most impactful events/scenarios** that could occur, runs them through the 3-statement model, and analyzes the outcomes.

## Decisions made

- **Q1 — model vs DCF: RESOLVED → Option 1 ("Model feeds the DCF").** The 3-statement model becomes the **single projection engine**. The DCF's segment-revenue build and FCF path move *into* the model; the `dcf` skill stops projecting on its own and just discounts the model's FCF. One source of truth, no drift. This restructures the `dcf` skill to consume the model's output.

## Open questions — resume the clarifying-questions phase here (one at a time)

1. **Scenario type** — discrete catalyst events (earnings miss, an acquisition, a guide cut, a rate shock) vs thematic bull/base/bear vs both. And how phase-2 scenario analysis relates to / builds on the existing `risk-upside` pod (which already produces bull/bear cases + a bear-case PT). Avoid duplicating risk-upside.
2. **Model depth / horizon** — projection years (the DCF uses 5), driver granularity, and whether the model is a formula-driven `.xlsx` consistent with the `dcf.xlsx` / `comps.xlsx` house standard (formula-driven, ticker-prefixed filename, reference-integrity check).
3. **Phase-2 placement mechanics** — is phase 2 a second firing of the same skill, a separate late pod, or a step folded near Checkpoint C? How it threads into the existing pipeline ordering and the `/deep-dive` command.
4. **Output artifacts** — which files (`<TICKER> model.xlsx`? `model/section.md`? a scenario table/chart?), and whether the model also feeds `md-synthesis` and/or `comps`.
5. **Skill naming** — e.g. `model`, `three-statement`, `model-builder`.

## Brainstorming checklist state (`superpowers:brainstorming`)

1. Explore project context — **DONE**
2. Offer visual companion — **skipped** (conceptual/architecture topic, not visual)
3. Ask clarifying questions — **IN PROGRESS** (Q1 resolved; questions 1-5 above remain)
4. Propose 2-3 approaches — pending
5. Present design — pending
6. Write design doc → `docs/superpowers/specs/2026-05-17-3-statement-model-agent-design.md` — pending
7. Spec self-review + user review gate — pending
8. Transition to `writing-plans` — pending

## Project context for the resuming session

- The desk: Claude Code (Managing Director) orchestrates **13 skills** (`.claude/skills/`) + **9 commands** (`.claude/commands/`).
- **Deep-dive pipeline** (`.claude/commands/deep-dive.md`): validate ticker → `accountant` → **Checkpoint A** (user reviews reconciliation) → **Checkpoint B** (user supplies peer list) → `fundamentals` → 5 research pods in parallel (`industry-moat`, `comps`, `macro`, `risk-upside`, `technicals`) → `dcf` → `md-synthesis` (in-context) → **Checkpoint C** (deliverable choice) → production (`memo-builder`, `deck-builder`, `synthesize-html`).
- The new agent's **phase 1** slots between `fundamentals` and the 5 pods; **phase 2** slots after `md-synthesis` (around Checkpoint C).
- **Output location:** `~/Desktop/Agentic_Equity_Reports/<TICKER>/` — NOT the repo (set by `RESEARCH_DIR` in `tools/settings.py`). Deliverables stay out of git.
- **Key data contracts:**
  - `fundamentals/financials.json` — fundamentals' canonical base: `annual` / `quarterly` statements, `ttm`, `ratios`, `live_quote`, `latest_quarter`, and a `segments` block (audited reportable-segment revenue).
  - `accountant/reconciliation.json` — SEC-vs-FMP reconciliation (now 4 periods: latest 10-K + 3 most recent 10-Qs) plus the audited `segments` block.
- The `dcf` skill currently builds a 5-year **segment-driven** FCF projection in a formula-driven `<TICKER> dcf.xlsx` (first sheet `Revenue Build`). Under the resolved Q1, that projection logic moves into the new model agent and the DCF consumes it.
- Excel deliverables are **ticker-prefixed** (`<TICKER> dcf.xlsx`, `<TICKER> comps.xlsx`, etc.) and **formula-driven**; the `dcf` skill mandates a programmatic reference-integrity check.

## What shipped earlier this session (all on `main`, pushed)

Recent commits (newest first):

```
0bcb3ac feat(accountant): reconcile the full TTM base — FY + 3 most recent 10-Qs
b3acfd4 feat(md-synthesis): add Idiosyncratic & Systematic Risk subsections
79613e1 feat(technicals): indicator suite, per-indicator charts, expanded skill
d0e4e2b feat(technicals): extend price history pull to 3 years
3b7cffd fix(marketdata): fall back to yfinance on FMP errors, not just empties
57b3a41 feat: ticker-prefix the memo, deck, and one-pager deliverables
99640fb feat: ticker-prefix the DCF and comps Excel models
8066c40 docs(dcf): mandate programmatic reference-integrity check
6e72e66 feat(dcf): segment-driven bottom-up revenue build
1cceff8 fix(html_writer): strip synthesis frontmatter; doc deep-dive cost
```

Highlights: the DCF gained a segment-driven bottom-up revenue build (accountant extracts/audits segment revenue → fundamentals carries it in `financials.json` → DCF builds on it); a new `tools/indicators.py` module (VWAP, MACD, Bollinger, ADX, volume-by-price, etc.) with the technicals skill rewritten for a 3-year pull + per-indicator charts; ticker-prefixed Excel/doc deliverables; MarketData hardened to fall back to yfinance on FMP errors. **197 tests pass.**

## ADBE deep-dive state (the live coverage example)

ADBE was deep-dived this session — artifacts at `~/Desktop/Agentic_Equity_Reports/ADBE/`. Rating **Buy**, PT **$315**. The DCF, technicals, and synthesis were regenerated with the new features. `report.html` is current. No rerun pending.
