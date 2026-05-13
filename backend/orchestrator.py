"""Orchestrator — runs the workflow pipelines.

Stage layout (Full Deep-Dive):
  1. Fundamentals (sequential, blocks Stage 2).
  2a. Industry, Comps, Macro, Risk, Technicals (parallel via asyncio.gather).
  2b. DCF (after Comps writes peer-multiples.json).
  3. MD synthesis.
  4. Deck Builder + Memo Builder (parallel).

All Anthropic calls are throttled by a shared asyncio.Semaphore wrapping the
client. Per-agent model selection comes from Settings.model_for(agent_name).
"""
import asyncio
import re
from pathlib import Path
from typing import Any

from backend.agents.comps import CompsAgent
from backend.agents.dcf import DCFAgent
from backend.agents.fundamentals import FundamentalsAgent
from backend.agents.industry import IndustryAgent
from backend.agents.macro import MacroAgent
from backend.agents.md import MDAgent
from backend.agents.memo_builder import MemoBuilderAgent
from backend.agents.risk import RiskAgent
from backend.agents.technicals import TechnicalsAgent


RATING_PATTERN = re.compile(r"\*\*Rating:\*\*\s*(Buy|Hold|Sell)", re.IGNORECASE)


class Orchestrator:
    def __init__(
        self,
        anthropic_client,
        fmp_client,
        edgar_client,
        fred_client,
        research_dir: Path,
        cik_resolver,
        settings,
    ):
        self.anthropic = anthropic_client
        self.fmp = fmp_client
        self.edgar = edgar_client
        self.fred = fred_client
        self.research_dir = Path(research_dir)
        self.cik_resolver = cik_resolver
        self.settings = settings

    async def run_full_deep_dive(self, ticker: str) -> dict[str, Any]:
        ticker = ticker.upper()
        ticker_dir = self.research_dir / ticker
        ticker_dir.mkdir(parents=True, exist_ok=True)

        state: dict[str, Any] = {"ticker": ticker, "stages": {}, "status": "running"}

        # Stage 1 — Fundamentals
        state["current_stage"] = "fundamentals"
        try:
            cik = await self.cik_resolver.resolve(ticker)
        except Exception as exc:
            state["status"] = "failed"
            state["error"] = f"CIK lookup failed for {ticker}: {exc}"
            return state
        fund = FundamentalsAgent(
            anthropic_client=self.anthropic,
            fmp_client=self.fmp, edgar_client=self.edgar,
            model=self.settings.model_for("fundamentals"),
        )
        await fund.run(ticker=ticker, cik=cik, ticker_dir=ticker_dir)
        state["stages"]["fundamentals"] = "complete"

        # Stage 2a — Industry, Comps, Macro, Risk, Technicals (parallel)
        state["current_stage"] = "research"
        industry = IndustryAgent(self.anthropic, self.fmp,
                                 model=self.settings.model_for("industry"))
        comps = CompsAgent(self.anthropic, self.fmp,
                           model=self.settings.model_for("comps"))
        macro = MacroAgent(self.anthropic, self.fred,
                           model=self.settings.model_for("macro"))
        risk = RiskAgent(self.anthropic,
                         model=self.settings.model_for("risk"))
        technicals = TechnicalsAgent(self.anthropic, self.fmp,
                                     model=self.settings.model_for("technicals"))
        results_2a = await asyncio.gather(
            industry.run(ticker=ticker, ticker_dir=ticker_dir),
            comps.run(ticker=ticker, ticker_dir=ticker_dir),
            macro.run(ticker=ticker, ticker_dir=ticker_dir, catalysts=[]),
            risk.run(ticker=ticker, ticker_dir=ticker_dir),
            technicals.run(ticker=ticker, ticker_dir=ticker_dir),
            return_exceptions=True,
        )
        for name, res in zip(["industry", "comps", "macro", "risk", "technicals"],
                             results_2a):
            state["stages"][name] = "failed" if isinstance(res, Exception) else "complete"
            if isinstance(res, Exception):
                state.setdefault("errors", {})[name] = str(res)

        # Stage 2b — DCF (after Comps wrote peer-multiples.json)
        if state["stages"].get("comps") == "complete":
            dcf = DCFAgent(self.anthropic, self.fmp,
                           model=self.settings.model_for("dcf"))
            try:
                await dcf.run(ticker=ticker, ticker_dir=ticker_dir)
                state["stages"]["dcf"] = "complete"
            except Exception as exc:
                state["stages"]["dcf"] = "failed"
                state.setdefault("errors", {})["dcf"] = str(exc)
        else:
            state["stages"]["dcf"] = "skipped"

        # Stage 3 — Synthesis
        state["current_stage"] = "synthesis"
        md = MDAgent(self.anthropic, model=self.settings.model_for("md"))
        await md.synthesize(ticker=ticker, ticker_dir=ticker_dir)
        synthesis = (ticker_dir / "synthesis" / "_synthesis.md").read_text()
        state["rating"] = self._extract_rating(synthesis)
        state["stages"]["synthesis"] = "complete"

        # Stage 4 — Production (Memo only — Task 19 wires Deck in parallel)
        state["current_stage"] = "production"
        memo = MemoBuilderAgent(self.anthropic,
                                model=self.settings.model_for("memo_builder"))
        await memo.run(ticker=ticker, ticker_dir=ticker_dir, rating=state["rating"])
        state["stages"]["memo_builder"] = "complete"

        state["status"] = "complete"
        state["current_stage"] = None
        return state

    @staticmethod
    def _extract_rating(synthesis: str) -> str:
        m = RATING_PATTERN.search(synthesis)
        return m.group(1).title() if m else "Hold"
