"""Orchestrator — runs the 4-stage Full Deep-Dive pipeline.

Plan A scope: only the full-deep-dive workflow with stubbed research pods.
Plan B will branch this for earnings-update / morning-note / thesis-check /
sector-sweep workflows.
"""
import asyncio
import re
from pathlib import Path
from typing import Any

from backend.agents._stubs import STUB_AGENTS, run_stub
from backend.agents.fundamentals import FundamentalsAgent
from backend.agents.md import MDAgent
from backend.agents.memo_builder import MemoBuilderAgent


RATING_PATTERN = re.compile(r"\*\*Rating:\*\*\s*(Buy|Hold|Sell)", re.IGNORECASE)


class Orchestrator:
    def __init__(
        self,
        anthropic_client,
        fmp_client,
        edgar_client,
        research_dir: Path,
        ticker_to_cik: dict[str, str],
        opus_model: str,
        sonnet_model: str,
    ):
        self.anthropic = anthropic_client
        self.fmp = fmp_client
        self.edgar = edgar_client
        self.research_dir = Path(research_dir)
        self.ticker_to_cik = ticker_to_cik
        self.opus_model = opus_model
        self.sonnet_model = sonnet_model

    async def run_full_deep_dive(self, ticker: str) -> dict[str, Any]:
        ticker = ticker.upper()
        ticker_dir = self.research_dir / ticker
        ticker_dir.mkdir(parents=True, exist_ok=True)

        state: dict[str, Any] = {"ticker": ticker, "stages": {}, "status": "running"}

        # Stage 1 — Fundamentals (sequential)
        state["current_stage"] = "fundamentals"
        cik = self.ticker_to_cik.get(ticker)
        if not cik:
            state["status"] = "failed"
            state["error"] = f"No CIK mapping for {ticker}"
            return state
        fund_agent = FundamentalsAgent(
            anthropic_client=self.anthropic,
            fmp_client=self.fmp,
            edgar_client=self.edgar,
            model=self.opus_model,
        )
        await fund_agent.run(ticker=ticker, cik=cik, ticker_dir=ticker_dir)
        state["stages"]["fundamentals"] = "complete"

        # Stage 2 — Stub research pods (parallel)
        state["current_stage"] = "research"
        await asyncio.gather(
            *(run_stub(name, ticker, ticker_dir) for name in STUB_AGENTS)
        )
        for name in STUB_AGENTS:
            state["stages"][name] = "complete"

        # Stage 3 — Synthesis
        state["current_stage"] = "synthesis"
        md_agent = MDAgent(anthropic_client=self.anthropic, model=self.opus_model)
        await md_agent.synthesize(ticker=ticker, ticker_dir=ticker_dir)
        synthesis = (ticker_dir / "synthesis" / "_synthesis.md").read_text()
        rating = self._extract_rating(synthesis)
        state["rating"] = rating
        state["stages"]["synthesis"] = "complete"

        # Stage 4 — Production (Memo only in Plan A)
        state["current_stage"] = "production"
        memo_agent = MemoBuilderAgent(
            anthropic_client=self.anthropic, model=self.sonnet_model
        )
        await memo_agent.run(ticker=ticker, ticker_dir=ticker_dir, rating=rating)
        state["stages"]["memo_builder"] = "complete"

        state["status"] = "complete"
        state["current_stage"] = None
        return state

    @staticmethod
    def _extract_rating(synthesis: str) -> str:
        m = RATING_PATTERN.search(synthesis)
        return m.group(1).title() if m else "Hold"
