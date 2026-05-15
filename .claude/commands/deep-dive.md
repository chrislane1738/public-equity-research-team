---
description: Run the full deep-dive workflow on a ticker, with two mandatory human-in-the-loop pause checkpoints before research dispatches
argument-hint: <TICKER>
---

Run a deep-dive on `$1`. This pipeline has **two mandatory pause points** where the orchestrator (you) stops and prompts the user before continuing. The pauses exist so we never dispatch the 5 research pods on bad data or bad comps.

> **Note:** the accountant runs first as the ground-truth step; the user reviews its findings + provides a peer list; only then do the research agents fire.

## Pipeline

1. **Validate ticker.** Confirm `MarketData.get_profile($1)` returns non-empty. If empty, halt and report.

2. **Dispatch `accountant` skill as a subagent (Agent tool, single call).** This pulls SEC filings (most recent FY 10-K + most recent 10-Q), reconciles them line-by-line against FMP, audits for red flags, and downloads the latest IR earnings presentation. Wait for the accountant to return one of three signals: `CLEAN`, `PAUSE_FOR_REVIEW`, or `FMP_ONLY_FALLBACK`.

3. **PAUSE CHECKPOINT A — present accountant findings to the user.** Read `accountant/section.md`, `accountant/reconciliation.json`, and the top items in `accountant/red-flags.md`. Present to the user:

   - **If `CLEAN`:** a one-paragraph summary ("Accountant pass clean — N line items reconciled, K Medium/High-severity red flags. Proceed?").
   - **If `PAUSE_FOR_REVIEW`:** the divergent items in a structured list with SEC value, FMP value, and delta %. Ask the user **per concept** which value to use (SEC, FMP, or manual override). Record the resolutions — downstream agents (fundamentals, comps, dcf) must respect them.
   - **If `FMP_ONLY_FALLBACK`:** note that SEC reconciliation was skipped (foreign listing or no XBRL). Ask the user whether to proceed on FMP data alone or abort.

   **Wait for the user's explicit confirmation before continuing.** Do not auto-proceed.

4. **PAUSE CHECKPOINT B — request the peer list for comps.** Ask the user: *"Provide the peer ticker list for comps (3–12 tickers, comma-separated). Example: AMD, NVDA, AVGO, ARM."* The peer list is **mandatory** — do not fall back to FMP-curated peers or LLM-picked peers. Wait for the user's response.

5. **Dispatch `fundamentals` skill as a subagent.** Pass any reconciliation overrides from Checkpoint A. Fundamentals reads `accountant/reconciliation.json`, `accountant/filings/earnings_presentation_*.pdf` for KPI grounding, and `accountant/extracted_sections/mda.txt` (canonical MD&A). Wait for it to return.

6. **Dispatch the 5 research pods in parallel** (single message, multiple Agent tool calls): `industry-moat`, `comps`, `macro`, `risk-upside`, `technicals`. Pass the user-supplied peer list to `comps` explicitly. Pass any Checkpoint-A resolutions to `risk-upside` so red flags are referenced in its bull/bear case.

7. **Dispatch `dcf`** as a subagent once `comps/peer-multiples.json` exists on disk. DCF reads canonical TTM + live_quote from `fundamentals/financials.json`.

8. **Invoke `md-synthesis` skill in-context (not a subagent).** Read all section.md files (canonical order: accountant, fundamentals, industry, dcf, comps, macro, risk, technicals) plus `_synthesis.md` inputs. Write `synthesis/_synthesis.md`. The synthesis surfaces any High-severity red flags in the executive summary.

9. **PAUSE CHECKPOINT C — which deliverables?** Synthesis is complete. Before dispatching the production agents, ask the user which deliverables to produce:

   > *"Synthesis complete (rating: <X>, PT: <Y>). Which deliverables would you like?*
   > *— memo (.docx, ~50K tokens)*
   > *— deck (.pptx, ~70K tokens)*
   > *— html (report.html, in-context — cheap)*
   >
   > *Reply with any combination, e.g. 'all', 'just html', 'memo and html', 'deck only', 'none' (synthesis already on disk)."*

   Parse the user's response into a set of {memo, deck, html}. Default if response is ambiguous: ask for clarification, do not guess. Wait for explicit confirmation.

10. **Dispatch the selected production agents.** Based on Checkpoint C:
    - If memo + deck both selected: dispatch `memo-builder` and `deck-builder` as two parallel subagents (one Agent message).
    - If only memo: single `memo-builder` dispatch.
    - If only deck: single `deck-builder` dispatch.
    - If neither memo nor deck: skip this step entirely.

11. **If html was selected:** invoke `synthesize-html` skill in-context. Assemble `<TICKER>/report.html`. The HTML auto-includes whichever companion files (memo.docx, pitch.pptx) actually exist — missing companions are silently skipped.

12. Report the final paths to the user (only the artifacts you actually produced; do not list synthesis if it was already on disk pre-checkpoint).

## Failure handling

- Pod fails (one of the 5 parallel): note in synthesis, continue with the rest.
- Accountant returns `FMP_ONLY_FALLBACK` and user declines to proceed: halt cleanly with no artifacts beyond accountant outputs.
- User does not respond to Checkpoint A or B within the session: stop; do not auto-proceed.
- Reference `docs/superpowers/specs/2026-05-13-skill-based-migration-design.md` §16 for stage-level failure rules.
