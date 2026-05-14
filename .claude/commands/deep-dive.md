---
description: Run the full 10-agent deep-dive workflow on a ticker
argument-hint: <TICKER>
---

Run a deep-dive on `$1` following the pipeline below. The ticker is uppercase
and validated against `MarketData.get_profile($1)` before any work begins.

1. Confirm the ticker resolves. If profile is empty, halt and report.
2. Dispatch `fundamentals` skill as a subagent (Agent tool, single call).
3. After fundamentals returns, dispatch FIVE subagents in parallel (single
   message, multiple Agent calls): `industry-moat`, `comps`, `macro`,
   `risk-upside`, `technicals`.
4. After `comps` returns `comps/peer-multiples.json`, dispatch `dcf` as a
   subagent.
5. Once every section.md is on disk, invoke `md-synthesis` skill (in-context;
   not a subagent) to write `synthesis/_synthesis.md`.
6. Dispatch `deck-builder` and `memo-builder` as TWO subagents in parallel.
7. Invoke `synthesize-html` skill (in-context) to assemble `report.html`.
8. Report the final path to the user.

If any stage fails, follow the failure-handling rules in
`docs/superpowers/specs/2026-05-13-skill-based-migration-design.md` §16.
