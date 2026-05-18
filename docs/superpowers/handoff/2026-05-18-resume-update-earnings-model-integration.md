# Resume — `model` skill integration into `/update` and `/earnings`

**Date:** 2026-05-18
**Repo:** `/Users/chrislane/Desktop/Claude_Code/public-equity-research-team` — branch `main`, all work pushed to `github.com/chrislane1738/public-equity-research-team` (public). Latest commit `29bc3c3`. Working tree clean.
**Status:** Not started. The 3-statement `model` agent shipped and is wired into `/deep-dive` only. Integrating it into `/update` and `/earnings` was a deliberate spec non-goal — this handoff is the follow-on.

## How to resume

Open a fresh Claude Code session in the repo. First message:

> Pick up the `/update` and `/earnings` model-integration work — see `docs/superpowers/handoff/2026-05-18-resume-update-earnings-model-integration.md`. Start with the `superpowers:brainstorming` skill to resolve the open questions, then spec → plan → implement.

This is a creative change (adding functionality to two workflows), so it should go through `brainstorming` → `writing-plans` → `subagent-driven-development`, the same path the `model` agent itself took. It is small enough that the brainstorm can be light.

## The idea

The `model` skill (the desk's 3-statement projection engine) currently runs only in `/deep-dive` — phase `build` after the 5 research pods, phase `scenarios` after `md-synthesis`. The `/update` and `/earnings` workflows also dispatch `dcf`, but they never run `model`. The `dcf` skill's **inline-projection fallback** keeps them working: when `model/projection.json` is absent, `dcf` builds the projection itself in-memory via `tools.model_engine` (`project_segment_revenue` + `build_projection`).

That fallback is functional but it means `/update` and `/earnings` produce **no `model/` artifacts** — no `<TICKER> model.xlsx`, no `model/section.md`, no scenario analysis. For `/update` especially (a quarterly refresh of a covered name), not refreshing the three-statement model is a real gap: the model *should* roll forward each quarter.

The task: decide whether and how `model` should run in each workflow, then wire it in.

## Why it was deferred

The model-agent spec (`docs/superpowers/specs/2026-05-17-3-statement-model-agent-design.md`, §Non-Goals) explicitly scoped integration to `/deep-dive` and left `/update` + `/earnings` as a follow-on, to keep that spec a single focused implementation plan. The `dcf` inline-projection fallback (added in plan Task 11) was the bridge that kept the other two workflows from breaking.

## How `/update` works today (`.claude/commands/update.md`)

Quarterly refresh of a previously-covered ticker (`~4-5 min`, ~40-50% of a deep-dive). Pipeline:
1. Validate ticker + verify a prior `_synthesis.md` exists.
2. Capture prior baseline (rating, PT, date).
3. `accountant` in `mode="earnings-update"`.
4. Checkpoint A (accountant review).
5. Checkpoint B (confirm/modify peer list — defaults to prior).
6. Refresh quarter-sensitive pods in parallel: `fundamentals`, `comps`, `macro`, `technicals`. **Skips** `industry-moat` and `risk-upside` (reuses prior `industry/section.md`, `risk/section.md`).
7. `dcf` after comps. **Today the DCF takes the inline-projection fallback** (no `model/projection.json`).
8. `md-synthesis` in `mode="update"` — diff-style synthesis with a "What moved (by pod)" block.
9. Checkpoint C (deliverables).
10. Production + html.

## How `/earnings` works today (`.claude/commands/earnings.md`)

Lightweight earnings-update (`~4 min`, minimal outputs). Pipeline:
1. Validate ticker.
2. `accountant` in `mode="earnings-update"` (8-K + earnings deck only).
3. Checkpoint (accountant review).
4. `fundamentals` in `mode=earnings-update` (latest-quarter delta).
5. `dcf` + `risk-upside` **in parallel**. DCF takes the inline-projection fallback; also uses the 12× EV/EBITDA exit fallback since `comps` is absent.
6. Checkpoint (deliverables — memo / html).
7. `memo-builder` `variant=earnings` / `synthesize-html`.

## Open questions to brainstorm (resolve these first)

1. **`/update` — run the full `model` (both phases) or `build` only?** A quarterly refresh clearly wants the 3-statement model rebuilt (phase `build`). Does it also want refreshed Bull/Bear scenario analysis (phase `scenarios`)? Phase 2 adds a sequential subagent and reads `risk/section.md` — which `/update` *reuses from the prior run* rather than refreshing, so the scenarios would be re-quantified against stale risk swing factors. Lean: `build` only for `/update`, scenarios optional.

2. **`/earnings` — run `model` at all?** `/earnings` is deliberately lean (~4 min, minimal artifacts). A full six-sheet model build may be disproportionate. Option A: leave `/earnings` on the `dcf` inline fallback (no `model/` artifacts) — status quo. Option B: run phase `build` only. Recommendation to pressure-test: `/earnings` probably should NOT run `model` — the inline fallback is the right weight for that workflow. If so, the only real integration target is `/update`.

3. **Grounding gap.** Phase `build` step 2 grounds per-segment growth paths in `industry/section.md`. `/update` *reuses* the prior industry section (doesn't re-run `industry-moat`), and `/earnings` never produces one. Confirm the model skill degrades gracefully: ground in the prior/`fundamentals` data, or fall to the single-segment build. Industry/moat changes slowly, so reusing the prior section in `/update` is likely fine — but state it.

4. **Pipeline placement in `/update`.** `model` (build) would slot after step 6 (the parallel pod refresh — needs `fundamentals` done) and before step 7 (`dcf`). The `dcf` step then takes the **standard path** (reads `model/projection.json`) instead of the inline fallback. Renumber accordingly.

5. **`md-synthesis` update-mode diff block.** `update.md` step 8 / `md-synthesis.md` update mode has a "What moved (by pod)" list. If `model` runs in `/update`, add a `model` line to that block.

6. **The `dcf` inline fallback — keep or retire?** If `model` is wired into `/update`, the inline-projection fallback is no longer hit by `/update` (only by `/earnings`, if `/earnings` keeps skipping `model`). Keep the fallback as the `/earnings` path + a safety net; do not remove it.

7. **Cost / wall-clock.** `model` build adds one sequential subagent. `/update` ~4-5 min → ~6-7 min. Acceptable for a quarterly refresh? Confirm with the user.

## Recommended starting position (opinionated — pressure-test, don't assume)

- **`/update`:** wire in `model` phase `build` as a new step between the pod refresh and `dcf`; `dcf` then takes the standard `projection.json` path. Add a `model` line to the update-mode synthesis diff. Phase `scenarios` left out of `/update` (stale `risk` input) unless the user wants it.
- **`/earnings`:** leave as-is on the `dcf` inline fallback — adding a full model build is disproportionate to a 4-minute lean workflow. Worth confirming with the user, but this is the likely answer, which would make `/update` the only real integration.
- Update `earnings.md` step 5 and `update.md` step 7 prose either way — both currently describe the DCF without mentioning the inline-projection fallback / standard path.

## Key files & contracts

- `.claude/skills/model.md` — the `model` skill: phase `build` (workflow steps 1-7), phase `scenarios` (steps 1-7). Reads `fundamentals/financials.json`, `accountant/reconciliation.json`, `industry/section.md`. Writes `model/<TICKER> model.xlsx`, `model/projection.json`, `model/section.md` (+ `model/scenarios.md` in phase 2).
- `.claude/skills/dcf.md` — workflow step 1 has the standard path (load `model/projection.json`) and the fallback path (build inline via `tools.model_engine` when absent). This is the seam the integration flips for `/update`.
- `.claude/commands/update.md`, `.claude/commands/earnings.md` — the two pipelines to edit.
- `.claude/skills/md-synthesis.md` — `mode="update"` diff block ("What moved (by pod)").
- `tools/model_engine.py` — `project_revenue`, `project_segment_revenue`, `project_fcf_path`, `project_fcf`, `build_projection`. `compute_beta` lives in `tools/dcf_engine.py`.
- `model/projection.json` contract — `ticker`, `horizon`, `base_year`, `revenue`, `implied_growth`, `ebit`, `nopat`, `da`, `capex`, `wc_change`, `unlevered_fcf`, `segments`, `drivers`, `_source`.
- The model-agent spec & plan: `docs/superpowers/specs/2026-05-17-3-statement-model-agent-design.md`, `docs/superpowers/plans/2026-05-17-3-statement-model-agent.md`.

## What shipped in the model-agent iteration (context — all on `main`, pushed)

- New `model` skill (`.claude/skills/model.md`) — two phases; the desk's single forward-projection engine; wraps `financial-analysis:3-statement-model` but builds the workbook headless with `openpyxl`.
- New `tools/model_engine.py` — projection math + `build_projection` (the `projection.json` assembler), moved out of `dcf_engine.py`.
- `dcf` restructured — discounts the model's FCF (standard path) or builds the projection inline (fallback for `/earnings`, `/update`); gained a 3-year weekly SPY **regression beta** (`dcf_engine.compute_beta`) with the analyst choosing the WACC beta vs FMP's 5-year.
- `/deep-dive` pipeline: `model` build at step 7, `model` scenarios at step 10.
- Wired into `md-synthesis` (canonical section order), `memo-builder`, `deck-builder`, `html_writer` (model section + `3-statement-model` companion download), and the masthead now parses synthesis frontmatter.
- House style: `report.html` strips em-dashes.
- 211 tests pass. README / CLAUDE.md / COMMANDS.md updated.
- ADBE was the live flow-test ticker — model phases 1+2, the restructured DCF (β 1.112, WACC 10.16%, blended PT $426; synthesis rating Buy, PT $350), and `report.html` were all regenerated. ADBE artifacts at `~/Desktop/Agentic_Equity_Reports/ADBE/`.
