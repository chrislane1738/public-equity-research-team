"""Tests for tools/edgar.py — existing + T27 additions."""
from pathlib import Path

import pytest
import respx
from httpx import Response

from tools.edgar import EdgarClient


FIXTURE_HTML = (Path(__file__).parent / "fixtures" / "edgar_nvda_10k.html").read_text()

# ------------------------------------------------------------------
# Minimal payloads for mocking
# ------------------------------------------------------------------

MINIMAL_SUBMISSIONS = {
    "cik": "0001045810",
    "name": "NVIDIA CORP",
    "tickers": ["NVDA"],
    "filings": {
        "recent": {
            "form":                   ["10-K", "10-Q", "8-K"],
            "accessionNumber":        ["0001045810-24-000029", "0001045810-24-000050", "0001045810-24-000060"],
            "filingDate":             ["2024-02-21", "2024-05-29", "2024-06-10"],
            "reportDate":             ["2024-01-28", "2024-04-28", ""],
            "primaryDocument":        ["nvda-20240128.htm", "nvda-20240428.htm", "8k.htm"],
            "primaryDocDescription":  ["10-K", "10-Q", "", ],
        }
    },
}

MINIMAL_COMPANYFACTS = {
    "cik": "CIK0001045810",
    "entityName": "NVIDIA CORP",
    "facts": {
        "us-gaap": {
            "Revenues": {
                "label": "Revenues",
                "description": "Amount of revenue.",
                "units": {
                    "USD": [
                        {
                            "start": "2023-01-29",
                            "end":   "2024-01-28",
                            "val":   60922000000,
                            "accn":  "0001045810-24-000029",
                            "fy":    2024,
                            "fp":    "FY",
                            "form":  "10-K",
                            "filed": "2024-02-21",
                            "frame": "CY2024",
                        }
                    ]
                },
            }
        }
    },
}

# ------------------------------------------------------------------
# Fixture
# ------------------------------------------------------------------


@pytest.fixture
def client(tmp_path):
    return EdgarClient(user_agent="Test test@example.com", cache_dir=tmp_path)


# ------------------------------------------------------------------
# Existing test — fetch_10k_excerpt (must still pass after refactor)
# ------------------------------------------------------------------


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


# ------------------------------------------------------------------
# 2.1 — get_company_submissions
# ------------------------------------------------------------------


@respx.mock(using="httpx")
async def test_get_company_submissions_returns_parsed_dict(client, respx_mock):
    respx_mock.get("https://data.sec.gov/submissions/CIK0001045810.json").mock(
        return_value=Response(200, json=MINIMAL_SUBMISSIONS)
    )

    result = await client.get_company_submissions("1045810")

    assert result["cik"] == "0001045810"
    assert result["name"] == "NVIDIA CORP"
    assert "10-K" in result["filings"]["recent"]["form"]


@respx.mock(using="httpx")
async def test_get_company_submissions_uses_zero_padded_cik(client, respx_mock):
    """CIK is zero-padded to 10 digits in the URL regardless of input form."""
    route = respx_mock.get("https://data.sec.gov/submissions/CIK0001045810.json").mock(
        return_value=Response(200, json=MINIMAL_SUBMISSIONS)
    )

    await client.get_company_submissions("1045810")  # short form
    assert route.called


@respx.mock(using="httpx")
async def test_get_company_submissions_caches_result(client, respx_mock, tmp_path):
    """Second call returns cached value without a second HTTP request."""
    route = respx_mock.get("https://data.sec.gov/submissions/CIK0001045810.json").mock(
        return_value=Response(200, json=MINIMAL_SUBMISSIONS)
    )

    await client.get_company_submissions("1045810")
    await client.get_company_submissions("1045810")

    assert route.call_count == 1  # only one real HTTP call


# ------------------------------------------------------------------
# 2.2 — get_company_facts
# ------------------------------------------------------------------


@respx.mock(using="httpx")
async def test_get_company_facts_returns_parsed_dict(client, respx_mock):
    respx_mock.get(
        "https://data.sec.gov/api/xbrl/companyfacts/CIK0001045810.json"
    ).mock(return_value=Response(200, json=MINIMAL_COMPANYFACTS))

    result = await client.get_company_facts("1045810")

    assert result["entityName"] == "NVIDIA CORP"
    revenues = result["facts"]["us-gaap"]["Revenues"]["units"]["USD"]
    assert len(revenues) == 1
    assert revenues[0]["val"] == 60922000000
    assert revenues[0]["form"] == "10-K"


@respx.mock(using="httpx")
async def test_get_company_facts_caches_result(client, respx_mock):
    route = respx_mock.get(
        "https://data.sec.gov/api/xbrl/companyfacts/CIK0001045810.json"
    ).mock(return_value=Response(200, json=MINIMAL_COMPANYFACTS))

    await client.get_company_facts("1045810")
    await client.get_company_facts("1045810")

    assert route.call_count == 1


# ------------------------------------------------------------------
# 2.3 — list_filings
# ------------------------------------------------------------------


@respx.mock(using="httpx")
async def test_list_filings_no_filter_returns_all_up_to_limit(client, respx_mock):
    respx_mock.get("https://data.sec.gov/submissions/CIK0001045810.json").mock(
        return_value=Response(200, json=MINIMAL_SUBMISSIONS)
    )

    filings = await client.list_filings("1045810", limit=10)

    assert len(filings) == 3  # all three filings in the fixture
    assert {f["form"] for f in filings} == {"10-K", "10-Q", "8-K"}


@respx.mock(using="httpx")
async def test_list_filings_filters_by_form_type(client, respx_mock):
    respx_mock.get("https://data.sec.gov/submissions/CIK0001045810.json").mock(
        return_value=Response(200, json=MINIMAL_SUBMISSIONS)
    )

    filings = await client.list_filings("1045810", form_types=["10-K", "10-Q"])

    assert len(filings) == 2
    assert all(f["form"] in ("10-K", "10-Q") for f in filings)


@respx.mock(using="httpx")
async def test_list_filings_respects_limit(client, respx_mock):
    respx_mock.get("https://data.sec.gov/submissions/CIK0001045810.json").mock(
        return_value=Response(200, json=MINIMAL_SUBMISSIONS)
    )

    filings = await client.list_filings("1045810", limit=1)

    assert len(filings) == 1


@respx.mock(using="httpx")
async def test_list_filings_entry_shape(client, respx_mock):
    respx_mock.get("https://data.sec.gov/submissions/CIK0001045810.json").mock(
        return_value=Response(200, json=MINIMAL_SUBMISSIONS)
    )

    filings = await client.list_filings("1045810", form_types=["10-K"])

    assert len(filings) == 1
    f = filings[0]
    assert f["accession_number"] == "0001045810-24-000029"
    assert f["form"] == "10-K"
    assert f["filing_date"] == "2024-02-21"
    assert f["report_date"] == "2024-01-28"
    assert f["primary_document"] == "nvda-20240128.htm"


# ------------------------------------------------------------------
# 2.4 — download_filing_document
# ------------------------------------------------------------------


@respx.mock(using="httpx")
async def test_download_filing_document_writes_file(client, respx_mock, tmp_path):
    expected_url = (
        "https://www.sec.gov/Archives/edgar/data/1045810/"
        "000104581024000029/nvda-20240128.htm"
    )
    binary_content = b"<html><body>10-K content</body></html>"
    respx_mock.get(expected_url).mock(
        return_value=Response(200, content=binary_content)
    )

    out = tmp_path / "filings" / "nvda-20240128.htm"
    result = await client.download_filing_document(
        cik="0001045810",
        accession_number="0001045810-24-000029",
        primary_document="nvda-20240128.htm",
        output_path=out,
    )

    assert result == out
    assert out.exists()
    assert out.read_bytes() == binary_content


@respx.mock(using="httpx")
async def test_download_filing_document_correct_url_construction(client, respx_mock, tmp_path):
    """Dashes in accession number must be stripped; CIK must be unpadded int."""
    captured_url = None

    def capture(request):
        nonlocal captured_url
        captured_url = str(request.url)
        return Response(200, content=b"data")

    respx_mock.get(
        "https://www.sec.gov/Archives/edgar/data/1045810/"
        "000104581024000029/nvda-20240128.htm"
    ).mock(side_effect=capture)

    await client.download_filing_document(
        cik="0001045810",          # padded
        accession_number="0001045810-24-000029",  # with dashes
        primary_document="nvda-20240128.htm",
        output_path=tmp_path / "out.htm",
    )

    assert captured_url is not None
    assert "000104581024000029" in captured_url   # dashes stripped
    assert "/1045810/" in captured_url             # CIK unpadded


@respx.mock(using="httpx")
async def test_download_filing_document_creates_parent_dirs(client, respx_mock, tmp_path):
    respx_mock.get(
        "https://www.sec.gov/Archives/edgar/data/1045810/"
        "000104581024000029/nvda-20240128.htm"
    ).mock(return_value=Response(200, content=b"data"))

    deep_path = tmp_path / "a" / "b" / "c" / "filing.htm"
    assert not deep_path.parent.exists()

    await client.download_filing_document(
        cik="1045810",
        accession_number="0001045810-24-000029",
        primary_document="nvda-20240128.htm",
        output_path=deep_path,
    )

    assert deep_path.exists()


# ------------------------------------------------------------------
# 2.5 — extract_filing_section
# ------------------------------------------------------------------

# A minimal 10-K HTML that exercises the case-insensitive fix:
#  - Uses uppercase "ITEM 7." (the bug trigger) and "ITEM 7A."
_UPPERCASE_10K_HTML = """
<html><body>
<h2>ITEM 1. BUSINESS</h2>
<p>We make widgets.</p>
<h2>ITEM 1A. RISK FACTORS</h2>
<p>Market volatility risk.</p>
<h2>ITEM 2. PROPERTIES</h2>
<p>We lease office space.</p>
<h2>ITEM 7. MANAGEMENT'S DISCUSSION AND ANALYSIS</h2>
<p>Revenue increased 30% year over year.</p>
<p>Operating income improved significantly.</p>
<h2>ITEM 7A. QUANTITATIVE AND QUALITATIVE DISCLOSURES ABOUT MARKET RISK</h2>
<p>Interest rate sensitivity.</p>
<h2>ITEM 8. FINANCIAL STATEMENTS AND SUPPLEMENTARY DATA</h2>
<p>See consolidated financial statements below.</p>
</body></html>
"""

# A mixed-case fixture for completeness
_MIXED_CASE_10K_HTML = """
<html><body>
<h2>Item 7. Management's Discussion and Analysis</h2>
<p>Gross profit grew 15%.</p>
<h2>Item 7A. Quantitative and Qualitative Disclosures About Market Risk</h2>
<p>Foreign exchange exposure.</p>
</body></html>
"""


def test_extract_filing_section_mda_uppercase_markers():
    """Core regression: uppercase ITEM 7. must be matched and cut before ITEM 7A."""
    result = EdgarClient.extract_filing_section(_UPPERCASE_10K_HTML, "mda")
    assert "Revenue increased 30%" in result
    assert "Operating income improved" in result
    # ITEM 7A text must NOT bleed in
    assert "Interest rate sensitivity" not in result


def test_extract_filing_section_mda_mixed_case():
    result = EdgarClient.extract_filing_section(_MIXED_CASE_10K_HTML, "mda")
    assert "Gross profit grew 15%" in result
    assert "Foreign exchange exposure" not in result


def test_extract_filing_section_risk_factors():
    result = EdgarClient.extract_filing_section(_UPPERCASE_10K_HTML, "risk_factors")
    assert "Market volatility risk" in result
    # should not bleed into properties
    assert "We lease office space" not in result


def test_extract_filing_section_business():
    result = EdgarClient.extract_filing_section(_UPPERCASE_10K_HTML, "business")
    assert "We make widgets" in result
    assert "Market volatility risk" not in result


def test_extract_filing_section_financial_statements():
    result = EdgarClient.extract_filing_section(_UPPERCASE_10K_HTML, "financial_statements")
    assert "consolidated financial statements" in result
    # ITEM 7A text is before Item 8 and should not be present
    assert "Interest rate sensitivity" not in result


def test_extract_filing_section_returns_empty_for_missing_section():
    html = "<html><body><p>No SEC items here.</p></body></html>"
    result = EdgarClient.extract_filing_section(html, "mda")
    assert result == ""


def test_extract_filing_section_caps_at_max_length():
    # Build an artificially large section
    large_content = "<p>" + ("x" * 100) + "</p>\n" * 1000  # ~101 000 chars
    html = (
        f"<html><body><h2>Item 7. MD&A</h2>{large_content}"
        "<h2>Item 7A. Market Risk</h2><p>stop here</p></body></html>"
    )
    result = EdgarClient.extract_filing_section(html, "mda")
    assert len(result) <= 50_000


def test_extract_filing_section_raises_for_unknown_section():
    with pytest.raises(ValueError, match="Unknown section_id"):
        EdgarClient.extract_filing_section("<html/>", "unknown_section")


# ------------------------------------------------------------------
# 2.6 — fetch_10k_excerpt now uses extract_filing_section (fixture test)
#        uses the UPPERCASE fixture to verify the bug is fixed end-to-end
# ------------------------------------------------------------------


@respx.mock(using="httpx")
async def test_fetch_10k_excerpt_fixed_for_uppercase_items(client, respx_mock):
    """fetch_10k_excerpt must return MD&A content even when markers are uppercase."""
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
    ).mock(return_value=Response(200, text=_UPPERCASE_10K_HTML))

    excerpt = await client.fetch_10k_excerpt("NVDA", cik="0001045810")

    assert "Revenue increased 30%" in excerpt
    assert "Interest rate sensitivity" not in excerpt  # 7A must be excluded


# ------------------------------------------------------------------
# lookup_cik — ticker → CIK via SEC's official mapping file
# ------------------------------------------------------------------

SEC_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"

MINIMAL_TICKER_MAPPING = {
    "0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."},
    "1": {"cik_str": 789019, "ticker": "MSFT", "title": "Microsoft Corp"},
    "2": {"cik_str": 723125, "ticker": "MU", "title": "Micron Technology, Inc."},
}


@respx.mock(using="httpx")
async def test_lookup_cik_returns_padded_string_for_known_us_ticker(client, respx_mock):
    respx_mock.get(SEC_TICKERS_URL).mock(return_value=Response(200, json=MINIMAL_TICKER_MAPPING))
    cik = await client.lookup_cik("MU")
    assert cik == "0000723125"


@respx.mock(using="httpx")
async def test_lookup_cik_is_case_insensitive(client, respx_mock):
    respx_mock.get(SEC_TICKERS_URL).mock(return_value=Response(200, json=MINIMAL_TICKER_MAPPING))
    cik = await client.lookup_cik("aapl")
    assert cik == "0000320193"


@respx.mock(using="httpx")
async def test_lookup_cik_returns_none_for_foreign_ticker(client, respx_mock):
    respx_mock.get(SEC_TICKERS_URL).mock(return_value=Response(200, json=MINIMAL_TICKER_MAPPING))
    cik = await client.lookup_cik("005930.KS")  # Samsung — not in SEC mapping
    assert cik is None


@respx.mock(using="httpx")
async def test_lookup_cik_caches_the_mapping_file(client, respx_mock):
    """Two consecutive calls hit the network only once."""
    route = respx_mock.get(SEC_TICKERS_URL).mock(
        return_value=Response(200, json=MINIMAL_TICKER_MAPPING)
    )
    cik1 = await client.lookup_cik("AAPL")
    cik2 = await client.lookup_cik("AAPL")
    assert cik1 == "0000320193"
    assert cik2 == "0000320193"
    assert route.call_count == 1
