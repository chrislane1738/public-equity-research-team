# Public Equity Research Team

Local-first multi-agent equity research workstation. Claude Code is the managing director; 12 skills under `.claude/skills/` orchestrate 10 specialized research pods (Fundamentals · Industry · DCF · Comps · Macro · Risk · Technicals · Deck Builder · Memo Builder · MD) to produce institutional-quality research — pitch deck, written memo, one-pager, DCF model, comps table — for any US-listed equity.

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

## Development

```bash
# Activate the venv (carried over from the FastAPI build — still works)
source backend/venv/bin/activate
pytest tests/ -q
deactivate
```

Tests run under ~10 seconds — they exercise the deterministic helpers
(`tools/`) via mocked fixtures. Live API smoke is opt-in: run
`/deep-dive NVDA` inside Claude Code when you want a real end-to-end check.

## Workflows

| Workflow         | What it does                                                              | Wall-clock |
|------------------|---------------------------------------------------------------------------|------------|
| Full Deep-Dive   | All 10 pods → pitch deck + memo + one-pager + DCF + comps                 | ~7 min     |
| Earnings Update  | Fundamentals + DCF + Risk → memo only (no deck)                           | ~3 min     |
| Morning Note     | Fundamentals → MD writes a brief note                                     | ~1 min     |
| Thesis Check     | LLM-routed 2-3 pods focused on a specific question                        | varies     |
| Sector Sweep     | Industry + Comps + Macro across N tickers → sector overview               | varies     |

Outputs land at `~/Documents/equity-research/<TICKER>/` (configurable via `RESEARCH_DIR`).

## Repo layout

```
.claude/
  skills/            12 skill definitions (one per research pod + orchestration)
  commands/          8 slash commands (/deep-dive, /earnings, /morning-note, …)

tools/               Deterministic Python helpers
  fmp_client.py      Financial Modeling Prep wrapper
  edgar_client.py    SEC EDGAR wrapper
  fred_client.py     FRED macro data wrapper
  dcf_engine.py      DCF model engine
  charts.py          Chart generation
  writers/           xlsx / pptx / docx / pdf output

backend/venv/        Python virtualenv (test runner only — no server process)
tests/               pytest — 78 tests covering tools/ helpers
docs/superpowers/    specs + plans + handoffs
```

## Known limitations

- Single user, no auth.
- Local only — no cloud deploy.
- Equity only (no fixed income, FX, options).
- Manual quality eval (no automated scoring).

## Architecture

See `docs/superpowers/specs/2026-05-13-skill-based-migration-design.md` for the
full design spec. TL;DR: Claude Code is the MD; 12 skills under
`.claude/skills/`; 8 slash commands under `.claude/commands/`; deterministic
helpers under `tools/`.
