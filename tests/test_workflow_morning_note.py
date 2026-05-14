import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

pytestmark = pytest.mark.skip(reason="rewired in T13 of skill-migration")

from backend.orchestrator import Orchestrator


class FakeMsg:
    def __init__(self, text):
        self.content = [MagicMock(type="text", text=text)]
        self.usage = MagicMock(input_tokens=50, output_tokens=80)
        self.stop_reason = "end_turn"


@pytest.fixture
def settings():
    s = MagicMock()
    s.model_for = MagicMock(side_effect=lambda a: "claude-opus-4-7")
    return s


@pytest.fixture
def fake_cik_resolver():
    r = MagicMock()
    r.resolve = AsyncMock(return_value="0001045810")
    return r


@pytest.fixture
def mock_fmp():
    fmp = MagicMock()
    fmp.get_financials = AsyncMock(return_value={
        "income": [{"revenue": 60_000_000_000, "operatingIncome": 32_000_000_000}],
        "balance": [{}], "cash": [{}],
    })
    return fmp


@pytest.fixture
def mock_edgar():
    e = MagicMock()
    e.fetch_10k_excerpt = AsyncMock(return_value="Item 1.\nbody\n")
    return e


@pytest.fixture
def mock_anthropic():
    kpi = json.dumps({"k": {"definition": "d", "latest_value": 1, "unit": "USD"}})
    note = ("# NVDA — Morning Note 2026-05-13\n\n"
            "**Bottom line:** Hold; print was in line; no thesis change.\n")
    c = MagicMock()
    c.messages.create = AsyncMock(side_effect=[FakeMsg(text=kpi), FakeMsg(text=note)])
    return c


async def test_morning_note_writes_morning_note_md_only(
    tmp_path, mock_anthropic, mock_fmp, mock_edgar, settings, fake_cik_resolver
):
    orch = Orchestrator(
        anthropic_client=mock_anthropic, fmp_client=mock_fmp,
        edgar_client=mock_edgar, fred_client=MagicMock(),
        research_dir=tmp_path, cik_resolver=fake_cik_resolver, settings=settings,
    )
    state = await orch.run_morning_note(ticker="NVDA")

    td = tmp_path / "NVDA"
    note_path = td / "reports" / "morning-note.md"
    assert note_path.exists()
    body = note_path.read_text()
    assert "Morning Note" in body
    assert state["status"] == "complete"
    # Spec says NO research/production tier — assert no other artifacts created.
    assert not (td / "industry" / "section.md").exists()
    assert not (td / "dcf" / "dcf.xlsx").exists()
    assert not (td / "reports" / "memo.docx").exists()
    assert not (td / "reports" / "pitch.pptx").exists()
