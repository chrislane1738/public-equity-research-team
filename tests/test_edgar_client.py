from pathlib import Path

import pytest
import respx
from httpx import Response

from backend.tools.edgar_client import EdgarClient


FIXTURE_HTML = (Path(__file__).parent / "fixtures" / "edgar_nvda_10k.html").read_text()


@pytest.fixture
def client():
    return EdgarClient(user_agent="Test test@example.com")


@respx.mock(using="httpx")
async def test_extract_sections_pulls_business_risk_mda(client, respx_mock):
    respx_mock.get("https://data.sec.gov/submissions/CIK0001045810.json").mock(
        return_value=Response(200, json={
            "filings": {
                "recent": {
                    "form": ["10-K"],
                    "accessionNumber": ["0001045810-24-000029"],
                    "primaryDocument": ["nvda-20240128.htm"],
                }
            }
        })
    )
    respx_mock.get(
        "https://www.sec.gov/Archives/edgar/data/1045810/000104581024000029/nvda-20240128.htm"
    ).mock(return_value=Response(200, text=FIXTURE_HTML))

    excerpt = await client.fetch_10k_excerpt("NVDA", cik="0001045810")

    assert "Business" in excerpt
    assert "two reportable segments" in excerpt
    assert "Risk Factors" in excerpt
    assert "supply chain concentration" in excerpt
    assert "Management's Discussion" in excerpt
    assert "Revenue grew 126%" in excerpt
    # confirm the items that should be cut are absent
    assert "Item 1B" not in excerpt
    assert "Item 7A" not in excerpt
