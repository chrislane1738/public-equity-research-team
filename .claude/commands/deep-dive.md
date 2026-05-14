---
description: Run the full 10-agent deep-dive workflow on a ticker
argument-hint: <TICKER>
---

Run a deep-dive on `$1` following the pipeline below. The ticker is uppercase
and validated against `MarketData.get_profile($1)` before any work begins.

> **Note:** This pipeline runs the accountant first as the ground-truth step;
> all downstream agents anchor on its reconciled SEC data and red-flag findings.

1. Confirm the ticker resolves via `MarketData.get_profile($1)`. If profile is
   empty, halt and report.
2. **Dispatch `accountant` skill as a subagent (Agent tool, single call).** This
   pulls SEC filings, reconciles them against FMP, audits for red flags, and
   downloads the latest earnings presentation. **All subsequent agents depend on
   its outputs.** Wait for it to complete before proceeding.
3. Dispatch `fundamentals` skill as a subagent. (Now reads
   `accountant/reconciliation.json` and prefers SEC over FMP on divergent line
   items; reads `accountant/filings/earnings_presentation_*.pdf` for KPI
   grounding.)
4. After fundamentals returns, dispatch FIVE subagents in parallel (single
   message, multiple Agent calls): `industry-moat`, `comps`, `macro`,
   `risk-upside`, `technicals`.
5. After `comps` returns `comps/peer-multiples.json`, dispatch `dcf` as a
   subagent.
6. Once every section.md is on disk (including `accountant/section.md`), invoke
   `md-synthesis` skill (in-context; not a subagent). The synthesis now reads
   `accountant/red-flags.md` and surfaces High-severity flags in the executive
   summary.
7. Dispatch `deck-builder` and `memo-builder` as TWO subagents in parallel.
   Both will produce a dedicated "Accounting Audit Summary" section/slide using
   `accountant/section.md` and `accountant/red-flags.md`.
8. Invoke `synthesize-html` skill (in-context) to assemble `report.html`.
9. Report the final path to the user.

If any stage fails, follow the failure-handling rules in
`docs/superpowers/specs/2026-05-13-skill-based-migration-design.md` §16.
