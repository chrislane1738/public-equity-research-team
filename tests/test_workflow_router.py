from unittest.mock import AsyncMock, MagicMock

import pytest

pytestmark = pytest.mark.skip(reason="rewired in T13 of skill-migration")

from backend.orchestrator import Orchestrator


@pytest.fixture
def settings():
    s = MagicMock()
    s.model_for = MagicMock(side_effect=lambda agent: "claude-opus-4-7")
    return s


def _make_orch(tmp_path, settings):
    return Orchestrator(
        anthropic_client=MagicMock(), fmp_client=MagicMock(),
        edgar_client=MagicMock(), fred_client=MagicMock(),
        research_dir=tmp_path,
        cik_resolver=MagicMock(), settings=settings,
    )


async def test_run_dispatches_full_deep_dive(tmp_path, settings):
    orch = _make_orch(tmp_path, settings)
    orch.run_full_deep_dive = AsyncMock(return_value={"status": "complete"})
    out = await orch.run(workflow="full-deep-dive", ticker="NVDA", job_id="j1")
    orch.run_full_deep_dive.assert_awaited_once_with(ticker="NVDA", job_id="j1")
    assert out["status"] == "complete"


async def test_run_dispatches_earnings_update(tmp_path, settings):
    orch = _make_orch(tmp_path, settings)
    orch.run_earnings_update = AsyncMock(return_value={"status": "complete"})
    await orch.run(workflow="earnings-update", ticker="NVDA", job_id="j2")
    orch.run_earnings_update.assert_awaited_once_with(ticker="NVDA", job_id="j2")


async def test_run_dispatches_morning_note(tmp_path, settings):
    orch = _make_orch(tmp_path, settings)
    orch.run_morning_note = AsyncMock(return_value={"status": "complete"})
    await orch.run(workflow="morning-note", ticker="NVDA", job_id="j3")
    orch.run_morning_note.assert_awaited_once_with(ticker="NVDA", job_id="j3")


async def test_run_dispatches_thesis_check(tmp_path, settings):
    orch = _make_orch(tmp_path, settings)
    orch.run_thesis_check = AsyncMock(return_value={"status": "complete"})
    await orch.run(workflow="thesis-check", ticker="NVDA", job_id="j4",
                   question="Is the AI capex story still intact?")
    orch.run_thesis_check.assert_awaited_once_with(
        ticker="NVDA", job_id="j4",
        question="Is the AI capex story still intact?",
    )


async def test_run_dispatches_sector_sweep(tmp_path, settings):
    orch = _make_orch(tmp_path, settings)
    orch.run_sector_sweep = AsyncMock(return_value={"status": "complete"})
    await orch.run(workflow="sector-sweep", tickers=["NVDA", "AMD"], job_id="j5")
    orch.run_sector_sweep.assert_awaited_once_with(
        tickers=["NVDA", "AMD"], job_id="j5",
    )


async def test_run_raises_on_unknown_workflow(tmp_path, settings):
    orch = _make_orch(tmp_path, settings)
    with pytest.raises(ValueError, match="unknown workflow"):
        await orch.run(workflow="bogus", ticker="NVDA", job_id="jx")
