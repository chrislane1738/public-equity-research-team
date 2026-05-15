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
# fetch_10k_excerpt — edgartools structured TenK path + regex fallback
# ------------------------------------------------------------------
#
# fetch_10k_excerpt now pulls sections from edgartools' structured TenK parser
# (Company.latest_tenk). We mock the edgartools `Company` so the TenK path is
# exercised without network access; a separate test drives the regex fallback.


class _FakeTenK:
    """Stand-in for edgartools' TenK object — exposes the section properties
    that EdgarClient._fetch_10k_sections_edgartools reads."""

    def __init__(self, business="", risk_factors="", management_discussion=""):
        self.business = business
        self.risk_factors = risk_factors
        self.management_discussion = management_discussion


class _FakeCompany:
    """Stand-in for edgartools' Company — yields a _FakeTenK or raises."""

    _tenk = None
    _html = None

    def __init__(self, identifier):
        self.identifier = identifier

    @property
    def latest_tenk(self):
        return type(self)._tenk

    def get_filings(self, form=None):
        return self  # chainable stub

    def latest(self):
        if type(self)._html is None:
            return None
        outer = self

        class _FakeFiling:
            def html(self_inner):
                return type(outer)._html

        return _FakeFiling()


async def test_fetch_10k_excerpt_uses_edgartools_tenk_sections(client, monkeypatch):
    """Primary path: sections come straight from edgartools' TenK object."""
    fake_tenk = _FakeTenK(
        business="Item 1. Business\nNVIDIA operates in two reportable segments.",
        risk_factors="Item 1A. Risk Factors\nWe face supply chain concentration risk.",
        management_discussion="Item 7. Management's Discussion\nRevenue grew 126% YoY.",
    )

    def _fake_company(identifier):
        c = _FakeCompany(identifier)
        type(c)._tenk = fake_tenk
        return c

    monkeypatch.setattr("tools.edgar.Company", _fake_company)

    excerpt = await client.fetch_10k_excerpt("NVDA", cik="0001045810")

    assert "two reportable segments" in excerpt
    assert "supply chain concentration" in excerpt
    assert "Revenue grew 126%" in excerpt
    # the --- delimiter joins the three sections
    assert excerpt.count("\n\n---\n\n") == 2


@respx.mock(using="httpx")
async def test_fetch_10k_excerpt_falls_back_to_raw_html(client, respx_mock, monkeypatch):
    """Fallback path: when edgartools' TenK yields nothing, fetch raw 10-K
    HTML and run the regex section extractor."""

    class _NoTenKCompany:
        def __init__(self, identifier):
            self.identifier = identifier

        @property
        def latest_tenk(self):
            return None  # forces the fallback

        def get_filings(self, form=None):
            return self

        def latest(self):
            outer = self

            class _Filing:
                def html(self_inner):
                    return FIXTURE_HTML

            return _Filing()

    monkeypatch.setattr("tools.edgar.Company", _NoTenKCompany)

    # This path emits two kinds of UserWarning: the "raw-HTML" fallback from
    # fetch_10k_excerpt, plus per-section "regex extractor" fallbacks from the
    # synthetic-fixture extract_filing_section calls. Capture all of them so
    # none leak, then assert the raw-HTML one is present.
    with pytest.warns(UserWarning) as record:
        excerpt = await client.fetch_10k_excerpt("NVDA", cik="0001045810")

    assert any("falling back to raw-HTML" in str(w.message) for w in record)
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


# NOTE: the synthetic-HTML fixtures below are not parseable by edgartools'
# structured HTMLParser (it returns no SEC sections for them), so every
# extract_filing_section call here legitimately exercises the *regex fallback*
# path and emits the fallback UserWarning. Each call is wrapped in
# pytest.warns(UserWarning) so that warning is asserted-and-consumed rather
# than leaked. The dedicated edgartools-branch coverage lives in
# test_extract_filing_section_uses_edgartools_branch / _warns_on_parser_failure.


def test_extract_filing_section_mda_uppercase_markers():
    """Core regression: uppercase ITEM 7. must be matched and cut before ITEM 7A.

    Exercises the regex fallback path (synthetic HTML, edgartools yields none).
    """
    with pytest.warns(UserWarning, match="falling back to regex"):
        result = EdgarClient.extract_filing_section(_UPPERCASE_10K_HTML, "mda")
    assert "Revenue increased 30%" in result
    assert "Operating income improved" in result
    # ITEM 7A text must NOT bleed in
    assert "Interest rate sensitivity" not in result


def test_extract_filing_section_mda_mixed_case():
    """Regex fallback path (synthetic HTML)."""
    with pytest.warns(UserWarning, match="falling back to regex"):
        result = EdgarClient.extract_filing_section(_MIXED_CASE_10K_HTML, "mda")
    assert "Gross profit grew 15%" in result
    assert "Foreign exchange exposure" not in result


def test_extract_filing_section_risk_factors():
    """Regex fallback path (synthetic HTML)."""
    with pytest.warns(UserWarning, match="falling back to regex"):
        result = EdgarClient.extract_filing_section(_UPPERCASE_10K_HTML, "risk_factors")
    assert "Market volatility risk" in result
    # should not bleed into properties
    assert "We lease office space" not in result


def test_extract_filing_section_business():
    """Regex fallback path (synthetic HTML)."""
    with pytest.warns(UserWarning, match="falling back to regex"):
        result = EdgarClient.extract_filing_section(_UPPERCASE_10K_HTML, "business")
    assert "We make widgets" in result
    assert "Market volatility risk" not in result


def test_extract_filing_section_financial_statements():
    """Regex fallback path (synthetic HTML)."""
    with pytest.warns(UserWarning, match="falling back to regex"):
        result = EdgarClient.extract_filing_section(_UPPERCASE_10K_HTML, "financial_statements")
    assert "consolidated financial statements" in result
    # ITEM 7A text is before Item 8 and should not be present
    assert "Interest rate sensitivity" not in result


def test_extract_filing_section_returns_empty_for_missing_section():
    """Regex fallback path (synthetic HTML)."""
    html = "<html><body><p>No SEC items here.</p></body></html>"
    with pytest.warns(UserWarning, match="falling back to regex"):
        result = EdgarClient.extract_filing_section(html, "mda")
    assert result == ""


def test_extract_filing_section_caps_at_max_length():
    """Regex fallback path (synthetic HTML)."""
    # Build an artificially large section
    large_content = "<p>" + ("x" * 100) + "</p>\n" * 1000  # ~101 000 chars
    html = (
        f"<html><body><h2>Item 7. MD&A</h2>{large_content}"
        "<h2>Item 7A. Market Risk</h2><p>stop here</p></body></html>"
    )
    with pytest.warns(UserWarning, match="falling back to regex"):
        result = EdgarClient.extract_filing_section(html, "mda")
    assert len(result) <= 50_000


def test_extract_filing_section_raises_for_unknown_section():
    with pytest.raises(ValueError, match="Unknown section_id"):
        EdgarClient.extract_filing_section("<html/>", "unknown_section")


# ------------------------------------------------------------------
# 2.5b — extract_filing_section: hermetic coverage of the *edgartools*
#        structured-parser branch (no network).
#
# On the synthetic test HTML, the real edgartools HTMLParser returns no SEC
# sections, so every offline test above falls through to the regex fallback.
# To exercise the edgartools branch deterministically we monkeypatch the
# `edgar.documents.HTMLParser` symbol that `_extract_section_via_edgartools`
# imports lazily, swapping in a fake parsed document.
# ------------------------------------------------------------------


class _FakeParsedDoc:
    """Stand-in for an edgartools parsed HTML document.

    Exposes the two methods `_extract_section_via_edgartools` calls:
    get_available_sec_sections() and get_sec_section(key).
    """

    def __init__(self, sections):
        # sections: {sec_section_key: text}
        self._sections = sections

    def get_available_sec_sections(self):
        return list(self._sections.keys())

    def get_sec_section(self, key):
        return self._sections.get(key, "")


def _make_fake_htmlparser(sections=None, raises=None):
    """Build a fake HTMLParser class for monkeypatching edgar.documents.HTMLParser.

    If `raises` is given, .parse() raises that exception; otherwise .parse()
    returns a _FakeParsedDoc carrying `sections`.
    """

    class _FakeHTMLParser:
        def parse(self, filing_html):
            if raises is not None:
                raise raises
            return _FakeParsedDoc(sections or {})

    return _FakeHTMLParser


def test_extract_filing_section_uses_edgartools_branch(monkeypatch):
    """When edgartools' parser yields the section, extract_filing_section
    returns the edgartools-parsed text and emits NO fallback warning."""
    fake_cls = _make_fake_htmlparser(
        sections={
            "part_ii_item_7": "MD&A via edgartools structured parser. "
                              "Revenue grew 42% on AI demand.",
        }
    )
    monkeypatch.setattr("edgar.documents.HTMLParser", fake_cls)

    import warnings as _w

    with _w.catch_warnings(record=True) as caught:
        _w.simplefilter("always")
        result = EdgarClient.extract_filing_section(
            "<html><body>irrelevant — parser is faked</body></html>", "mda"
        )

    assert "edgartools structured parser" in result
    assert "Revenue grew 42%" in result
    # the edgartools branch succeeded — no fallback warning of any kind
    assert not [w for w in caught if "falling back" in str(w.message)]


def test_extract_filing_section_warns_on_edgartools_parser_failure(monkeypatch):
    """When the edgartools entry point RAISES, the fallback fires, the regex
    result is returned, and the attribution warning (Fix 1) is emitted."""
    fake_cls = _make_fake_htmlparser(raises=RuntimeError("simulated parser crash"))
    monkeypatch.setattr("edgar.documents.HTMLParser", fake_cls)

    with pytest.warns(UserWarning) as record:
        result = EdgarClient.extract_filing_section(_UPPERCASE_10K_HTML, "mda")

    # regex fallback still produces the MD&A section, 7A excluded
    assert "Revenue increased 30%" in result
    assert "Interest rate sensitivity" not in result

    messages = [str(w.message) for w in record]
    # attribution warning names the exception type + message (Fix 1)
    assert any(
        "edgartools section parser failed" in m
        and "RuntimeError" in m
        and "simulated parser crash" in m
        for m in messages
    )


# ------------------------------------------------------------------
# 2.6 — fetch_10k_excerpt fallback path handles uppercase Item markers
#        (regression: the regex extractor must still match uppercase ITEM 7.)
# ------------------------------------------------------------------


async def test_fetch_10k_excerpt_fixed_for_uppercase_items(client, monkeypatch):
    """When the fallback regex extractor runs, uppercase ITEM 7. must still
    be matched and cut before ITEM 7A."""

    class _UppercaseHtmlCompany:
        def __init__(self, identifier):
            self.identifier = identifier

        @property
        def latest_tenk(self):
            return None  # forces the raw-HTML + regex fallback

        def get_filings(self, form=None):
            return self

        def latest(self):
            class _Filing:
                def html(self_inner):
                    return _UPPERCASE_10K_HTML

            return _Filing()

    monkeypatch.setattr("tools.edgar.Company", _UppercaseHtmlCompany)

    with pytest.warns(UserWarning):
        excerpt = await client.fetch_10k_excerpt("NVDA", cik="0001045810")

    assert "Revenue increased 30%" in excerpt
    assert "Interest rate sensitivity" not in excerpt  # 7A must be excluded


# ------------------------------------------------------------------
# lookup_cik — ticker → CIK via edgartools' get_company_tickers
# ------------------------------------------------------------------
#
# edgartools fetches the SEC ticker→CIK mapping internally and returns it as a
# pandas DataFrame (columns: cik, ticker, exchange, company). We mock that
# DataFrame at the `get_company_tickers` entry point so the EdgarClient's own
# zip/upper/zero-pad logic still runs against realistic data.

import pandas as pd

MINIMAL_TICKER_DF = pd.DataFrame(
    [
        {"cik": 320193, "ticker": "AAPL", "exchange": "NASDAQ", "company": "Apple Inc."},
        {"cik": 789019, "ticker": "MSFT", "exchange": "NASDAQ", "company": "Microsoft Corp"},
        {"cik": 723125, "ticker": "MU", "exchange": "NASDAQ", "company": "Micron Technology, Inc."},
    ]
)


@pytest.fixture
def mock_company_tickers(monkeypatch):
    """Patch edgartools' get_company_tickers to return a fixed DataFrame.

    Returns a counter dict so tests can assert how many times edgartools'
    network-backed loader was actually invoked (caching coverage).
    """
    calls = {"count": 0}

    def _fake_get_company_tickers(*args, **kwargs):
        calls["count"] += 1
        return MINIMAL_TICKER_DF.copy()

    # Patch in the `edgar` package — EdgarClient imports it lazily inside
    # _load_ticker_mapping, so patching the source module is what counts.
    monkeypatch.setattr("edgar.get_company_tickers", _fake_get_company_tickers)
    return calls


async def test_lookup_cik_returns_padded_string_for_known_us_ticker(client, mock_company_tickers):
    cik = await client.lookup_cik("MU")
    assert cik == "0000723125"


async def test_lookup_cik_is_case_insensitive(client, mock_company_tickers):
    cik = await client.lookup_cik("aapl")
    assert cik == "0000320193"


async def test_lookup_cik_returns_none_for_foreign_ticker(client, mock_company_tickers):
    cik = await client.lookup_cik("005930.KS")  # Samsung — not in SEC mapping
    assert cik is None


async def test_lookup_cik_caches_the_mapping_file(client, mock_company_tickers):
    """Two consecutive calls hit edgartools' loader only once (disk-cached)."""
    cik1 = await client.lookup_cik("AAPL")
    cik2 = await client.lookup_cik("AAPL")
    assert cik1 == "0000320193"
    assert cik2 == "0000320193"
    assert mock_company_tickers["count"] == 1  # only one real load


# ------------------------------------------------------------------
# _normalize_item_markers — HTML entities, nbsp, § notation
# ------------------------------------------------------------------

from tools.edgar import _normalize_item_markers


def test_normalize_item_markers_decodes_html_entities():
    # &#167; is § (numeric entity); &nbsp; is non-breaking space
    raw = "Item&nbsp;7. MD&amp;A"
    result = _normalize_item_markers(raw)
    assert "Item 7." in result  # nbsp normalized to plain space
    assert "MD&A" in result     # &amp; decoded


def test_normalize_item_markers_handles_nbsp_in_marker():
    raw = "Item\xa07. Management's Discussion"
    result = _normalize_item_markers(raw)
    assert "Item 7." in result


def test_normalize_item_markers_converts_section_sign_to_item():
    raw = "§ 7. MD&A Section"
    result = _normalize_item_markers(raw)
    assert "Item 7." in result


def test_extract_filing_section_handles_nbsp_in_item_marker():
    """Legacy filer with nbsp inside the marker — was a known parser miss.

    Exercises the regex fallback path (synthetic HTML).
    """
    html = """
    <html><body>
    <h2>Item&nbsp;7. MD&amp;A</h2>
    <p>Revenue increased 30%</p>
    <h2>Item&nbsp;7A. Quantitative Risk</h2>
    <p>Interest rate sensitivity</p>
    </body></html>
    """
    with pytest.warns(UserWarning, match="falling back to regex"):
        text = EdgarClient.extract_filing_section(html, "mda")
    assert "Revenue increased 30%" in text
    assert "Interest rate sensitivity" not in text


# ------------------------------------------------------------------
# extract_filing_section_pdf — pypdf-based extractor
# ------------------------------------------------------------------


def test_extract_filing_section_pdf_extracts_mda(monkeypatch, tmp_path):
    """Mock pypdf.PdfReader; verify section pattern matching on extracted text."""
    pdf_file = tmp_path / "fake.pdf"
    pdf_file.write_bytes(b"%PDF-1.4 stub")

    # Build a fake page whose extract_text() returns 10-K-like content.
    class _FakePage:
        def __init__(self, text):
            self._text = text
        def extract_text(self):
            return self._text

    class _FakeReader:
        def __init__(self, path):
            self.pages = [
                _FakePage("Cover page text\nItem 1. Business\nWe make things."),
                _FakePage("Item 7. MD&A\nRevenue rose 25%.\nGross margin held at 42%."),
                _FakePage("Item 7A. Quantitative Risk\nForeign currency exposure."),
                _FakePage("Item 8. Financial Statements\nSee tables."),
            ]

    monkeypatch.setattr("pypdf.PdfReader", _FakeReader)
    text = EdgarClient.extract_filing_section_pdf(pdf_file, "mda")
    assert "Revenue rose 25%" in text
    assert "Gross margin held at 42%" in text
    # Stop boundary respected — 7A content should not bleed through
    assert "Foreign currency exposure" not in text
    # And shouldn't drift into Item 8 either
    assert "See tables" not in text


def test_extract_filing_section_pdf_returns_empty_when_section_absent(monkeypatch, tmp_path):
    pdf_file = tmp_path / "fake.pdf"
    pdf_file.write_bytes(b"%PDF-1.4 stub")

    class _FakePage:
        def extract_text(self):
            return "This filing has no Item markers at all, just narrative."

    class _FakeReader:
        def __init__(self, path):
            self.pages = [_FakePage()]

    monkeypatch.setattr("pypdf.PdfReader", _FakeReader)
    text = EdgarClient.extract_filing_section_pdf(pdf_file, "mda")
    assert text == ""


def test_extract_filing_section_pdf_rejects_unknown_section_id(tmp_path):
    pdf_file = tmp_path / "fake.pdf"
    pdf_file.write_bytes(b"%PDF-1.4 stub")
    with pytest.raises(ValueError, match="Unknown section_id"):
        EdgarClient.extract_filing_section_pdf(pdf_file, "executive_summary")


# ------------------------------------------------------------------
# extract_filing_section_auto — dispatcher by file extension
# ------------------------------------------------------------------


def test_extract_filing_section_auto_dispatches_html(tmp_path):
    """Dispatches to extract_filing_section; synthetic HTML hits the regex
    fallback path, so the fallback warning is expected."""
    f = tmp_path / "filing.htm"
    f.write_text("<html><body><h2>Item 7. MD&A</h2><p>Revenue up 10%.</p>"
                 "<h2>Item 7A. Risk</h2><p>FX exposure.</p></body></html>")
    with pytest.warns(UserWarning, match="falling back to regex"):
        text = EdgarClient.extract_filing_section_auto(f, "mda")
    assert "Revenue up 10%" in text


def test_extract_filing_section_auto_dispatches_pdf(monkeypatch, tmp_path):
    pdf_file = tmp_path / "filing.pdf"
    pdf_file.write_bytes(b"%PDF-1.4 stub")

    class _FakePage:
        def extract_text(self):
            return "Item 7. MD&A\nNet income flat.\nItem 7A. Risk\nrate sensitivity"

    class _FakeReader:
        def __init__(self, path):
            self.pages = [_FakePage()]

    monkeypatch.setattr("pypdf.PdfReader", _FakeReader)
    text = EdgarClient.extract_filing_section_auto(pdf_file, "mda")
    assert "Net income flat" in text


def test_extract_filing_section_auto_rejects_unsupported_extension(tmp_path):
    f = tmp_path / "filing.txt"
    f.write_text("Item 7. MD&A\nstuff")
    with pytest.raises(ValueError, match="Unsupported filing format"):
        EdgarClient.extract_filing_section_auto(f, "mda")


# ------------------------------------------------------------------
# Network integration tests — verify the *real* edgartools paths.
#
# The offline unit tests above mock edgartools at its entry points so they run
# fast and deterministically; they prove the EdgarClient wiring and the regex
# fallback, but not edgartools itself. These opt-in tests hit live SEC via
# edgartools to confirm the structured-parser path actually works.
#
# Run them explicitly:  pytest tests/test_edgar.py -m network
# They are skipped by default so the standard suite stays offline.
# ------------------------------------------------------------------


@pytest.mark.network
async def test_lookup_cik_live(client):
    """edgartools' real ticker→CIK mapping resolves a known US ticker."""
    cik = await client.lookup_cik("AAPL")
    assert cik == "0000320193"
    assert await client.lookup_cik("NOT_A_REAL_TICKER_XYZ") is None


@pytest.mark.network
async def test_get_company_submissions_live(client):
    """edgartools-backed download_json returns raw SEC submissions JSON."""
    subs = await client.get_company_submissions("320193")
    assert subs["cik"] in ("320193", "0000320193")
    assert "10-K" in subs["filings"]["recent"]["form"]


@pytest.mark.network
async def test_get_company_facts_live(client):
    """edgartools-backed download_json returns raw XBRL companyfacts JSON."""
    facts = await client.get_company_facts("320193")
    assert facts["entityName"]
    # raw-shape contract: facts → us-gaap → concept → units → period list
    assert "us-gaap" in facts["facts"]


@pytest.mark.network
async def test_extract_filing_section_real_filing_uses_edgartools_parser(client):
    """The edgartools structured section parser (not the regex fallback)
    extracts MD&A from a real 10-K and respects the 7A boundary."""
    import warnings as _w

    from tools.edgar import Company

    filing = Company("AAPL").get_filings(form="10-K").latest()
    html = filing.html()

    with _w.catch_warnings(record=True) as caught:
        _w.simplefilter("always")
        mda = EdgarClient.extract_filing_section(html, "mda")

    # edgartools parsed it — so no fallback warning should have fired.
    assert not [w for w in caught if "falling back" in str(w.message)]
    assert len(mda) > 1_000
    assert "Management" in mda and "Discussion" in mda
    # MD&A must not bleed into Item 7A.
    assert "Quantitative and Qualitative Disclosures" not in mda


@pytest.mark.network
async def test_fetch_10k_excerpt_live(client):
    """End-to-end: fetch_10k_excerpt pulls real 10-K sections via edgartools."""
    excerpt = await client.fetch_10k_excerpt("AAPL", cik="0000320193")
    assert len(excerpt) > 1_000
    assert "---" in excerpt  # multiple sections joined
