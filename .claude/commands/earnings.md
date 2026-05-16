---
description: Run an earnings-update workflow on a ticker (delta vs prior quarter) with a single pause checkpoint after the accountant
argument-hint: <TICKER>
---

Run an earnings-update on `$1`. Unlike `/deep-dive`, this skips comps + the 5-pod batch, so there's only ONE pause point (after the accountant) — no peer-list ask.

1. **Validate ticker.** Confirm `MarketData.get_profile($1)` returns non-empty. If empty, halt and report.

2. **Dispatch `accountant` skill as a subagent with `mode="earnings-update"`.** The accountant skill body has explicit short-circuits for this mode:
   - Step 2: pull most recent 8-K only.
   - Step 3: XBRL pull narrows to the most recent quarter (skip annual).
   - Step 4: FMP pulls narrow to the latest quarterly period only.
   - Step 5: reconciliation runs on the latest Q only.
   - Step 6: download latest 8-K + earnings deck only (skip 10-K, 10-Q, DEF 14A).
   - Step 7: full earnings-presentation hunt (unchanged — this is the priority artifact).
   - Step 8: skip 10-K section extracts entirely.
   - Step 9: reduced red-flag set — RF-01 (revenue rec), RF-02 (OCF/NI), RF-06 (segment reorg), RF-14 (inventory write-downs).
   - Returns `CLEAN` / `PAUSE_FOR_REVIEW` / `FMP_ONLY_FALLBACK` per the standard signal contract.

   Save ~30-50% of the accountant's wall-clock + tokens vs the deep-dive variant.

3. **PAUSE CHECKPOINT — present accountant findings.** Same logic as `/deep-dive` Checkpoint A:
   - `CLEAN`: brief summary, ask to proceed.
   - `PAUSE_FOR_REVIEW`: list the divergent line items, ask per-concept which value to use.
   - `FMP_ONLY_FALLBACK`: note SEC was skipped, ask whether to continue on FMP alone.

   Wait for explicit user confirmation.

4. **Dispatch `fundamentals` skill as a subagent.** Pass `mode=earnings-update` so it focuses on the latest reported quarter delta vs. prior. Pass any reconciliation overrides from the pause checkpoint. Fundamentals reads accountant's downloaded earnings deck for KPI grounding.

5. **Dispatch `dcf` and `risk-upside` in parallel** (two Agent calls in one message). DCF uses the default 12× EV/EBITDA fallback since comps is absent in this workflow. Risk-upside references any red flags the accountant surfaced.

6. **PAUSE CHECKPOINT — which deliverables?** Synthesis (a brief one via md-synthesis) is implicit in the earnings flow via the memo prompt, but the explicit deliverables are: memo, html. Ask:

   > *"Earnings update synthesized. Which deliverables would you like?*
   > *— memo (.docx, ~30K tokens — wraps `equity-research:earnings-analysis`)*
   > *— html (report.html, cheap)*
   >
   > *Reply with any combination, e.g. 'both', 'just html', 'just memo'."*

   Wait for explicit confirmation.

7. **If memo selected:** dispatch `memo-builder` with `variant=earnings` so it wraps `equity-research:earnings-analysis`. The memo carries an "Accounting & Filings Audit" mini-section even in earnings mode.

8. **If html selected:** invoke `synthesize-html` skill in-context to assemble `<TICKER>/report.html`.

Output: only the artifacts produced per the deliverable selection. `~/Desktop/Agentic_Equity_Reports/$1/{reports/memo.docx, report.html}` depending on Checkpoint.
