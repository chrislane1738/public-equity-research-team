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

### Step 3 — Dispatch Off-the-Shelf Skill

- Invoke `financial-analysis:comps-analysis` via the Skill tool with:
  - ticker
  - final peer list (8–12 tickers)
  - data directory: `~/Documents/equity-research/<TICKER>/`
  - output paths: `comps/comps.xlsx`, `comps/box-plot.png`

### Step 4 — Write peer-multiples.json

After the comps run, write `comps/peer-multiples.json` with exactly this shape:

```json
{
  "peer_median_ev_ebitda": <number>,
  "peer_p75_ev_ebitda": <number>,
  "peers": ["TICK1", "TICK2", ...]
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
