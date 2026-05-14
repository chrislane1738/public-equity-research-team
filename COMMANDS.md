# Workflow commands

All workflows accept arguments inline (`/deep-dive NVDA`) and also work as
natural-language prompts ("deep-dive on NVDA").

## `/deep-dive <TICKER>` — Full Deep-Dive (~8 min)

Stages: accountant (filings audit) → fundamentals → 5 research pods in parallel
→ DCF (after comps) → synthesis → deck + memo in parallel → HTML rollup.

Outputs: every section.md + every artifact, plus `report.html`.

Example: `/deep-dive NVDA`

## `/earnings <TICKER>` — Earnings Update (~4 min)

Stages: accountant (lightweight — downloads latest 8-K + earnings deck) →
fundamentals (delta) → DCF + risk in parallel → memo.

Outputs: minimal — `fundamentals/section.md`, `dcf/section.md`,
`risk/section.md`, `reports/memo.docx`, `report.html`.

Example: `/earnings ANET`

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
