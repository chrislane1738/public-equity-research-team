# Public Equity Research Team

Local-first multi-agent equity research workstation. Claude Code is the managing director; **13 skills** under `.claude/skills/` orchestrate a roster of specialized research pods (Accountant · Fundamentals · Industry · DCF · Comps · Macro · Risk · Technicals · Deck Builder · Memo Builder · MD) to produce institutional-quality research — pitch deck, written memo, one-pager, DCF model, comps table, self-contained HTML report — for any US-listed equity.

## Usage

1. Set up `.env` (copy `.env.example`):
   - `FMP_API_KEY` — Financial Modeling Prep ($20-50/mo)
   - `FRED_API_KEY` — Federal Reserve Economic Data (free)
   - `SEC_EDGAR_USER_AGENT` — `Your Name your.email@example.com` (SEC fair-use)

2. From the repo root:
   ```bash
   claude
   ```

3. Type a workflow command, e.g. `/deep-dive NVDA`, or just talk naturally:
   "deep-dive on NVDA". Claude routes the request through the skill pipeline
   and lands artifacts under `~/Documents/equity-research/<TICKER>/`.

4. Open `<TICKER>/report.html` in your browser. That's the canonical
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
source backend/venv/bin/activate
pytest tests/ -q
deactivate
```

Tests run in ~4 seconds — they exercise the deterministic helpers (`tools/`)
via mocked fixtures. Live API smoke is opt-in: run `/deep-dive NVDA` inside
Claude Code when you want a real end-to-end check.

## Workflows

| Command | What it does | Wall-clock |
|---|---|---|
| `/deep-dive <T>` | All pods → accountant audit + deck + memo + one-pager + DCF + comps + HTML | ~8 min |
| `/update <T>` | Quarterly refresh on a covered name; diff-style synthesis vs prior run | ~4-5 min |
| `/earnings <T>` | Fundamentals + DCF + Risk → memo (lightweight accountant) | ~4 min |
| `/morning <T>` | Fundamentals → MD writes a brief note | ~1 min |
| `/thesis <T> "<q>"` | LLM-routed 2-3 pods focused on a specific question | varies |
| `/sector <T1> <T2> …` | Industry + Comps + Macro across N tickers → sector overview | varies |
| `/screen "<criteria>"` | FMP screener + WebSearch → ranked candidates | ~2 min |
| `/catalysts <T>` | Quick dated-events lookup | ~30s |
| `/help` | Print `COMMANDS.md` | instant |

Outputs land at `~/Documents/equity-research/<TICKER>/` (configurable via `RESEARCH_DIR`).

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

All providers cache to `~/Documents/equity-research/_cache/` with a 24h TTL.

**Quality rule:** FMP's pre-calculated ratio/multiple/TTM endpoints are *never*
used — they go stale at fiscal period-end. Every margin, multiple, and TTM
figure is computed manually from raw 3-statement line items + the live quote.
The accountant independently reconciles the most recent annual + quarterly
SEC filings against FMP and pauses for the user if anything diverges.

## Repo layout

```
.claude/
  skills/            13 skill definitions (one per research pod + orchestration)
  commands/          9 slash commands (/deep-dive, /update, /earnings, …)

tools/               Deterministic Python helpers
  marketdata/        FMP + yfinance abstraction (MarketData facade)
  edgar.py           SEC EDGAR client (edgartools-backed)
  fred.py            FRED macro data client
  dcf_engine.py      DCF model engine
  multiples.py       Comps multiples math
  charts.py          Chart generation
  html_writer.py     Self-contained report.html assembler
  settings.py        Dotenv-loaded keys

backend/venv/        Python virtualenv (test runner only — no server process)
backend/requirements.txt   Pinned dependencies
tests/               pytest — 144 tests covering tools/ helpers
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
accountant forensic sub-passes). TL;DR: Claude Code is the MD; 13 skills under
`.claude/skills/`; 9 slash commands under `.claude/commands/`; deterministic
helpers under `tools/`.
