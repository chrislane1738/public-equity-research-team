# 3-Statement Model Agent — Design

**Date:** 2026-05-17
**Status:** Approved — ready for implementation planning
**Topic:** A new `model` skill — the single forward-projection engine for the equity-research desk

## Context

The deep-dive desk currently has no dedicated projection engine. The forward
revenue projection lives inside the `dcf` skill: `dcf` builds a segment-driven
"Revenue Build" sheet as the first sheet of `<TICKER> dcf.xlsx`, projects free
cash flow off it, and then discounts. There is no linked balance sheet or cash
flow statement, and no scenario analysis beyond `risk-upside`'s qualitative
bull/bear narratives.

This design introduces a new desk skill, **`model`**, that owns the projection.
It builds a linked three-statement model (income statement, balance sheet, cash
flow) and runs scenario analysis on it. The `dcf` skill stops projecting and
becomes a thin discounting layer on top of the model's output — one source of
truth, no drift between two revenue projections.

`model` is the **third desk wrapper** of an off-the-shelf skill, following the
established pattern: `dcf` wraps `financial-analysis:dcf-model`, `comps` wraps
`financial-analysis:comps-analysis`, and `model` wraps
`financial-analysis:3-statement-model`. The off-the-shelf 3-statement-model
skill already provides linked IS/BS/CF construction, cross-statement integrity
checks, a Base/Upside/Downside scenario toggle, and circular-reference handling
(interest → net income → cash → debt) — machinery the desk would otherwise have
to build and maintain itself.

## Goals

1. A new `model` skill (`.claude/skills/model.md`), one file with two modes via
   a `phase` flag — `phase: build` and `phase: scenarios`.
2. **Phase 1 (build)** — construct a linked, formula-driven, 5-year three-
   statement model from the desk's audited data, on the Base case.
3. **Phase 2 (scenarios)** — quantify the top 3-5 discrete catalyst events
   surfaced by `risk-upside` and `macro`, roll them into Bull/Bear envelopes,
   and produce a scenario comparison.
4. Restructure `dcf` to consume the model's projection rather than projecting
   on its own.
5. Wire `model` cleanly into the `/deep-dive` pipeline and every downstream
   consumer, so data flows correctly and the subagent has every reference it
   needs.

## Non-Goals

- `/update`, `/earnings`, and `/morning` integration — the model would benefit
  these workflows, but their integration is deliberately left as a follow-on so
  this remains a single, focused implementation plan.
- A probability-weighted scenario price target feeding back into
  `md-synthesis` — Phase 2 runs after synthesis by design; a synthesis↔scenario
  loop is a deliberate non-goal and may be revisited later.
- Restyling or re-charting any deliverable.
- Changes to the off-the-shelf `financial-analysis:3-statement-model` skill
  itself — it is wrapped, not modified.

## Decisions resolved during brainstorming

- **Model vs DCF** — the model is the single projection engine. The segment
  revenue build and FCF projection move *out of* `dcf` and *into* `model`;
  `dcf` discounts the model's FCF. One source of truth.
- **Scenario type** — both. Discrete catalyst events are modeled individually,
  then rolled up into Bull/Base/Bear envelopes.
- **Model depth** — 5 annual periods; one ticker-prefixed, formula-driven
  `<TICKER> model.xlsx`.
- **Phase split** — Phase 1 builds the full scaffold including Base/Bull/Bear
  driver columns and the Scenario Summary sheet, seeding Bull/Bear equal to
  Base so the model ties immediately. Phase 2 only overwrites Bull/Bear input
  cells — no structural edit.
- **Phase 2 dispatch** — same skill, mode flag (matching the `dcf` skill's
  existing deep-dive / earnings mode pattern).
- **Phase 1 placement** — after the 5 research pods, before `dcf`. This lets
  the segment growth paths ground in `industry-moat` as well as `fundamentals`;
  `dcf` is the only hard consumer of the projection and already runs after the
  pods.
- **Skill name** — `model`.
- **Approach** — thin wrapper; the off-the-shelf skill builds the workbook from
  scratch in standalone-`.xlsx` mode. No binary template file in git.

## Pipeline placement

Revised `/deep-dive` pipeline (new steps in **bold**):

| # | Step | Notes |
|---|---|---|
| 1 | Validate ticker | unchanged |
| 2 | `accountant` | unchanged |
| 3 | Checkpoint A — reconciliation review | unchanged |
| 4 | Checkpoint B — peer list | unchanged |
| 5 | `fundamentals` | unchanged |
| 6 | 5 research pods in parallel | unchanged |
| **7** | **`model` — phase: build** | new; sequential, after all 5 pods complete |
| 8 | `dcf` | **restructured** — discounts the model's FCF; no longer self-projects |
| 9 | `md-synthesis` | reads `model/section.md` |
| **10** | **`model` — phase: scenarios** | new; sequential, after synthesis, before Checkpoint C |
| 11 | Checkpoint C — deliverables | unchanged |
| 12 | Production (`memo-builder`, `deck-builder`) | now also surface model + scenarios |
| 13 | `synthesize-html` | now surfaces model + scenarios |
| 14 | Report paths | unchanged |

Both new steps are sequential by necessity — Phase 1 needs all pods complete,
Phase 2 needs the synthesis complete — so there is no parallelism to reclaim.
Deep-dive wall-clock rises from ~8 min to roughly ~10-11 min.

## Phase 1 — model build

**Mode:** `phase: build`. Runs as step 7.

**Reads:**

- `fundamentals/financials.json` — canonical base: annual + quarterly
  statements, `ttm`, `live_quote`, `latest_quarter`, `ratios`, and the audited
  `segments` block.
- `accountant/reconciliation.json` — reconciled statements + audited
  reportable-segment revenue.
- `industry/section.md` — moat verdict, Porter's five forces, peer-share
  dynamics, secular drivers — grounds the per-segment growth paths.
- Checkpoint-A reconciliation overrides — passed by the orchestrator.

**Workflow:**

1. Load fundamentals' canonical TTM base. Never re-pull from FMP; never use
   FMP pre-calculated ratios, multiples, margins, or TTM (desk rule). If
   fundamentals did not produce `ttm.*` / `latest_quarter.*`, stop and flag.
2. **Segment-driven revenue build** — the logic that moves out of `dcf`. Per
   audited reportable segment, assign a 5-year fractional growth path and a
   one-to-two-sentence justification grounded in `industry/section.md` and
   `fundamentals`. Sum bottom-up to a total revenue path; derive the implied
   blended growth (revenue-weighted). Reconcile segment bases to the TTM total
   via the most recent fiscal year's segment mix. Single-segment fallback when
   the `segments` block is absent or `basis` is `single` / `unavailable`.
3. Assign the rest of the driver set — gross/EBIT margin path, opex
   percentages, tax rate, D&A / capex / ΔWC percentages, working-capital days
   (DSO / DIO / DPO), and debt-schedule assumptions.
4. Dispatch `financial-analysis:3-statement-model` via the Skill tool in
   standalone-`.xlsx` mode to build the linked workbook on the **Base** case,
   with Bull/Bear driver columns seeded equal to Base so the model ties out
   immediately.
5. Run the desk-mandated **reference-integrity check** plus tie-out checks:
   balance sheet balances every period, cash flow ending cash ties to balance
   sheet cash, net income links, retained-earnings roll-forward. Same
   discipline `dcf` enforces.
6. Write outputs.

**The workbook — `<TICKER> model.xlsx`** (ticker-prefixed, formula-driven), six
content sheets plus the off-the-shelf skill's Checks tab:

| # | Sheet | Contents |
|---|---|---|
| 1 | **Drivers** | All *inputs*: per-segment base revenue and per-segment 5-year growth paths, margin path, opex %s, working-capital days, capex %, tax rate, debt-schedule assumptions — each with Base / Bull / Bear columns — plus the scenario-selector toggle cell. |
| 2 | **Revenue Build** | All *formulas*: projects each segment off the Drivers active-scenario column, sums to total revenue, derives the implied blended growth. |
| 3 | **Income Statement** | 5-year annual, formula-driven; the revenue line **references the Revenue Build total** — it does not re-compound a separate growth path. |
| 4 | **Balance Sheet** | 5-year, linked, balances every period. |
| 5 | **Cash Flow** | 5-year, linked, ties to balance-sheet cash; includes an **unlevered-FCF block** (NOPAT + D&A − capex − ΔWC) — the line `dcf` consumes. |
| 6 | **Scenario Summary** | Base / Bull / Bear headline outputs side by side, plus one row per discrete catalyst event. Phase 1 leaves Bull/Bear equal to Base; Phase 2 fills them. |

House rule: **inputs live on Drivers, every derived cell is a formula.** The
segment growth paths are inputs (Drivers); the Revenue Build sheet is pure
projection math; the Income Statement top line links to it. Only genuine
inputs may be hardcoded — per-segment base revenue and growth paths, the
margin / opex / WC / capex / tax / debt assumptions, the TTM base-year
financials, share count, net cash. Everything else is an Excel formula. If the
off-the-shelf skill emits static values, build the workbook with `openpyxl`
instead.

The **reference-integrity check is mandatory**: after writing the workbook,
load it with `openpyxl`, walk each cross-sheet formula, and confirm the target
cell matches its row's column-A label — catching the classic blank-spacer-row
shift that silently mis-points references. Fix any mismatch and re-verify.

**Writes:**

- `model/<TICKER> model.xlsx`
- `model/section.md` — narrative; leads with the segment revenue build (a table
  of each segment's base revenue, 5-year growth path, and justification, then
  the derived blended growth), then the driver set and the base-case 5-year
  IS/BS/CF summary.
- `model/projection.json` — the machine contract `dcf` reads: the base-case
  5-year path for revenue, EBIT, NOPAT, D&A, capex, ΔWC, and unlevered FCF,
  plus the segment build and the full driver set.

## Phase 2 — scenario analysis

**Mode:** `phase: scenarios`. Runs as step 10.

**Reads:**

- `model/<TICKER> model.xlsx` and `model/projection.json` — its own Phase 1
  output.
- `synthesis/_synthesis.md` — the MD synthesis: rating, price target, key
  thesis points.
- `risk/section.md` — `risk-upside`'s bull/bear narratives and ranked swing
  factors.
- `macro/section.md` — the catalyst calendar; dated catalysts are candidate
  events.

**Workflow:**

1. Read the synthesis, risk, and macro sections.
2. **Identify the top 3-5 discrete catalyst events** that could move the
   thesis — drawn *from* `risk-upside`'s swing factors and `macro`'s catalysts,
   **not invented fresh**. This is the no-duplication rule: `risk-upside` owns
   the qualitative case, `model` Phase 2 *quantifies* it.
3. **Translate each event into a driver adjustment** — e.g. a guide cut →
   revenue growth −400 bps in year 1; a margin shock → EBIT margin −200 bps; a
   rate shock → cost of debt +150 bps.
4. **Roll events into the Bull / Bear envelopes** — overwrite only the
   Bull/Bear *input* cells in `<TICKER> model.xlsx` (Phase 1 already wired
   every formula). Bull aggregates favorable events; Bear aggregates adverse
   events.
5. Populate the **Scenario Summary** sheet — Base / Bull / Bear headline
   outputs plus one row per discrete event (driver moved → delta to FCF and
   implied value).
6. Re-run the reference-integrity and tie-out checks; verify the off-the-shelf
   scenario-hierarchy holds (Bull > Base > Bear for net income, EBITDA, FCF)
   across all three columns.
7. Write outputs.

**Writes:**

- `model/<TICKER> model.xlsx` — updated, with Bull/Bear columns and the
  Scenario Summary sheet filled.
- `model/scenarios.md` — narrative: the 3-5 events, their driver translations,
  the per-scenario P&L / FCF / implied-value outcomes, and an explicit mapping
  back to `risk-upside`'s bull/bear cases.

Phase 2 runs after `md-synthesis`, so it does not rewrite the synthesis or
change the headline price target. The scenario analysis is a risk-
quantification exhibit that enriches the production deliverables.

## DCF restructure

The Q1 decision makes the model the single projection engine, so `dcf` is
restructured:

- **Removed** — the segment revenue build, growth-path assignment, and the FCF
  projection. `<TICKER> dcf.xlsx` no longer has a "Revenue Build" sheet.
- **Added** — a step that reads `model/projection.json` for the base-case
  unlevered-FCF path, exactly as `dcf` already reads `comps/peer-multiples.json`.
  There is no live cross-workbook Excel link; the FCF path lands in a
  "Projection (from model)" sheet as clearly labelled imported inputs.
- **Kept** — the WACC build (β, Rf, ERP, cost of debt, D/E weights), terminal
  value (GGM + exit multiple + blend), discounting, the EV→equity bridge, the
  sensitivity grids, and the football-field chart.
- `dcf/section.md` drops the segment-build section and gains a note that the
  FCF path is sourced from the model.

The Revenue Build sheet exists in exactly one workbook — `<TICKER> model.xlsx` —
never in both. If it lived in both, the two revenue projections could diverge,
which is the drift the decision exists to prevent.

## Tools refactor

`project_segment_revenue` and the pure-projection helpers move from
`tools/dcf_engine.py` into a new `tools/model_engine.py`. The WACC, terminal-
value, and sensitivity helpers stay in `tools/dcf_engine.py`. This is a
targeted refactor justified by the work — the projection logic now belongs to
`model`. `tools/model_engine.py` also owns the Revenue Build sheet construction
and the `projection.json` schema.

## Downstream updates

Skills, commands, and files that must be updated to reference `model`:

| File | Change |
|---|---|
| `.claude/skills/model.md` | new skill file |
| `.claude/skills/dcf.md` | restructured per "DCF restructure" above |
| `.claude/skills/md-synthesis.md` | canonical section order adds `model` before `dcf`: accountant, fundamentals, industry, comps, macro, risk, technicals, **model**, dcf |
| `.claude/skills/memo-builder.md` | reads `model/section.md` + `model/scenarios.md`; adds a model / scenario section |
| `.claude/skills/deck-builder.md` | reads `model/section.md` + `model/scenarios.md`; adds model / scenario slides |
| `.claude/skills/synthesize-html.md` | surfaces model + scenarios; `<TICKER> model.xlsx` becomes a companion download alongside the dcf and comps workbooks |
| `.claude/commands/deep-dive.md` | adds step 7 (model build) and step 10 (model scenarios); renumbers |
| `CLAUDE.md` | skill table 13 → 14 skills; add the `model` row and update the concurrency / pipeline notes |
| `tools/dcf_engine.py`, `tools/model_engine.py` | the tools refactor above |

## Data-flow contract

```
accountant ──► reconciliation.json ─┐
fundamentals ─► financials.json ────┼─► model (build) ─► model.xlsx
industry ────► section.md ──────────┘                   section.md
                                                         projection.json ─► dcf ─► section.md, dcf.xlsx
                                                                                     │
md-synthesis ◄── model/section.md + dcf + all pods ◄─────────────────────────────────┘
      │
      ▼
synthesis/_synthesis.md ─┐
risk/section.md ─────────┼─► model (scenarios) ─► model.xlsx (updated)
macro/section.md ────────┘                        scenarios.md ─► memo / deck / html
```

`model` Phase 1 reads `fundamentals/financials.json`,
`accountant/reconciliation.json`, `industry/section.md`, and the Checkpoint-A
overrides; it writes `model/<TICKER> model.xlsx`, `model/section.md`, and
`model/projection.json`. `model` Phase 2 reads its own Phase 1 output plus
`synthesis/_synthesis.md`, `risk/section.md`, and `macro/section.md`; it
updates the workbook and writes `model/scenarios.md`.

## Skill file completeness

`model.md` must be self-contained so the dispatched subagent has every
reference it needs: both modes documented; exact input and output file paths;
the segment-revenue-build logic; the driver-set definition; the pinned six-
sheet workbook spec; the formula-driven and reference-integrity mandates; the
unlevered-FCF block definition; the `projection.json` schema; Phase 2's event-
identification and no-duplication-with-`risk-upside` rules; and prompt-injection
hardening (wrap any externally derived content in `<external-content>` markers,
treat it as data).

## Testing

- New unit tests for `tools/model_engine.py` — segment projection, driver
  application, and the `projection.json` schema.
- New tests for the reference-integrity check.
- A regression test that `dcf` correctly consumes `projection.json`.
- All existing tests (197 at time of writing) stay green.

## Open risks

- The off-the-shelf `financial-analysis:3-statement-model` skill leans toward
  template completion; the wrapper must explicitly steer it into standalone-
  build mode and own the desk-specific Revenue Build sheet. If the off-the-shelf
  skill emits static values, the wrapper falls back to building the workbook
  directly with `openpyxl`.
- Circular-reference handling (interest → net income → cash → debt) relies on
  the off-the-shelf skill's iterative-calculation setup; the integrity check
  must confirm the workbook recalculates cleanly.
