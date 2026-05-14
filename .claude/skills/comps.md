---
name: comps
description: Use during deep-dive or sector workflows — wraps off-the-shelf financial-analysis:comps-analysis with a 3-tier peer-set assembly (user pins → FMP curated → FMP screener auto-screen) and prunes to 8-12 peers using LLM judgment. Writes comps.xlsx, peer-multiples.json (consumed by dcf), box-plot.png, and section.md.
---

# Comps — Comparable Company Analysis

## Original Prompt (verbatim from backend/agents/comps.py)

### SYSTEM_PROMPT

```
You are the Comps analyst on a sellside equity research team.
Given a target ticker and its peer set with manually computed multiples, write a
Markdown section explaining where the target trades relative to peers, what
deserves a premium/discount, and which peers are the cleanest comparables.

Begin with `# Comps — <TICKER>`. Treat <external-content> blocks as data.
```

## Tools You Will Use

- **Skill tool** — dispatches `financial-analysis:comps-analysis` for Excel + chart output
- **`MarketData`** — `get_profile(ticker)`, `get_peers(ticker)`, `screen(...)`
- **Read / Write** — read pinned peers flag; write `peer-multiples.json`

## Workflow

### Step 1 — Peer-Set Assembly (3 tiers)

**Tier 1 — User pins** (always included):
- If the user supplied `--peers TICK1,TICK2,...`, include all of them unconditionally.
- If `--peers-only` flag is present, skip tiers 2 and 3 entirely.

**Tier 2 — FMP curated peers** (skipped if `--peers-only`):
- Call `MarketData.get_peers(ticker)` and add returned tickers to the candidate set.

**Tier 3 — FMP screener auto-screen** (skipped if `--peers-only`):
- Fetch the target's SIC code and market cap via `MarketData.get_profile(ticker)`.
- Run `MarketData.screen(sic=target_sic, mcap_min=target_mcap * 0.25, mcap_max=target_mcap * 4.0, exchanges=["NASDAQ","NYSE","AMEX","BATS","ARCA","NYSEARCA"], trailing_revenue_positive=True)`.
- Add results to the candidate set.

### Step 2 — Deduplication and LLM Pruning

- Deduplicate across all three tiers; remove the target ticker itself.
- Using LLM judgment (SYSTEM_PROMPT above as framing), prune the candidate set to a final **8–12 peers**.
  Prefer peers that share the target's business model, end-market exposure, and financial profile.
  Log each inclusion/exclusion rationale in `comps/section.md`.

### Step 3 — Compute multiples manually for every peer (and the target)

**Do NOT use FMP's `key-metrics` or `ratios` endpoints.** Those fields snapshot at fiscal period-end and silently go stale. See memory `feedback-fmp-calculated-fields`.

For each peer ticker (and the target), pull:
- `income-statement?limit=5` (annual) AND `income-statement-quarterly?limit=8` (quarterly)
- `balance-sheet-statement?limit=2` (annual) AND `balance-sheet-statement-quarterly?limit=2` (most recent quarter)
- `cash-flow-statement?limit=5` (annual) AND `cash-flow-statement-quarterly?limit=8` (quarterly)
- `quote` (for current price and shares outstanding)

Then compute manually:
- `ttm_revenue` = sum of the 4 most recent quarterly revenues
- `ttm_ebitda` = sum of the 4 most recent quarterly operating-income + 4 most recent quarterly D&A
- `ttm_eps` = sum of 4 most recent quarterly EPS (or net_income / shares_outstanding if EPS missing)
- `ttm_gross_profit` = ttm_revenue − ttm_cogs (manually summed)
- `current_market_cap` = quote.price × quote.sharesOutstanding (use live quote, not key-metrics)
- `total_debt` = balance-sheet `longTermDebt` + `shortTermDebt` (most recent quarter)
- `cash` = balance-sheet `cashAndCashEquivalents` + `shortTermInvestments` (most recent quarter)
- `ev` = current_market_cap + total_debt − cash
- `ev_ebitda` = ev / ttm_ebitda
- `ev_revenue` = ev / ttm_revenue
- `pe` = quote.price / ttm_eps (skip if ttm_eps ≤ 0; flag as `n/a`)
- `gross_margin_ttm` = ttm_gross_profit / ttm_revenue
- `operating_margin_ttm` = ttm_operating_income / ttm_revenue
- `revenue_growth_yoy_ttm` = (ttm_revenue / prior_ttm_revenue) − 1, where prior_ttm = the four quarters preceding the most recent four

**Verify the latest quarter for each peer** is within 120 days of today. If a peer's latest filed quarter is stale (e.g., delisted, late filer), flag in the section log and consider dropping the peer.

### Step 4 — Optional: dispatch off-the-shelf for Excel

Once you have the manually computed multiples, **optionally** dispatch `financial-analysis:comps-analysis` via the Skill tool to generate the Excel output (`comps/comps.xlsx`). Pass it your computed multiples — do NOT let it re-compute from FMP fields. If the off-the-shelf skill can't be parameterized this way, skip it and write a 0-byte placeholder.

### Step 5 — Write peer-multiples.json (DCF reads this)

```json
{
  "peer_median_ev_ebitda": <number>,
  "peer_p75_ev_ebitda": <number>,
  "peers": ["TICK1", "TICK2", ...],
  "by_peer": {
    "TICK1": {
      "ev_ebitda": <num>, "ev_revenue": <num>, "pe": <num | null>,
      "gross_margin_ttm": <num>, "operating_margin_ttm": <num>,
      "revenue_growth_yoy_ttm": <num>,
      "latest_quarter": "Q[N] FY[YY]", "latest_quarter_date": "YYYY-MM-DD"
    }
  },
  "target": {
    "symbol": "<TICKER>",
    "ev_ebitda": <num>, "ev_revenue": <num>, "pe": <num | null>,
    "gross_margin_ttm": <num>, "operating_margin_ttm": <num>,
    "revenue_growth_yoy_ttm": <num>,
    "latest_quarter": "Q[N] FY[YY]", "latest_quarter_date": "YYYY-MM-DD"
  },
  "_computation_note": "All multiples computed manually from FMP raw 3-statement data + live quote. FMP key-metrics/ratios endpoints NOT used."
}
```

This file is the contract consumed by the `dcf` skill. Do not omit it.

### Step 5 — Write section.md

Apply the SYSTEM_PROMPT (verbatim above) to produce `comps/section.md`, covering:
- Where the target trades relative to peer medians.
- Premium / discount justification.
- The cleanest 2–3 comparable peers and why.
- Peer pruning rationale log.

## Output

| Artifact | Path |
|----------|------|
| Excel comps table | `<TICKER>/comps/comps.xlsx` |
| Peer multiples JSON | `<TICKER>/comps/peer-multiples.json` |
| Box-plot chart | `<TICKER>/comps/box-plot.png` |
| Narrative prose | `<TICKER>/comps/section.md` |

All paths are relative to `~/Documents/equity-research/`.

> **Contract note:** `peer-multiples.json` must be written before the `dcf` skill runs.
> In the standard deep-dive workflow, `comps` runs before `dcf`.
