---
description: Refresh a previously-covered ticker — quarterly-update workflow. Refetches only the pods that change between quarters; produces a diff-style synthesis vs the prior run.
argument-hint: <TICKER>
---

Run an `/update` on `$1`. This is a lightweight refresh on a ticker we've previously deep-dove. It re-runs only the pods that change quarter-over-quarter, reuses the prior peer list, and produces a diff-style synthesis vs the prior `_synthesis.md` (rating change, PT delta, what moved).

Use `/update` when:
- You've previously run `/deep-dive` on this ticker (so `~/Desktop/Agentic_Equity_Reports/$1/synthesis/_synthesis.md` exists).
- You want a quarterly refresh rather than a full ground-up rebuild.
- The competitive landscape / risk profile hasn't materially changed.

If `~/Desktop/Agentic_Equity_Reports/$1/synthesis/_synthesis.md` does NOT exist, halt and report: *"No prior synthesis for $1. Run `/deep-dive $1` first; `/update` is for refreshes only."*

## Pipeline

1. **Validate ticker + verify prior synthesis exists.** Confirm `MarketData.get_profile($1)` returns non-empty AND `~/Desktop/Agentic_Equity_Reports/$1/synthesis/_synthesis.md` exists. If either fails, halt and report.

2. **Capture prior baseline.** Read `~/Desktop/Agentic_Equity_Reports/$1/synthesis/_synthesis.md`. Extract the prior **rating** (Buy/Hold/Sell), **price target**, and **synthesis date** (from frontmatter or top heading). Hold these in context for the diff in Step 9.

3. **Dispatch `accountant` skill with `mode="earnings-update"`** (the light variant — see `.claude/skills/accountant.md` Mode parameter section). Pulls latest 8-K + earnings deck, narrow reconciliation, reduced red-flag set. Wait for return signal.

4. **PAUSE CHECKPOINT A — review accountant findings.** Same as `/deep-dive`:
   - `CLEAN`: brief summary + ask to proceed.
   - `PAUSE_FOR_REVIEW`: list divergent items, ask per-concept resolution.
   - `FMP_ONLY_FALLBACK`: note skip, ask whether to continue.

5. **PAUSE CHECKPOINT B — confirm peer list.** Default to the peer list from the prior run by reading `~/Desktop/Agentic_Equity_Reports/$1/comps/peer-multiples.json` (the `peers` field). Present to user: *"Prior peer list: [AMD, NVDA, AVGO, ARM]. Use same? (yes / no / new list: TICK1,TICK2,…)"* Wait for user confirmation or modification.

6. **Refresh the per-quarter-sensitive pods (parallel).** Dispatch in a single message, all as subagents:
   - `fundamentals` — TTM moves every quarter.
   - `comps` — peer multiples drift; pass the confirmed peer list from Checkpoint B.
   - `macro` — rates/FX/calendar refreshes.
   - `technicals` — price action moves daily.

   **Skip by default in `/update`:**
   - `industry-moat` — competitive landscape rarely shifts quarter-to-quarter; reuse prior `industry/section.md`.
   - `risk-upside` — risk factors are stable; reuse prior `risk/section.md`.

   If the user wants those refreshed too, they'll request it explicitly (e.g., *"refresh industry-moat too — there's been a major competitive change"*). Otherwise skip.

7. **Dispatch `dcf` after comps writes `comps/peer-multiples.json`.** DCF reads the refreshed TTM from `fundamentals/financials.json` and the refreshed peer multiples.

8. **Invoke `md-synthesis` skill in-context, with `mode="update"`.** The synthesis reads:
   - The prior `_synthesis.md` (the baseline).
   - The newly refreshed section files (fundamentals, comps, dcf, macro, technicals, accountant).
   - The retained section files (industry, risk — same as prior run unless refreshed).

   In `mode="update"`, the synthesis produces a **diff-style document** (see md-synthesis skill body for the format): new rating vs prior, PT delta with attribution, what moved in each pod, decision-condition changes. Writes to `synthesis/_synthesis.md` (overwriting prior — git history preserves both).

9. **PAUSE CHECKPOINT C — which deliverables?** Same as `/deep-dive`:

   > *"Update synthesis complete. Rating: <prior> → <new>. PT: <prior> → <new>. Which deliverables?*
   > *— update memo (.docx — shorter than full memo, focuses on diff)*
   > *— deck (.pptx — full rebuild)*
   > *— html (report.html, cheap)*
   >
   > *Reply: 'all', 'just html', 'memo and html', etc."*

10. **Dispatch selected production agents.** memo-builder with `variant=update` (writes a shorter diff memo); deck-builder with the full slide deck (no diff variant — easier to consume); synthesize-html assembles `report.html`.

11. Report final paths.

## Notes

- **Token cost vs `/deep-dive`:** roughly 40-50% of a full deep-dive when industry-moat + risk-upside are skipped. The accountant earnings-update mode and the synthesis diff mode contribute additional savings.
- **Pre-existing artifacts are preserved.** The refresh overwrites only the pods that re-ran. Prior section.md files for industry/risk remain in place; the diff synthesis references them by name.
- **For a name where the competitive landscape HAS shifted** (M&A, new entrant, tech disruption), prefer `/deep-dive` over `/update` — the full rebuild ensures industry/risk reflect the new reality.
