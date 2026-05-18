# Workflow commands

All workflows accept arguments inline (`/deep-dive NVDA`) and also work as
natural-language prompts ("deep-dive on NVDA").

## `/deep-dive <TICKER>` — Full Deep-Dive (~10-11 min)

Stages: accountant (filings audit) → fundamentals → 5 research pods in parallel
→ model (3-statement build) → DCF → synthesis → model (scenario analysis) →
deck + memo in parallel → HTML rollup.

Outputs: every section.md + every artifact, plus `report.html`.

Example: `/deep-dive NVDA`

## `/earnings <TICKER>` — Earnings Update (~4 min)

Stages: accountant (lightweight — downloads latest 8-K + earnings deck) →
fundamentals (delta) → DCF + risk in parallel → memo.

Outputs: minimal — `fundamentals/section.md`, `dcf/section.md`,
`risk/section.md`, `reports/memo.docx`, `report.html`.

Example: `/earnings ANET`

## `/update <TICKER>` — Quarterly Refresh (~4-5 min)

For a ticker we've previously deep-dove. Refreshes only the quarter-sensitive
pods (fundamentals, comps, macro, technicals, DCF) + the accountant in
earnings-update mode. Reuses prior industry-moat + risk-upside sections
(saves ~30-40% vs a full deep-dive). Synthesis runs in diff mode — produces a
"Δ vs prior synthesis" block showing rating change, PT delta, and what moved
by pod.

Defaults to the prior peer list (with user confirmation). Same three pause
checkpoints as `/deep-dive` (accountant findings, peer list, deliverable
selection).

If no prior `_synthesis.md` exists, the workflow halts and asks the user to
run `/deep-dive` first.

Example: `/update MU`

## `/morning <TICKER>` — Morning Note (~1 min)

Stages: fundamentals delta → md-synthesis writes the note directly.

Output: `<TICKER>/morning-note.md` (or chat-only if no tree exists).

Example: `/morning AAPL`

## `/thesis <TICKER> "<question>"` — Thesis Check (variable)

Routes the question to 2-3 relevant skills and writes a focused memo.

Example: `/thesis NVDA "is the moat narrowing as AMD MI400 ramps?"`

## `/sector <T1> <T2> <T3> ...` — Sector Sweep (variable)

Per ticker: fundamentals + industry + comps + macro in parallel. Then a
sector-overview synthesis written by md-synthesis.

Example: `/sector NVDA AMD AVGO ARM`

## `/screen "<criteria>"` — Stock Screen (~2 min)

FMP screener primary, WebSearch for thematic searches. Returns ranked
candidates with one-line theses (chat-only by default).

Example: `/screen "semis under $50B mcap with 20%+ ntm growth"`

## `/catalysts <TICKER>` — Catalyst Calendar (~30s)

Quick lookup of dated events: earnings dates, product launches, regulatory,
conferences.

Example: `/catalysts NVDA`

## `/help` — Print this file

Example: `/help`
