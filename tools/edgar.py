"""SEC EDGAR client + filing section extractor.

Backed by the ``edgartools`` library (https://github.com/dgunning/edgartools)
for all SEC HTTP access — edgartools manages rate-limiting, the contact-info
identity SEC requires, retries, and a throttle cache internally. The legacy
hand-rolled regex section extractor is retained as a fallback for filings that
edgartools' structured parser cannot handle, and the pypdf-based PDF path is
kept unchanged (edgartools does not parse PDFs).

Public methods
--------------
lookup_cik              — resolve ticker → 10-digit CIK via SEC's official mapping
fetch_10k_excerpt       — fetch latest 10-K and return key sections
get_company_submissions — fetch submissions JSON for a CIK
get_company_facts       — fetch XBRL companyfacts JSON for a CIK
list_filings            — convenience wrapper; returns filtered filing list
download_filing_document — download a single filing document to disk
extract_filing_section  — parse Item sections from a 10-K/10-Q HTML string
extract_filing_section_pdf — same but for PDF-format filings (pypdf-based)
extract_filing_section_auto — auto-dispatch by file extension (.htm/.html/.pdf)
get_insider_transactions — Form 4 insider buy/sell transactions + aggregate
get_institutional_holdings — latest 13F-HR holdings for a filer + QoQ delta
get_activist_stakes     — Schedule 13D/13G large-ownership stakes for a company
get_segment_facts       — segment-level XBRL facts (revenue/op-income by segment)
"""
import asyncio
import html as _html
import json
import math
import re
import time
import warnings
from pathlib import Path
from typing import Any, Optional

from bs4 import BeautifulSoup

# edgartools — synchronous SEC client. Imported at module load so set_identity()
# can be wired exactly once (see _ensure_identity below).
from edgar import Company, get_identity, set_identity
from edgar.httprequests import download_file, download_json


def _normalize_item_markers(text: str) -> str:
    """Normalize legacy 10-K/10-Q section markers so the standard regex matches.

    Handles three edge cases observed in legacy filers:
    1. HTML entities still present (&#167; → §, &nbsp; → \\xa0, etc.).
    2. Non-standard whitespace inside markers (Item\\xa07. or Item\\u202f7.).
    3. § used in place of "Item" (e.g., "§ 7. Management's Discussion").
    """
    text = _html.unescape(text)
    text = re.sub(r"[\xa0   ]", " ", text)
    text = re.sub(r"§\s*(\d+[A-Z]?)\.?", r"Item \1.", text)
    return text


DAILY_TTL_SECONDS = 24 * 60 * 60

# Section markers: maps section_id → (start patterns, stop-at-any-of patterns)
# Each pattern set is tried with a case-insensitive regex.
_SECTION_MARKERS: dict[str, tuple[list[str], list[str]]] = {
    "business":          (["Item\\s+1\\.(?!A)"],       ["Item\\s+1A\\.", "Item\\s+2\\."]),
    "risk_factors":      (["Item\\s+1A\\."],             ["Item\\s+1B\\.", "Item\\s+2\\."]),
    "properties":        (["Item\\s+2\\."],              ["Item\\s+3\\."]),
    "legal_proceedings": (["Item\\s+3\\."],              ["Item\\s+4\\."]),
    "mda":               (["Item\\s+7\\.(?!A)"],         ["Item\\s+7A\\.", "Item\\s+8\\."]),
    "financial_statements": (["Item\\s+8\\."],           ["Item\\s+9\\."]),
}

# section_id → the SEC item number it corresponds to. Used to match against the
# edgartools structured-section keys (e.g. "part_ii_item_7"), which carry an
# unpredictable part prefix that varies per filing.
_SECTION_ITEM_NUMBERS: dict[str, str] = {
    "business":             "1",
    "risk_factors":         "1a",
    "properties":           "2",
    "legal_proceedings":    "3",
    "mda":                  "7",
    "financial_statements": "8",
}

# _SECTION_MARKERS and _SECTION_ITEM_NUMBERS are parallel dicts keyed by
# section_id; a key mismatch would silently break the edgartools/regex
# dispatch, so fail fast at import time if they ever drift apart.
assert _SECTION_MARKERS.keys() == _SECTION_ITEM_NUMBERS.keys(), (
    "_SECTION_MARKERS and _SECTION_ITEM_NUMBERS must have identical keys; "
    f"mismatch: {_SECTION_MARKERS.keys() ^ _SECTION_ITEM_NUMBERS.keys()}"
)

_MAX_SECTION_CHARS = 50_000


class EdgarClient:
    BASE_DATA = "https://data.sec.gov"
    BASE_ARCHIVES = "https://www.sec.gov/Archives/edgar/data"

    def __init__(self, user_agent: str, cache_dir: Optional[Path] = None):
        # SEC requires a contact-info User-Agent / identity. edgartools wants
        # the same thing via set_identity(); reuse the user_agent verbatim.
        self.user_agent = user_agent
        self.headers = {"User-Agent": user_agent, "Accept": "application/json"}
        _ensure_identity(user_agent)
        if cache_dir is None:
            from tools.settings import CACHE_DIR
            cache_dir = CACHE_DIR
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Cache helpers (same pattern as FredClient / FmpClient)
    # ------------------------------------------------------------------

    def _cache_path(self, key: str) -> Path:
        safe = re.sub(r"[^A-Za-z0-9_\-]", "_", key)
        return self.cache_dir / f"_EDGAR_{safe}.json"

    def _read_cache(self, path: Path) -> Any | None:
        if not path.exists():
            return None
        if (time.time() - path.stat().st_mtime) > DAILY_TTL_SECONDS:
            return None
        return json.loads(path.read_text())

    def _write_cache(self, path: Path, data: Any) -> None:
        path.write_text(json.dumps(data))

    # ------------------------------------------------------------------
    # Ticker → CIK lookup
    # ------------------------------------------------------------------

    async def lookup_cik(self, ticker: str) -> Optional[str]:
        """Resolve a US-listed ticker to its 10-digit zero-padded SEC CIK.

        Uses SEC's official ticker→CIK mapping (fetched via edgartools'
        ``get_company_tickers``). Returns None for tickers not present in the
        mapping (typically foreign-listed companies without US ADRs) — that
        None is the signal for accountant fallback to FMP-only mode.

        The mapping is cached on disk for 24h as a {ticker: cik_int} dict.
        """
        cache_file = self._cache_path("company_tickers")
        mapping = self._read_cache(cache_file)
        if mapping is None:
            mapping = await asyncio.to_thread(self._load_ticker_mapping)
            self._write_cache(cache_file, mapping)

        cik_int = mapping.get(ticker.upper())
        if cik_int is None:
            return None
        return f"{int(cik_int):010d}"

    @staticmethod
    def _load_ticker_mapping() -> dict[str, int]:
        """Build a {TICKER: cik_int} dict from edgartools' company-tickers data."""
        from edgar import get_company_tickers

        df = get_company_tickers(as_dataframe=True)
        mapping: dict[str, int] = {}
        for ticker, cik in zip(df["ticker"], df["cik"]):
            if ticker:
                mapping[str(ticker).upper()] = int(cik)
        return mapping

    # ------------------------------------------------------------------
    # 2.1 — Submissions
    # ------------------------------------------------------------------

    async def get_company_submissions(self, cik: str) -> dict:
        """Return the SEC submissions JSON for a CIK (zero-padded to 10 digits)."""
        cik_padded = cik.zfill(10)
        cache_file = self._cache_path(f"submissions_{cik_padded}")
        cached = self._read_cache(cache_file)
        if cached is not None:
            return cached
        url = f"{self.BASE_DATA}/submissions/CIK{cik_padded}.json"
        data = await asyncio.to_thread(download_json, url)
        self._write_cache(cache_file, data)
        return data

    # ------------------------------------------------------------------
    # 2.2 — Company facts (XBRL)
    # ------------------------------------------------------------------

    async def get_company_facts(self, cik: str) -> dict:
        """Return the XBRL companyfacts JSON for a CIK."""
        cik_padded = cik.zfill(10)
        cache_file = self._cache_path(f"companyfacts_{cik_padded}")
        cached = self._read_cache(cache_file)
        if cached is not None:
            return cached
        url = f"{self.BASE_DATA}/api/xbrl/companyfacts/CIK{cik_padded}.json"
        data = await asyncio.to_thread(download_json, url)
        self._write_cache(cache_file, data)
        return data

    # ------------------------------------------------------------------
    # 2.3 — List filings (convenience wrapper)
    # ------------------------------------------------------------------

    async def list_filings(
        self,
        cik: str,
        form_types: list[str] | None = None,
        limit: int = 10,
    ) -> list[dict]:
        """Return recent filings, optionally filtered by form type, capped at limit."""
        submissions = await self.get_company_submissions(cik)
        recent = submissions["filings"]["recent"]

        forms        = recent.get("form", [])
        accessions   = recent.get("accessionNumber", [])
        filing_dates = recent.get("filingDate", [])
        report_dates = recent.get("reportDate", [])
        primary_docs = recent.get("primaryDocument", [])
        descriptions = recent.get("primaryDocDescription", [])

        results: list[dict] = []
        for i, form in enumerate(forms):
            if form_types is not None and form not in form_types:
                continue
            results.append({
                "accession_number":  accessions[i]   if i < len(accessions)   else "",
                "form":              form,
                "filing_date":       filing_dates[i]  if i < len(filing_dates) else "",
                "report_date":       report_dates[i]  if i < len(report_dates) else "",
                "primary_document":  primary_docs[i]  if i < len(primary_docs) else "",
                "description":       descriptions[i]  if i < len(descriptions) else "",
            })
            if len(results) >= limit:
                break
        return results

    # ------------------------------------------------------------------
    # 2.4 — Download a filing document to disk
    # ------------------------------------------------------------------

    async def download_filing_document(
        self,
        cik: str,
        accession_number: str,
        primary_document: str,
        output_path: Path,
    ) -> Path:
        """Download a filing document and write it to output_path.

        accession_number may include dashes (e.g. '0001045810-24-000029'); they
        are stripped for the URL path. The download goes through edgartools'
        managed HTTP layer (rate-limited, identity-aware).
        """
        cik_int = str(int(cik.lstrip("0") or "0"))
        accession_no_dashes = accession_number.replace("-", "")
        url = f"{self.BASE_ARCHIVES}/{cik_int}/{accession_no_dashes}/{primary_document}"

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        content = await asyncio.to_thread(download_file, url, as_text=False)
        if isinstance(content, str):
            output_path.write_text(content)
        else:
            output_path.write_bytes(content)
        return output_path

    # ------------------------------------------------------------------
    # 2.5 — Extract a named section from 10-K/10-Q HTML
    # ------------------------------------------------------------------

    @staticmethod
    def extract_filing_section(filing_html: str, section_id: str) -> str:
        """Extract a named section from 10-K/10-Q HTML.

        section_id must be one of: business, risk_factors, mda,
        financial_statements, properties, legal_proceedings.

        Tries edgartools' structured HTML section parser first; if that parser
        is unavailable, errors, or returns empty for the given filing, falls
        back to the legacy regex/BeautifulSoup extractor (a ``warnings.warn``
        is emitted so divergences stay visible).

        Returns plain text (HTML tags stripped), capped at 50 000 chars.
        """
        if section_id not in _SECTION_MARKERS:
            raise ValueError(
                f"Unknown section_id {section_id!r}. "
                f"Valid: {list(_SECTION_MARKERS)}"
            )

        parsed = _extract_section_via_edgartools(filing_html, section_id)
        if parsed:
            return parsed[:_MAX_SECTION_CHARS]

        warnings.warn(
            f"edgartools section parser returned no content for "
            f"section_id={section_id!r}; falling back to regex extractor.",
            stacklevel=2,
        )
        return EdgarClient._extract_filing_section_regex(filing_html, section_id)

    @staticmethod
    def _extract_filing_section_regex(filing_html: str, section_id: str) -> str:
        """Legacy regex/BeautifulSoup section extractor (fallback path)."""
        start_patterns, stop_patterns = _SECTION_MARKERS[section_id]

        # Normalize legacy markers (HTML entities, nbsp, § notation) before parsing.
        filing_html = _normalize_item_markers(filing_html)

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            soup = BeautifulSoup(filing_html, "lxml")

        # Collect all candidate heading elements
        candidate_tags = soup.find_all(["h1", "h2", "h3", "b", "span", "p"])

        def _text_of(tag) -> str:
            return tag.get_text(" ", strip=True)

        def _matches_any(text: str, patterns: list[str]) -> bool:
            for pat in patterns:
                if re.search(pat, text, re.IGNORECASE):
                    return True
            return False

        # Find the index of the first element that matches a start pattern
        start_idx = None
        for idx, tag in enumerate(candidate_tags):
            txt = _text_of(tag)
            if _matches_any(txt, start_patterns):
                start_idx = idx
                break

        if start_idx is None:
            return ""

        # Collect text until we hit a stop pattern
        collected: list[str] = []
        for tag in candidate_tags[start_idx:]:
            txt = _text_of(tag)
            if tag is not candidate_tags[start_idx] and _matches_any(txt, stop_patterns):
                break
            # Use the tag's get_text with newline separator for paragraph breaks
            para = tag.get_text("\n", strip=True)
            if para:
                collected.append(para)

        result = "\n\n".join(collected)
        return result[:_MAX_SECTION_CHARS]

    # ------------------------------------------------------------------
    # 2.6 — PDF section extractor (for native-PDF 10-K filings)
    # ------------------------------------------------------------------

    @staticmethod
    def extract_filing_section_pdf(pdf_path: Path, section_id: str) -> str:
        """Extract a named section from a PDF-format 10-K/10-Q filing.

        Same section_id values as extract_filing_section. Uses pypdf to pull
        plain text from every page, normalizes legacy item markers, then runs
        the same start/stop pattern matching as the HTML extractor.

        edgartools does not parse PDFs, so this path is intentionally
        unchanged. Useful for foreign private issuers and amendments filed
        as PDF.
        """
        if section_id not in _SECTION_MARKERS:
            raise ValueError(
                f"Unknown section_id {section_id!r}. "
                f"Valid: {list(_SECTION_MARKERS)}"
            )
        start_patterns, stop_patterns = _SECTION_MARKERS[section_id]

        import pypdf
        reader = pypdf.PdfReader(str(pdf_path))
        full_text = "\n".join(page.extract_text() or "" for page in reader.pages)
        full_text = _normalize_item_markers(full_text)

        # Split into lines; treat each line as a candidate heading.
        lines = full_text.splitlines()

        def _matches_any(text: str, patterns: list[str]) -> bool:
            for pat in patterns:
                if re.search(pat, text, re.IGNORECASE):
                    return True
            return False

        start_idx = None
        for idx, line in enumerate(lines):
            if _matches_any(line, start_patterns):
                start_idx = idx
                break
        if start_idx is None:
            return ""

        collected: list[str] = []
        for line in lines[start_idx:]:
            if line is not lines[start_idx] and _matches_any(line, stop_patterns):
                break
            if line.strip():
                collected.append(line)

        result = "\n".join(collected)
        return result[:_MAX_SECTION_CHARS]

    # ------------------------------------------------------------------
    # 2.7 — Auto-dispatcher (HTML vs PDF by file extension)
    # ------------------------------------------------------------------

    @staticmethod
    def extract_filing_section_auto(filing_path: Path, section_id: str) -> str:
        """Extract a section from a filing on disk; auto-dispatches by extension.

        Supports .htm, .html (→ extract_filing_section) and .pdf
        (→ extract_filing_section_pdf). Raises ValueError for any other suffix.
        """
        filing_path = Path(filing_path)
        suffix = filing_path.suffix.lower()
        if suffix in (".htm", ".html"):
            return EdgarClient.extract_filing_section(
                filing_path.read_text(errors="ignore"), section_id
            )
        if suffix == ".pdf":
            return EdgarClient.extract_filing_section_pdf(filing_path, section_id)
        raise ValueError(
            f"Unsupported filing format: {suffix!r}. "
            f"Supported: .htm, .html, .pdf"
        )

    # ------------------------------------------------------------------
    # Existing public API — fetch_10k_excerpt
    # ------------------------------------------------------------------

    async def fetch_10k_excerpt(self, ticker: str, cik: str) -> str:
        """Fetch the latest 10-K for ticker/cik and return key sections.

        Returns Business, Risk Factors, and MD&A sections separated by ---
        delimiters. Uses edgartools' structured 10-K parser
        (Company.latest_tenk) to pull each section; falls back to fetching the
        raw 10-K HTML and running extract_filing_section if the structured
        parser yields nothing.
        """
        wanted = ["business", "risk_factors", "mda"]

        chunks = await asyncio.to_thread(self._fetch_10k_sections_edgartools, ticker, cik, wanted)
        if chunks:
            return "\n\n---\n\n".join(chunks)

        # Fallback: raw HTML + legacy section extractor.
        warnings.warn(
            f"edgartools 10-K parser yielded no sections for {ticker!r}; "
            f"falling back to raw-HTML extraction.",
            stacklevel=2,
        )
        html = await asyncio.to_thread(self._fetch_latest_10k_html, ticker, cik)
        fallback_chunks: list[str] = []
        for section_id in wanted:
            section_text = self.extract_filing_section(html, section_id)
            if section_text:
                fallback_chunks.append(section_text.strip())
        return "\n\n---\n\n".join(fallback_chunks)

    # ------------------------------------------------------------------
    # 2.8 — Insider transactions (Form 4)
    # ------------------------------------------------------------------

    async def get_insider_transactions(
        self,
        ticker: str,
        cik: str,
        recent_filings: int = 40,
    ) -> dict:
        """Return Form 4 insider buy/sell transactions for a company.

        Pulls the ``recent_filings`` most-recent Form 4 filings for the
        company (via edgartools' ``Company.get_filings(form="4")``), parses
        each into an edgartools ``Form4`` object, and flattens every
        non-derivative transaction line into a structured record.

        Args:
            ticker: company ticker (preferred edgartools identifier).
            cik:    zero-padded or bare CIK (used as fallback identifier).
            recent_filings: how many of the most-recent Form 4 filings to
                read. Default 40 — roughly a quarter of insider activity for
                an actively-traded large cap. Form 4 filings are numerous so
                this is bounded by a filing count, not a date window.

        Returns a JSON-serializable dict::

            {
              "ticker": "NVDA",
              "filings_scanned": 40,
              "transactions": [
                {
                  "insider": "Huang Jen-Hsun",
                  "relationship": "Director / Officer (President & CEO)",
                  "transaction_date": "2024-06-13",
                  "code": "S",                # SEC transaction code
                  "code_description": "Open market or private sale",
                  "acquired_disposed": "D",   # "A" acquired / "D" disposed
                  "shares": 120000.0,
                  "price": 130.45,
                  "resulting_holding": 8593e3, # shares held after the trade
                  "security": "Common Stock",
                  "accession_number": "0001045810-24-000077"
                },
                ...
              ],
              "aggregate": {
                "net_shares": -240000.0,      # shares acquired minus disposed
                "shares_bought": 0.0,
                "shares_sold": 240000.0,
                "distinct_insiders": 5,
                "transaction_count": 12,
                "window_start": "2024-03-01", # earliest transaction date
                "window_end": "2024-06-13"    # latest transaction date
              }
            }

        ``net_shares``/``shares_bought``/``shares_sold`` are summed across all
        non-derivative transaction lines regardless of code (A vs D), giving a
        true net-position change. The result is cached on disk for 24h.
        """
        cik_padded = cik.zfill(10)
        cache_file = self._cache_path(
            f"insider_{cik_padded}_{recent_filings}"
        )
        cached = self._read_cache(cache_file)
        if cached is not None:
            return cached

        data = await asyncio.to_thread(
            self._fetch_insider_transactions, ticker, cik, recent_filings
        )
        self._write_cache(cache_file, data)
        return data

    def _fetch_insider_transactions(
        self, ticker: str, cik: str, recent_filings: int
    ) -> dict:
        """Sync worker for get_insider_transactions (runs in a thread)."""
        from edgar.ownership import TransactionCode

        company = EdgarClient._resolve_company(ticker, cik)
        transactions: list[dict] = []
        scanned = 0

        if company is not None:
            try:
                filings = company.get_filings(form="4").latest(recent_filings)
            except Exception as exc:
                warnings.warn(
                    f"edgartools Company.get_filings(form='4') failed for "
                    f"{ticker!r} ({type(exc).__name__}: {exc}).",
                    stacklevel=2,
                )
                filings = None

            if filings is not None:
                # .latest(n) may return a single Filing or a Filings container.
                filing_iter = filings if hasattr(filings, "__iter__") else [filings]
                for filing in filing_iter:
                    scanned += 1
                    try:
                        form4 = filing.obj()
                    except Exception as exc:
                        warnings.warn(
                            f"edgartools failed to parse Form 4 "
                            f"{getattr(filing, 'accession_no', '?')!r} "
                            f"({type(exc).__name__}: {exc}); skipping.",
                            stacklevel=2,
                        )
                        continue
                    if form4 is None:
                        continue
                    transactions.extend(
                        self._flatten_form4(form4, filing, TransactionCode)
                    )

        # Aggregate across every non-derivative transaction line.
        shares_bought = sum(
            t["shares"] for t in transactions
            if t["acquired_disposed"] == "A" and t["shares"] is not None
        )
        shares_sold = sum(
            t["shares"] for t in transactions
            if t["acquired_disposed"] == "D" and t["shares"] is not None
        )
        dates = sorted(t["transaction_date"] for t in transactions if t["transaction_date"])
        insiders = {t["insider"] for t in transactions if t["insider"]}

        return {
            "ticker": ticker.upper(),
            "filings_scanned": scanned,
            "transactions": transactions,
            "aggregate": {
                "net_shares": shares_bought - shares_sold,
                "shares_bought": shares_bought,
                "shares_sold": shares_sold,
                "distinct_insiders": len(insiders),
                "transaction_count": len(transactions),
                "window_start": dates[0] if dates else None,
                "window_end": dates[-1] if dates else None,
            },
        }

    @staticmethod
    def _flatten_form4(form4, filing, transaction_code_cls) -> list[dict]:
        """Flatten one edgartools Form4 object into per-transaction dicts."""
        owners = form4.reporting_owners.owners if form4.reporting_owners else []
        # Insider name + relationship come from the (first) reporting owner.
        if owners:
            owner = owners[0]
            insider = owner.name
            roles = []
            if owner.is_director:
                roles.append("Director")
            if owner.is_officer:
                roles.append("Officer")
            if owner.is_ten_pct_owner:
                roles.append("10% Owner")
            if owner.is_other:
                roles.append("Other")
            relationship = " / ".join(roles) if roles else "Unknown"
            if owner.officer_title:
                relationship = f"{relationship} ({owner.officer_title})"
        else:
            insider = form4.insider_name
            relationship = "Unknown"

        accession = getattr(filing, "accession_no", "")
        ndt = form4.non_derivative_table
        records: list[dict] = []
        if ndt is None or not ndt.has_transactions:
            return records

        for row in ndt.transactions.data.itertuples():
            code = getattr(row, "Code", "") or ""
            shares = _coerce_number(getattr(row, "Shares", None))
            records.append({
                "insider": insider,
                "relationship": relationship,
                "transaction_date": str(getattr(row, "Date", "") or ""),
                "code": code,
                "code_description": transaction_code_cls.DESCRIPTIONS.get(code, code),
                "acquired_disposed": getattr(row, "AcquiredDisposed", "") or "",
                "shares": shares,
                "price": _coerce_number(getattr(row, "Price", None)),
                "resulting_holding": _coerce_number(getattr(row, "Remaining", None)),
                "security": str(getattr(row, "Security", "") or ""),
                "accession_number": accession,
            })
        return records

    # ------------------------------------------------------------------
    # 2.9 — Institutional holdings (13F-HR)
    # ------------------------------------------------------------------

    async def get_institutional_holdings(self, cik: str) -> dict:
        """Return the latest 13F-HR holdings for an institutional filer.

        Interpretation implemented: **"latest 13F-HR holdings for a filer."**
        Given the CIK of an institutional investment manager (e.g. Berkshire
        Hathaway, CIK 1067983), this fetches that manager's most-recent
        13F-HR filing, returns its full holdings table, and — when the prior
        quarter's 13F is available — a quarter-over-quarter delta per security.

        (The alternative interpretation, "which institutions hold company X",
        is not exposed by edgartools as a clean first-class API — it requires
        a full-text 13F scan — so the filer-centric view is implemented.)

        Args:
            cik: CIK of the 13F filer (zero-padded or bare).

        Returns a JSON-serializable dict::

            {
              "filer_cik": "0001067983",
              "manager_name": "Berkshire Hathaway Inc",
              "report_period": "2024-12-31",
              "filing_date": "2025-02-14",
              "total_value": 267000000000,    # USD
              "total_holdings": 38,
              "holdings": [
                {"issuer": "APPLE INC", "ticker": "AAPL",
                 "cusip": "037833100", "shares": 300000000,
                 "value": 75000000000},
                ...
              ],
              "qoq_delta": {                  # null if prior 13F unavailable
                "previous_period": "2024-09-30",
                "changes": [
                  {"issuer": "APPLE INC", "ticker": "AAPL",
                   "cusip": "037833100", "status": "DECREASED",
                   "shares": 300000000, "prev_shares": 400000000,
                   "share_change": -100000000, "value_change": -25000000000},
                  ...
                ]
              }
            }

        Result is cached on disk for 24h.
        """
        cik_padded = cik.zfill(10)
        cache_file = self._cache_path(f"institutional_{cik_padded}")
        cached = self._read_cache(cache_file)
        if cached is not None:
            return cached

        data = await asyncio.to_thread(self._fetch_institutional_holdings, cik)
        self._write_cache(cache_file, data)
        return data

    def _fetch_institutional_holdings(self, cik: str) -> dict:
        """Sync worker for get_institutional_holdings (runs in a thread)."""
        cik_int = int(cik.lstrip("0") or "0")
        result: dict[str, Any] = {
            "filer_cik": cik.zfill(10),
            "manager_name": None,
            "report_period": None,
            "filing_date": None,
            "total_value": None,
            "total_holdings": None,
            "holdings": [],
            "qoq_delta": None,
        }

        try:
            company = Company(cik_int)
            filing = company.get_filings(form="13F-HR").latest()
        except Exception as exc:
            warnings.warn(
                f"edgartools could not load 13F-HR filings for CIK {cik!r} "
                f"({type(exc).__name__}: {exc}).",
                stacklevel=2,
            )
            return result
        if filing is None:
            return result

        thirteenf = filing.obj()
        if thirteenf is None:
            warnings.warn(
                f"edgartools could not parse the latest 13F-HR for CIK "
                f"{cik!r}; returning empty holdings.",
                stacklevel=2,
            )
            return result

        result["manager_name"] = thirteenf.management_company_name
        result["report_period"] = thirteenf.report_period
        result["filing_date"] = thirteenf.filing_date
        total_value = thirteenf.total_value
        result["total_value"] = _coerce_number(total_value)
        result["total_holdings"] = thirteenf.total_holdings
        result["holdings"] = _holdings_records(thirteenf.holdings)

        # Quarter-over-quarter delta vs the prior 13F, when available.
        try:
            comparison = thirteenf.compare_holdings()
        except Exception as exc:
            warnings.warn(
                f"edgartools 13F compare_holdings failed for CIK {cik!r} "
                f"({type(exc).__name__}: {exc}); omitting qoq_delta.",
                stacklevel=2,
            )
            comparison = None

        if comparison is not None:
            changes: list[dict] = []
            for row in comparison.data.itertuples():
                changes.append({
                    "issuer": str(getattr(row, "Issuer", "") or ""),
                    "ticker": str(getattr(row, "Ticker", "") or ""),
                    "cusip": str(getattr(row, "Cusip", "") or ""),
                    "status": str(getattr(row, "Status", "") or ""),
                    "shares": _coerce_number(getattr(row, "Shares", None)),
                    "prev_shares": _coerce_number(getattr(row, "PrevShares", None)),
                    "share_change": _coerce_number(getattr(row, "ShareChange", None)),
                    "value_change": _coerce_number(getattr(row, "ValueChange", None)),
                })
            result["qoq_delta"] = {
                "previous_period": comparison.previous_period,
                "changes": changes,
            }
        return result

    # ------------------------------------------------------------------
    # 2.10 — Activist / large-ownership stakes (Schedule 13D / 13G)
    # ------------------------------------------------------------------

    async def get_activist_stakes(
        self,
        cik: str,
        limit: int = 20,
    ) -> dict:
        """Return Schedule 13D / 13G large-ownership stakes for a company.

        A Schedule 13D or 13G is filed when an investor crosses 5% beneficial
        ownership of a company's stock. **13D signals an active/activist
        stake** (control intent); **13G signals a passive stake** (typically
        index funds and long-only institutions). This method pulls the most
        recent 13D/13G filings *against the company* and flattens each into a
        per-filer record, tagging the active-vs-passive distinction.

        Note: the SEC mandated structured-XML 13D/13G filings only from late
        2024 — older filings cannot be machine-parsed by edgartools and are
        skipped (with a warning), so this method is most useful for recent
        ownership activity.

        Args:
            cik:   CIK of the *subject company* (zero-padded or bare).
            limit: max number of recent 13D/13G filings to read (default 20).

        Returns a JSON-serializable dict::

            {
              "company_cik": "0000320193",
              "filings_scanned": 20,
              "stakes": [
                {
                  "filer": "BERKSHIRE HATHAWAY INC",
                  "filing_date": "2025-02-14",
                  "form_type": "SCHEDULE 13G",
                  "stake_type": "passive",      # "active" (13D) / "passive" (13G)
                  "is_amendment": false,
                  "percent_of_class": 5.4,      # max across joint filers
                  "shares": 915000000,          # aggregate beneficial shares
                  "accession_number": "0001067983-25-000001"
                },
                ...
              ]
            }

        Result is cached on disk for 24h.
        """
        cik_padded = cik.zfill(10)
        cache_file = self._cache_path(f"activist_{cik_padded}_{limit}")
        cached = self._read_cache(cache_file)
        if cached is not None:
            return cached

        data = await asyncio.to_thread(
            self._fetch_activist_stakes, cik, limit
        )
        self._write_cache(cache_file, data)
        return data

    def _fetch_activist_stakes(self, cik: str, limit: int) -> dict:
        """Sync worker for get_activist_stakes (runs in a thread)."""
        cik_int = int(cik.lstrip("0") or "0")
        result: dict[str, Any] = {
            "company_cik": cik.zfill(10),
            "filings_scanned": 0,
            "stakes": [],
        }

        # SEC form labels for the four Schedule 13D/13G variants. edgartools
        # uses the long "SCHEDULE 13x" spelling (the structured-XML era form).
        forms = ["SCHEDULE 13D", "SCHEDULE 13D/A",
                 "SCHEDULE 13G", "SCHEDULE 13G/A"]
        try:
            company = Company(cik_int)
            filings = company.get_filings(form=forms).latest(limit)
        except Exception as exc:
            warnings.warn(
                f"edgartools could not load 13D/13G filings for CIK {cik!r} "
                f"({type(exc).__name__}: {exc}).",
                stacklevel=2,
            )
            return result
        if filings is None:
            return result

        filing_iter = filings if hasattr(filings, "__iter__") else [filings]
        stakes: list[dict] = []
        for filing in filing_iter:
            result["filings_scanned"] += 1
            try:
                schedule = filing.obj()
            except Exception as exc:
                warnings.warn(
                    f"edgartools failed to parse 13D/13G "
                    f"{getattr(filing, 'accession_no', '?')!r} "
                    f"({type(exc).__name__}: {exc}); skipping.",
                    stacklevel=2,
                )
                continue
            if schedule is None:
                # Pre-XML filing edgartools cannot machine-parse — skip quietly.
                continue

            form_type = str(getattr(filing, "form", "") or "")
            is_13d = "13D" in form_type.upper()
            persons = getattr(schedule, "reporting_persons", None) or []
            filer = persons[0].name if persons else None
            stakes.append({
                "filer": filer,
                "filing_date": str(schedule.filing_date),
                "form_type": form_type,
                "stake_type": "active" if is_13d else "passive",
                "is_amendment": bool(getattr(schedule, "is_amendment", False)),
                "percent_of_class": _coerce_number(schedule.total_percent),
                "shares": _coerce_number(schedule.total_shares),
                "accession_number": getattr(filing, "accession_no", ""),
            })

        result["stakes"] = stakes
        return result

    # ------------------------------------------------------------------
    # 2.11 — Segment-level XBRL facts
    # ------------------------------------------------------------------

    async def get_segment_facts(self, ticker: str, cik: str) -> dict:
        """Return segment-level XBRL facts from the latest 10-K.

        Uses edgartools' dimensional-XBRL support: parses the latest 10-K's
        XBRL, then queries facts tagged against the reportable-segments axis
        (``us-gaap:StatementBusinessSegmentsAxis``). Each fact carries the
        segment name (the dimension member) so revenue / operating income /
        etc. can be read per reportable segment, per period.

        This feeds a downstream quantitative segment-reorg check (does the set
        of reportable segments change between filings?).

        Args:
            ticker: company ticker (preferred edgartools identifier).
            cik:    zero-padded or bare CIK (fallback identifier).

        Returns a JSON-serializable dict::

            {
              "ticker": "AAPL",
              "segment_axis": "us-gaap:StatementBusinessSegmentsAxis",
              "segments": ["Americas", "Europe", "Greater China", ...],
              "facts": [
                {
                  "segment": "Americas",
                  "concept": "us-gaap:RevenueFromContractWithCustomer...",
                  "label": "Americas",
                  "value": 167045000000.0,
                  "period_start": "2023-10-01",
                  "period_end": "2024-09-28"
                },
                ...
              ]
            }

        Result is cached on disk for 24h.
        """
        cik_padded = cik.zfill(10)
        cache_file = self._cache_path(f"segments_{cik_padded}")
        cached = self._read_cache(cache_file)
        if cached is not None:
            return cached

        data = await asyncio.to_thread(self._fetch_segment_facts, ticker, cik)
        self._write_cache(cache_file, data)
        return data

    _SEGMENT_AXIS = "us-gaap:StatementBusinessSegmentsAxis"

    def _fetch_segment_facts(self, ticker: str, cik: str) -> dict:
        """Sync worker for get_segment_facts (runs in a thread)."""
        result: dict[str, Any] = {
            "ticker": ticker.upper(),
            "segment_axis": self._SEGMENT_AXIS,
            "segments": [],
            "facts": [],
        }

        tenk_filing = self._latest_10k_filing(ticker, cik)
        if tenk_filing is None:
            return result

        from edgar.xbrl import XBRL

        try:
            xbrl = XBRL.from_filing(tenk_filing)
        except Exception as exc:
            warnings.warn(
                f"edgartools XBRL.from_filing failed for {ticker!r} "
                f"({type(exc).__name__}: {exc}); no segment facts.",
                stacklevel=2,
            )
            return result
        if xbrl is None:
            return result

        try:
            df = (
                xbrl.query()
                .by_dimension("StatementBusinessSegmentsAxis")
                .to_dataframe()
            )
        except Exception as exc:
            warnings.warn(
                f"edgartools dimensional XBRL query failed for {ticker!r} "
                f"({type(exc).__name__}: {exc}); no segment facts.",
                stacklevel=2,
            )
            return result

        if df is None or len(df) == 0:
            return result

        # The segment name is the dimension member; edgartools resolves a
        # human-readable label into 'dimension_member_label' (preferred), with
        # 'member' as the raw fallback.
        seg_col = (
            "dimension_member_label"
            if "dimension_member_label" in df.columns
            else "member"
        )
        facts: list[dict] = []
        for row in df.itertuples():
            segment = getattr(row, seg_col, None) if seg_col else None
            facts.append({
                "segment": str(segment) if segment else "",
                "concept": str(getattr(row, "concept", "") or ""),
                "label": str(getattr(row, "label", "") or ""),
                "value": _coerce_number(getattr(row, "value", None)),
                "period_start": str(getattr(row, "period_start", "") or ""),
                "period_end": str(getattr(row, "period_end", "") or ""),
            })

        result["facts"] = facts
        # Distinct segments, preserving first-seen order.
        seen: list[str] = []
        for f in facts:
            if f["segment"] and f["segment"] not in seen:
                seen.append(f["segment"])
        result["segments"] = seen
        return result

    @staticmethod
    def _latest_10k_filing(ticker: str, cik: str):
        """Resolve the latest 10-K as an edgartools Filing object, or None."""
        company = EdgarClient._resolve_company(ticker, cik)
        if company is None:
            return None
        try:
            return company.get_filings(form="10-K").latest()
        except Exception as exc:
            warnings.warn(
                f"edgartools Company.get_filings(form='10-K') failed for "
                f"{ticker!r} ({type(exc).__name__}: {exc}).",
                stacklevel=2,
            )
            return None

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _fetch_10k_sections_edgartools(
        self, ticker: str, cik: str, wanted: list[str]
    ) -> list[str]:
        """Pull 10-K sections via edgartools' structured TenK parser (sync)."""
        tenk = self._latest_tenk(ticker, cik)
        if tenk is None:
            return []
        # edgartools TenK exposes friendly properties for the common sections.
        attr_map = {
            "business":      "business",
            "risk_factors":  "risk_factors",
            "mda":           "management_discussion",
        }
        chunks: list[str] = []
        for section_id in wanted:
            text = ""
            attr = attr_map.get(section_id)
            if attr is not None:
                try:
                    val = getattr(tenk, attr, None)
                    text = str(val).strip() if val else ""
                except Exception as exc:
                    warnings.warn(
                        f"edgartools TenK.{attr} failed "
                        f"({type(exc).__name__}: {exc}); skipping section "
                        f"{section_id!r}.",
                        stacklevel=2,
                    )
                    text = ""
            if text:
                chunks.append(text[:_MAX_SECTION_CHARS])
        return chunks

    @staticmethod
    def _resolve_company(ticker: str, cik: str):
        """Resolve an edgartools Company, trying ticker then CIK; None on failure."""
        for identifier in (ticker, int(cik.lstrip("0") or "0")):
            try:
                return Company(identifier)
            except Exception:
                continue
        return None

    @staticmethod
    def _latest_tenk(ticker: str, cik: str):
        """Resolve the latest 10-K as an edgartools TenK object, or None."""
        company = EdgarClient._resolve_company(ticker, cik)
        if company is None:
            return None
        try:
            return company.latest_tenk
        except Exception as exc:
            warnings.warn(
                f"edgartools Company.latest_tenk failed "
                f"({type(exc).__name__}: {exc}); falling back to raw-HTML "
                f"extraction.",
                stacklevel=2,
            )
            return None

    def _fetch_latest_10k_html(self, ticker: str, cik: str) -> str:
        """Fetch the raw HTML of the latest 10-K via edgartools (sync)."""
        company = EdgarClient._resolve_company(ticker, cik)
        if company is None:
            raise RuntimeError(
                f"Could not resolve edgartools Company for ticker={ticker!r} "
                f"cik={cik!r}"
            )
        filing = company.get_filings(form="10-K").latest()
        if filing is None:
            raise RuntimeError("No 10-K found in recent filings")
        return filing.html()


# ----------------------------------------------------------------------
# Module-level helpers
# ----------------------------------------------------------------------

def _coerce_number(value: Any) -> Any:
    """Coerce an edgartools/pandas/Decimal scalar to a JSON-safe number.

    edgartools returns a mix of numpy scalars, ``Decimal``, plain ints/floats
    and occasionally strings or NaN. This normalizes anything numeric to a
    plain ``int``/``float`` and maps missing/NaN/None to ``None`` so the
    result survives ``json.dumps`` and reads cleanly for skill subagents.
    """
    if value is None:
        return None
    # pandas / numpy NaN — NaN != NaN is the portable check.
    try:
        if value != value:  # noqa: PLR0124 — NaN sentinel check
            return None
    except (TypeError, ValueError):
        pass
    # Fix 3: numpy.bool_ is not a Python bool subclass — handle it before the
    # int/float branches so it doesn't silently become 1/0.
    try:
        import numpy as _np  # noqa: PLC0415 — lazy import, numpy may be absent
        if isinstance(value, _np.bool_):
            return bool(value)
    except ImportError:
        pass
    # Fix 1: Use exact type checks so numpy scalars (subclasses of int/float)
    # fall through to explicit coercion below rather than being returned raw.
    if type(value) is bool:  # noqa: E721
        return value
    if type(value) is int:  # noqa: E721
        return value
    if type(value) is float:  # noqa: E721
        # Fix 2: plain Python float — still guard against inf/-inf.
        return None if not math.isfinite(value) else value
    # Decimal, numpy scalars, numeric strings.
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    # Fix 2: reject NaN and ±inf — both are non-finite.
    if not math.isfinite(f):
        return None
    return int(f) if f.is_integer() else f


def _holdings_records(holdings) -> list[dict]:
    """Flatten an edgartools 13F holdings DataFrame into JSON-safe records."""
    if holdings is None or len(holdings) == 0:
        return []
    records: list[dict] = []
    for row in holdings.itertuples():
        records.append({
            "issuer": str(getattr(row, "Issuer", "") or ""),
            "ticker": str(getattr(row, "Ticker", "") or ""),
            "cusip": str(getattr(row, "Cusip", "") or ""),
            "shares": _coerce_number(getattr(row, "SharesPrnAmount", None)),
            "value": _coerce_number(getattr(row, "Value", None)),
        })
    return records


def _ensure_identity(user_agent: str) -> None:
    """Wire edgartools' one-time SEC identity from the client's user_agent.

    SEC requires a contact-info string; the legacy client passed it as a
    User-Agent header. edgartools wants the same thing via set_identity().
    Only set it once — repeated calls are harmless but unnecessary.
    """
    try:
        current = get_identity()
    except Exception:
        current = None
    if not current:
        set_identity(user_agent)


def _extract_section_via_edgartools(filing_html: str, section_id: str) -> str:
    """Extract a section from raw 10-K/10-Q HTML using edgartools' parser.

    Returns the section's plain text, or "" if edgartools cannot parse the
    document or locate the requested section. Never raises — any failure is
    caught so the caller can fall back to the regex extractor, but a real
    edgartools breakage is surfaced via ``warnings.warn`` (with the exception
    type) so a permanent degradation to the regex path is never fully silent.
    """
    item_number = _SECTION_ITEM_NUMBERS.get(section_id)
    if item_number is None:
        return ""
    try:
        from edgar.documents import HTMLParser

        doc = HTMLParser().parse(filing_html)
        available = doc.get_available_sec_sections() or []
        # edgartools keys look like "part_ii_item_7" / "part_i_item_1a"; the
        # part prefix varies per filing, so match on the item-number suffix.
        suffix = f"_item_{item_number}"
        matches = [
            key for key in available
            if key.lower().endswith(suffix)
        ]
        if not matches:
            return ""
        text = doc.get_sec_section(matches[0])
        return str(text).strip() if text else ""
    except Exception as exc:
        warnings.warn(
            f"edgartools section parser failed "
            f"({type(exc).__name__}: {exc}); falling back to regex extractor.",
            stacklevel=2,
        )
        return ""
