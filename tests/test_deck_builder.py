import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from pptx import Presentation

from backend.agents.deck_builder import DeckBuilderAgent


class FakeMsg:
    def __init__(self, text):
        self.content = [MagicMock(type="text", text=text)]
        self.usage = MagicMock(input_tokens=100, output_tokens=400)
        self.stop_reason = "end_turn"


SLIDE_PACK_JSON = json.dumps({
    "thesis_bullets": [
        "Data Center capex tailwind",
        "CUDA moat sustaining pricing",
        "FCF inflection ahead of estimates",
    ],
    "triangulation_rows": [
        ["DCF GGM",     116, 0.20],
        ["DCF Exit",    200, 0.30],
        ["DCF Blend",   158, 0.20],
        ["Comps median",165, 0.20],
        ["52-wk anchor",130, 0.10],
    ],
    "top_risks": ["AI capex digestion", "China revenue", "Custom silicon"],
    "slide_bodies": {
        "Investment Thesis": "Three reasons we like NVDA.",
        "Business Snapshot": "Compute & Networking + Graphics.",
        "Industry & Moat": "Wide CUDA moat.",
        "Bespoke KPIs": "Data Center revenue, gross margin.",
        "Financial Performance": "Revenue +126% YoY, GM 73%.",
        "Forecast": "Revenue $250B by FY28.",
        "DCF": "WACC 10.5%, blended PT $158.",
        "Comps": "30x peer median EV/EBITDA.",
        "Valuation Triangulation": "DCF + Comps + 52-wk anchor.",
        "Catalysts": "Q1 earnings, GTC keynote.",
        "Risks / Bear Case": "AI capex digestion → -25% rev.",
        "Technical Setup": "Uptrend, stop $95.",
        "Recommendation": "Buy, 12-month horizon."
    }
})


@pytest.fixture
def mock_anthropic():
    c = MagicMock()
    c.messages.create = AsyncMock(return_value=FakeMsg(text=SLIDE_PACK_JSON))
    return c


def _seed_ticker_dir(td: Path) -> None:
    (td / "synthesis").mkdir(parents=True)
    (td / "synthesis" / "_synthesis.md").write_text(
        "# Synthesis\n**Rating:** Buy\n**PT:** $158\n"
        "## Triangulation\n- DCF Blend $158 (50%)\n- Comps median $165 (50%)\n"
    )
    for sub in ["fundamentals", "industry", "dcf", "comps", "macro", "risk", "technicals"]:
        (td / sub).mkdir(parents=True, exist_ok=True)
        (td / sub / "section.md").write_text(f"# {sub}\nbody\n")


async def test_deck_builder_writes_pptx_and_pdf(tmp_path, mock_anthropic):
    td = tmp_path / "NVDA"
    _seed_ticker_dir(td)
    agent = DeckBuilderAgent(anthropic_client=mock_anthropic,
                             model="claude-sonnet-4-6")
    await agent.run(ticker="NVDA", ticker_dir=td, rating="Buy",
                    price_target=158.0, current_price=110.0)

    pptx_path = td / "reports" / "pitch.pptx"
    pdf_path = td / "reports" / "onepager.pdf"
    assert pptx_path.exists()
    assert pdf_path.exists()

    pres = Presentation(pptx_path)
    assert len(pres.slides) == 14
