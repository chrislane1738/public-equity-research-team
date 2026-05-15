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
"""
import asyncio
import html as _html
import json
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
                except Exception:
                    text = ""
            if text:
                chunks.append(text[:_MAX_SECTION_CHARS])
        return chunks

    @staticmethod
    def _latest_tenk(ticker: str, cik: str):
        """Resolve the latest 10-K as an edgartools TenK object, or None."""
        try:
            company = Company(ticker)
        except Exception:
            try:
                company = Company(int(cik.lstrip("0") or "0"))
            except Exception:
                return None
        try:
            return company.latest_tenk
        except Exception:
            return None

    def _fetch_latest_10k_html(self, ticker: str, cik: str) -> str:
        """Fetch the raw HTML of the latest 10-K via edgartools (sync)."""
        try:
            company = Company(ticker)
        except Exception:
            company = Company(int(cik.lstrip("0") or "0"))
        filing = company.get_filings(form="10-K").latest()
        if filing is None:
            raise RuntimeError("No 10-K found in recent filings")
        return filing.html()


# ----------------------------------------------------------------------
# Module-level helpers
# ----------------------------------------------------------------------

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
    swallowed so the caller can fall back to the regex extractor.
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
    except Exception:
        return ""
