# Public Equity Research Team

![tests](https://img.shields.io/badge/tests-211%20passing-2ea44f)
![python](https://img.shields.io/badge/python-3.14-3776ab)
![license](https://img.shields.io/badge/license-MIT-blue)
![built with Claude Code](https://img.shields.io/badge/built%20with-Claude%20Code-d97757)

Local-first multi-agent equity research workstation. Claude Code is the managing director; **14 skills** under `.claude/skills/` orchestrate a roster of specialized research pods (Accountant · Fundamentals · Industry · Model · DCF · Comps · Macro · Risk · Technicals · Deck Builder · Memo Builder · MD) to produce institutional-quality research — pitch deck, written memo, one-pager, 3-statement model, DCF model, comps table, self-contained HTML report — for any US-listed equity.

## Prerequisites — read before first run

**1. You must supply your own API keys via `.env`.** The `.env` file is *not*
checked into the repo (it's gitignored so no keys ever leak). Copy
`.env.example` → `.env` at the repo root and fill in your own keys. The desk is
built on these data providers:

| Key | Powers | Required? | Where to get it |
|---|---|---|---|
| `FMP_API_KEY` | All market data — 3-statement financials, quotes, prices, peers, estimates | **Required** — nothing runs without it | [Financial Modeling Prep](https://site.financialmodelingprep.com/) (paid, ~$20-50/mo) |
| `SEC_EDGAR_USER_AGENT` | SEC EDGAR filings — 10-K / 10-Q / Form 4 / 13F / 13D-G | **Required** — SEC fair-use policy mandates it | Free — set it to `Your Name your.email@example.com` |
| `FRED_API_KEY` | The `macro` skill — rates, inflation, FX, catalyst calendar | Needed for `/deep-dive` & `macro`; other workflows degrade gracefully without it | Free — [FRED API key](https://fred.stlouisfed.org/docs/api/api_key.html) |

`ANTHROPIC_API_KEY` is **not** required — Claude Code runs on your existing
Claude subscription, with no per-token API spend.

**2. Generated research is written outside this repo.** Reports never land in
the git tree. Every run writes to:

```
~/Desktop/Agentic_Equity_Reports/<TICKER>/
```

The directory is created automatically on first run, and holds the reports,
companion files, and shared data caches. Change the location by setting
`RESEARCH_DIR` in `.env` (e.g. `RESEARCH_DIR=~/research`).

## Usage

1. Install Python dependencies (Python 3.14; a virtualenv is recommended):
   ```bash
   python3 -m venv .venv && source .venv/bin/activate
   pip install -r requirements.txt
   ```

2. Create your `.env` (copy `.env.example` → `.env` and fill in your keys —
   see [Prerequisites](#prerequisites--read-before-first-run) above for which
   keys are required and where to get them).

3. From the repo root:
   ```bash
   claude
   ```

4. Type a workflow command, e.g. `/deep-dive NVDA`, or just talk naturally:
   "deep-dive on NVDA". Claude routes the request through the skill pipeline
   and lands artifacts under `~/Desktop/Agentic_Equity_Reports/<TICKER>/`.

5. Open `<TICKER>/report.html` in your browser. That's the canonical
   deliverable. Companion `.docx`, `.pptx`, `.xlsx` sit alongside it.

See `COMMANDS.md` for the full workflow reference.

### Human-in-the-loop checkpoints

`/deep-dive` pauses three times for your input — so no agent ever runs on bad data:

- **After the accountant** — review the SEC-vs-FMP reconciliation and red flags. If figures diverge, you choose which source to trust per line item.
- **Before the research pods** — you supply the peer ticker list for comps (no auto-picked peers).
- **After synthesis** — you choose which deliverables to build ({memo, deck, html}), skipping what you don't need to save tokens.

## Development

```bash
# Activate the venv (test runner only — no server process)
source .venv/bin/activate
pytest tests/ -q
deactivate
```

Tests run in ~4 seconds — they exercise the deterministic helpers (`tools/`)
via mocked fixtures. Live API smoke is opt-in: run `/deep-dive NVDA` inside
Claude Code when you want a real end-to-end check.

## Workflows

| Command | What it does | Wall-clock |
|---|---|---|
| `/deep-dive <T>` | All pods → accountant audit + 3-statement model + DCF + comps + scenario analysis + deck + memo + one-pager + HTML | ~35-50 min |
| `/update <T>` | Quarterly refresh on a covered name; diff-style synthesis vs prior run | ~4-5 min |
| `/earnings <T>` | Fundamentals + DCF + Risk → memo (lightweight accountant) | ~4 min |
| `/morning <T>` | Fundamentals → MD writes a brief note | ~1 min |
| `/thesis <T> "<q>"` | LLM-routed 2-3 pods focused on a specific question | varies |
| `/sector <T1> <T2> …` | Industry + Comps + Macro across N tickers → sector overview | varies |
| `/screen "<criteria>"` | FMP screener + WebSearch → ranked candidates | ~2 min |
| `/catalysts <T>` | Quick dated-events lookup | ~30s |
| `/help` | Print `COMMANDS.md` | instant |

*A full `/deep-dive` runs **~35-50 minutes** wall-clock and consumes roughly **800K–950K tokens** end to end — about 650K across the nine research subagents (each on its own isolated context window — the `model` skill runs twice, build then scenarios) plus orchestration and synthesis. Adding the memo and deck deliverables is ~120K more. Lighter workflows scale down proportionally.*

Outputs land at `~/Desktop/Agentic_Equity_Reports/<TICKER>/` (configurable via `RESEARCH_DIR`).

## Data layer

`tools/marketdata.MarketData` is the single market-data entry point — FMP primary,
yfinance fallback, all responses normalized to TypedDicts. Skills never touch raw
provider payloads.

- **FMP** — 3 statements, profile, quote, historical prices, peers, estimates,
  treasury rates, short interest.
- **yfinance** — keyless fallback.
- **FRED** — macro series (rates, inflation, FX), 24h disk cache.
- **SEC EDGAR** — backed by the [`edgartools`](https://github.com/dgunning/edgartools)
  library: filings, XBRL company facts, **Form 4 insider transactions**,
  **13F-HR institutional holdings**, **Schedule 13D/13G activist stakes**, and
  **segment-level XBRL facts**.

All providers cache to `~/Desktop/Agentic_Equity_Reports/_cache/` with a 24h TTL.

**Quality rule:** FMP's pre-calculated ratio/multiple/TTM endpoints are *never*
used — they go stale at fiscal period-end. Every margin, multiple, and TTM
figure is computed manually from raw 3-statement line items + the live quote.
The accountant independently reconciles the most recent annual + quarterly
SEC filings against FMP and pauses for the user if anything diverges.

## Repo layout

```
.claude/
  skills/            14 skill definitions (one per research pod + orchestration)
  commands/          9 slash commands (/deep-dive, /update, /earnings, …)

tools/               Deterministic Python helpers
  marketdata/        FMP + yfinance abstraction (MarketData facade)
  edgar.py           SEC EDGAR client (edgartools-backed)
  fred.py            FRED macro data client
  model_engine.py    3-statement revenue / FCF projection engine
  dcf_engine.py      DCF engine — WACC, regression beta, terminal value, discounting
  multiples.py       Comps multiples math
  charts.py          Chart generation
  html_writer.py     Self-contained report.html assembler
  settings.py        Dotenv-loaded keys

requirements.txt     Pinned dependencies
tests/               pytest — 211 tests covering tools/ helpers
docs/superpowers/    specs + plans + handoffs
```

## Known limitations

- Single user, no auth.
- Local only — no cloud deploy.
- Equity only (no fixed income, FX, options).
- US-listed names only (SEC reconciliation needs a CIK; foreign tickers fall
  back to FMP-only data).
- Manual quality eval (no automated scoring).
- `MarketData.screen` is a stub — comps requires a user-supplied peer list.

## Architecture

See `docs/superpowers/specs/2026-05-13-skill-based-migration-design.md` for the
full design spec, and `docs/superpowers/handoff/2026-05-15-data-layer-forensic-update.md`
for the current capability surface (data layer, EDGAR ownership methods,
accountant forensic sub-passes). TL;DR: Claude Code is the MD; 14 skills under
`.claude/skills/`; 9 slash commands under `.claude/commands/`; deterministic
helpers under `tools/`.
