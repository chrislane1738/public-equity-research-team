---
description: Multi-ticker sector sweep — fundamentals/industry/comps/macro per ticker, then sector synthesis
argument-hint: <T1> <T2> <T3> [...]
---

Run a sector sweep across the tickers `$ARGUMENTS`.

For each ticker, in parallel where possible:
1. Dispatch `fundamentals`, `industry-moat`, `comps`, `macro` as subagents.
2. After all tickers finish their per-ticker pods, invoke `md-synthesis` in
   sector mode — write `<SECTOR>/sector-overview.md` triangulating which
   tickers screen best on growth, valuation, moat, and macro tailwinds.
3. Optional: invoke `synthesize-html` on the sector dir for an HTML rollup.

Sector dir: `~/Desktop/Agentic_Equity_Reports/_sectors/<slug>/` where `<slug>` is
derived from the ticker list (e.g., `nvda-amd-avgo-arm`).
