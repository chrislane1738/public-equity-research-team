# Memory — Data Layer + Forensic Update

**Date:** 2026-05-15
**Purpose:** Durable record of the system's current capability surface after the edgartools migration, the SEC ownership-data additions, the short-interest layer, and the accountant's forensic sub-passes. Read this to understand what the workstation can do today without re-deriving it from 1,200-line source files.

---

## 1. What the system is (current state)

A local-first equity research workstation that runs entirely inside Claude Code. Claude is the Managing Director; 13 skills under `.claude/skills/` and 9 slash commands under `.claude/commands/` orchestrate a roster of research pods to produce institutional-quality research per US-listed ticker. No server, no UI, no per-token API spend beyond the Claude plan.

- **Architecture spec:** `docs/superpowers/specs/2026-05-13-skill-based-migration-design.md`
- **Migration plan (executed):** `docs/superpowers/plans/2026-05-13-skill-migration.md`
- **Tests:** 144 passing (pytest, ~4s, mocked fixtures — no live API in CI).
- **Deliverable per ticker:** `~/Documents/equity-research/<TICKER>/report.html` (self-contained) + companion `.docx`/`.pptx`/`.xlsx`.

## 2. Skill roster (13)

| Skill | Role | Loaded as |
|---|---|---|
| `accountant` | SEC filings pull + FMP reconciliation + 16-category red-flag audit + earnings-deck download | Subagent |
| `fundamentals` | 3 statements + 10-K + bespoke KPIs + ownership/insider + capital-return durability | Subagent |
| `industry-moat` | Porter's 5 forces, moat verdict, peer-share dynamics | Subagent |
| `dcf` | Wraps `financial-analysis:dcf-model`; manual WACC; TTM base year | Subagent |
| `comps` | User-supplied peer list; multiples computed manually from raw statements | Subagent |
| `macro` | FRED rates/FX/inflation + catalyst calendar | Subagent |
| `risk-upside` | Bull/bear cases, swing factors, bear-case PT, short-side dynamics | Subagent |
| `technicals` | SMA/RSI/ATR + entry/stop levels (sidecar — never sets the rating) | Subagent |
| `md-synthesis` | Rating, PT, valuation triangulation; `mode="update"` diff variant | Skill (in-context) |
| `memo-builder` | `reports/memo.docx` (deep-dive or earnings variant) | Subagent |
| `deck-builder` | `reports/pitch.pptx` (16 slides incl. Accounting Audit slide) | Subagent |
| `synthesize-html` | `report.html` via `tools.html_writer` | Skill (in-context) |
| `screen` | Stock screen / thematic idea generation | Skill or Subagent |

## 3. Slash commands (9)

`/deep-dive` · `/update` · `/earnings` · `/morning` · `/thesis` · `/sector` · `/screen` · `/catalysts` · `/help`

`/deep-dive` has **three mandatory human-in-the-loop pause checkpoints** — the orchestrator stops and waits for the user:
- **Pause A** — after the accountant: review reconciliation result + red flags. If the accountant returns `PAUSE_FOR_REVIEW`, the user resolves each divergent line item (SEC / FMP / manual).
- **Pause B** — before the 5-pod batch: user supplies the peer ticker list (mandatory — no FMP-curated or LLM-picked peers).
- **Pause C** — after synthesis: user picks which deliverables to produce ({memo, deck, html}), skipping unwanted production subagents to save tokens.

`/update` (quarterly refresh on a previously-covered name) and `/earnings` carry the relevant subset of these pauses.

## 4. Data layer

`tools/marketdata.MarketData` is the single entry point for market data — FMP primary, yfinance fallback, normalized to the TypedDicts in `tools/marketdata/interface.py`. Skills never see raw provider payloads.

- **FMP** (`tools/marketdata/fmp.py`) — 3 statements (annual + quarterly), profile, quote, historical prices, peers, estimates, treasury rates, symbol search, **short interest** (`get_short_interest` — FINRA bi-monthly; degrades to `[]` on any HTTP error).
- **yfinance** — keyless fallback for profile/quote/historical/short-interest.
- **FRED** (`tools/fred.py`) — macro series, 24h disk cache.
- **SEC EDGAR** (`tools/edgar.py`) — see §5.
- **Disk cache:** every provider caches under `~/Documents/equity-research/_cache/` with a 24h TTL.

**Quality rules (non-negotiable — see memory `feedback-fmp-calculated-fields`):** never use FMP's pre-calculated `key-metrics`/`ratios` endpoints or its TTM endpoint. Every margin, multiple, ratio, and TTM figure is computed manually from raw 3-statement line items + the live quote. The `fundamentals` skill pulls quarterly statements and verifies the most recent quarter is captured (see `feedback-latest-earnings-check`).

## 5. SEC EDGAR — now backed by `edgartools`

`tools/edgar.py` is backed by the **`edgartools`** library (v5.31.2, MIT, free, no API key) for all SEC HTTP access — edgartools manages rate-limiting, the SEC contact-info identity, retries, and a throttle cache. The legacy hand-rolled regex section extractor is retained as `_extract_filing_section_regex` (fallback). The pypdf PDF path is unchanged (edgartools doesn't parse PDFs). SEC identity is wired once via `_ensure_identity`.

**Methods:**
- `lookup_cik(ticker)` — ticker → 10-digit CIK via SEC's official mapping; `None` for foreign-listed (signals accountant FMP-only fallback).
- `get_company_submissions` / `get_company_facts` — submissions list + XBRL companyfacts.
- `list_filings` / `download_filing_document` — filtered filing list + document download.
- `extract_filing_section` / `_pdf` / `_auto` — section extraction (HTML, PDF, or auto-dispatch by extension); `_normalize_item_markers` handles legacy markers (HTML entities, nbsp, §).
- `fetch_10k_excerpt` — latest 10-K key sections.
- **`get_insider_transactions(ticker, cik, recent_filings=40)`** — Form 4 insider buy/sell, flattened transactions + aggregate (net_shares, bought, sold, distinct_insiders, window).
- **`get_institutional_holdings(cik)`** — **filer-centric**: the latest 13F-HR holdings for the *manager whose CIK is passed* (NOT "who holds company X") + QoQ delta.
- **`get_activist_stakes(cik, limit=20)`** — Schedule 13D/13G stakes against the subject company. 13D = active/activist, 13G = passive. Only structured-XML filings (late-2024 onward) are machine-parsed.
- **`get_segment_facts(ticker, cik)`** — segment-level XBRL facts (revenue/op-income per reportable segment) via dimensional XBRL; feeds the accountant's quantitative segment-reorg check.

## 6. Accountant — forensic sub-passes

The accountant's red-flag audit (Step 9) is 16 categories (RF-01 to RF-16). Five forensic sub-passes were added on top:

- **Footnote walk (revenue-recognition leg)** — RF-01, deep-dive only. Systematic walk of every Item 8 footnote for revenue-recognition substance.
- **Conf-call analyst-Q&A sentiment** — RF-01 + RF-02, **all modes**. Parses the earnings-call Q&A transcript; flags analyst pushback met with evasive management answers.
- **Quantitative segment-reorg audit** — RF-06, deep-dive only. Uses `get_segment_facts` to catch silent segment mix shifts / count changes that the narrative MD&A check misses.
- **Footnote walk (off-balance-sheet leg)** — RF-08, deep-dive only. Leases, commitments/contingencies, VIEs.
- **Debt covenant scan** — RF-08, deep-dive only. Extracts covenant thresholds, compares to reported leverage/coverage, flags thin cushions.
- **5-year capital-allocation pass** — RF-08, deep-dive only. Sources-and-uses; flags debt-funded buybacks.

`mode="earnings-update"` runs only the conf-call Q&A sub-pass (the others need the 10-K + multi-year history that earnings mode doesn't pull). The accountant returns one of three signals to the MD: `CLEAN`, `PAUSE_FOR_REVIEW`, `FMP_ONLY_FALLBACK`.

## 7. Skill-level additions consuming the new data

- **`fundamentals`** — two situational subsections: **Ownership & Insider Flow** (uses `get_insider_transactions` + `get_activist_stakes`; RUN by default, SKIP only sub-$300M micro-caps with immaterial insiders) and **Capital Return Durability** (dividend-safety; SKIP non-payers with one line, RUN any cash-dividend payer). Both gates are exhaustive.
- **`risk-upside`** — **Short-side dynamics** step (always runs). Calls `MarketData.get_short_interest`; escalation gate at >10% short-of-float / >5 days-to-cover / >50% rise in shares-short inserts a detailed subsection and applies an extra 5–15% haircut to the bear-case PT.

## 8. For the next session

- The pipeline is feature-complete and on branch `feat/skill-based-migration` (not yet merged to `main`). `main` still holds the dead FastAPI/Next.js build.
- A live `/deep-dive` smoke on MU (2026-05-14) surfaced and fixed the FMP-stale-ratios and missing-quarterly-data bugs; MU artifacts were deleted afterward and the pipeline re-tightened.
- Known follow-ups not yet done: `MarketData.screen` is still a `return []` stub (Tier-3 auto-screen non-functional — comps relies on the mandatory user peer list instead).
- `edgartools` is in `backend/requirements.txt` as `edgartools==5.31.2` (the `[ai]` extra was deliberately dropped — it conflicts with starlette/pydantic).
