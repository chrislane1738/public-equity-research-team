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
import uuid
from pathlib import Path
from typing import Any

from backend.agents.comps import CompsAgent
from backend.agents.dcf import DCFAgent
from backend.agents.fundamentals import FundamentalsAgent
from backend.agents.industry import IndustryAgent
from backend.agents.macro import MacroAgent
from backend.agents.md import MDAgent
from backend.agents.deck_builder import DeckBuilderAgent
from backend.agents.memo_builder import MemoBuilderAgent
from backend.agents.risk import RiskAgent
from backend.agents.technicals import TechnicalsAgent
from backend.observability.job_logger import JobLogger


RATING_PATTERN = re.compile(r"\*\*Rating:\*\*\s*(Buy|Hold|Sell)", re.IGNORECASE)
PT_PATTERN = re.compile(
    r"\*\*(?:Price Target|PT)[^:]*:\*\*\s*\$?([0-9,.]+)", re.IGNORECASE
)


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

    async def run_full_deep_dive(self, ticker: str, job_id: str | None = None) -> dict[str, Any]:
        ticker = ticker.upper()
        ticker_dir = self.research_dir / ticker
        ticker_dir.mkdir(parents=True, exist_ok=True)
        job_id = job_id or str(uuid.uuid4())
        logger = JobLogger(job_id=job_id, log_dir=ticker_dir / "_logs")

        state: dict[str, Any] = {"ticker": ticker, "stages": {}, "status": "running",
                                 "job_id": job_id}

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
        fund_result = await fund.run(ticker=ticker, cik=cik, ticker_dir=ticker_dir)
        logger.log_agent("fundamentals", fund_result)
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
            if isinstance(res, Exception):
                state["stages"][name] = "failed"
                state.setdefault("errors", {})[name] = str(res)
                logger.log_error(name, str(res))
            else:
                state["stages"][name] = "complete"
                logger.log_agent(name, res)

        # Stage 2b — DCF (after Comps wrote peer-multiples.json)
        if state["stages"].get("comps") == "complete":
            dcf = DCFAgent(self.anthropic, self.fmp,
                           model=self.settings.model_for("dcf"))
            try:
                dcf_result = await dcf.run(ticker=ticker, ticker_dir=ticker_dir)
                state["stages"]["dcf"] = "complete"
                logger.log_agent("dcf", dcf_result)
            except Exception as exc:
                state["stages"]["dcf"] = "failed"
                state.setdefault("errors", {})["dcf"] = str(exc)
                logger.log_error("dcf", str(exc))
        else:
            state["stages"]["dcf"] = "skipped"

        # Stage 3 — Synthesis
        state["current_stage"] = "synthesis"
        md = MDAgent(self.anthropic, model=self.settings.model_for("md"))
        md_result = await md.synthesize(ticker=ticker, ticker_dir=ticker_dir)
        logger.log_agent("md", md_result)
        synthesis = (ticker_dir / "synthesis" / "_synthesis.md").read_text()
        state["rating"] = self._extract_rating(synthesis)
        state["stages"]["synthesis"] = "complete"

        # Stage 4 — Production (Deck + Memo, parallel)
        state["current_stage"] = "production"
        memo = MemoBuilderAgent(self.anthropic,
                                model=self.settings.model_for("memo_builder"))
        deck = DeckBuilderAgent(self.anthropic,
                                model=self.settings.model_for("deck_builder"))

        quote = await self.fmp.get_quote(ticker)
        current_price = quote.get("price", 0)
        # Try to read the blended PT off the synthesis; fall back to current.
        pt_value = self._extract_pt(synthesis) or current_price

        prod_results = await asyncio.gather(
            memo.run(ticker=ticker, ticker_dir=ticker_dir, rating=state["rating"]),
            deck.run(ticker=ticker, ticker_dir=ticker_dir, rating=state["rating"],
                     price_target=pt_value, current_price=current_price),
            return_exceptions=True,
        )
        for name, res in zip(["memo_builder", "deck_builder"], prod_results):
            if isinstance(res, Exception):
                state["stages"][name] = "failed"
                state.setdefault("errors", {})[name] = str(res)
                logger.log_error(name, str(res))
            else:
                state["stages"][name] = "complete"
                logger.log_agent(name, res)

        state["total_cost_usd"] = logger.total_cost_usd()
        state["status"] = "complete"
        state["current_stage"] = None
        return state

    async def run(self, workflow: str, **kwargs) -> dict[str, Any]:
        if workflow == "full-deep-dive":
            return await self.run_full_deep_dive(**kwargs)
        if workflow == "earnings-update":
            return await self.run_earnings_update(**kwargs)
        if workflow == "morning-note":
            return await self.run_morning_note(**kwargs)
        if workflow == "thesis-check":
            return await self.run_thesis_check(**kwargs)
        if workflow == "sector-sweep":
            return await self.run_sector_sweep(**kwargs)
        raise ValueError(f"unknown workflow: {workflow}")

    async def run_earnings_update(self, ticker: str, job_id: str | None = None) -> dict[str, Any]:
        raise NotImplementedError("Task 23")

    async def run_morning_note(self, ticker: str, job_id: str | None = None) -> dict[str, Any]:
        raise NotImplementedError("Task 24")

    async def run_thesis_check(self, ticker: str, question: str,
                               job_id: str | None = None) -> dict[str, Any]:
        raise NotImplementedError("Task 25")

    async def run_sector_sweep(self, tickers: list[str],
                               job_id: str | None = None) -> dict[str, Any]:
        raise NotImplementedError("Task 26")

    @staticmethod
    def _extract_rating(synthesis: str) -> str:
        m = RATING_PATTERN.search(synthesis)
        return m.group(1).title() if m else "Hold"

    @staticmethod
    def _extract_pt(synthesis: str) -> float | None:
        m = PT_PATTERN.search(synthesis)
        if not m:
            return None
        try:
            return float(m.group(1).replace(",", ""))
        except ValueError:
            return None
