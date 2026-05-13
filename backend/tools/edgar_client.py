"""SEC EDGAR client + 10-K section extractor.

Extracts only Item 1 (Business), Item 1A (Risk Factors), and Item 7 (MD&A).
"""
import re
import warnings
from typing import Optional

import httpx
from bs4 import BeautifulSoup


KEEP_ITEMS = [
    ("Item 1.", "Item 1A."),     # Business → up to Risk Factors
    ("Item 1A.", "Item 1B."),    # Risk Factors → up to Unresolved
    ("Item 7.", "Item 7A."),     # MD&A → up to Market Risk
]


class EdgarClient:
    BASE = "https://data.sec.gov"

    def __init__(self, user_agent: str):
        # SEC requires a contact-info User-Agent. Default headers reused per request.
        self.headers = {"User-Agent": user_agent, "Accept": "application/json"}

    async def fetch_10k_excerpt(self, ticker: str, cik: str) -> str:
        cik_padded = cik.zfill(10)
        async with httpx.AsyncClient(timeout=30.0, headers=self.headers) as http:
            submissions = await self._fetch_submissions(http, cik_padded)
            doc_url = self._latest_10k_url(submissions, cik_padded)
            resp = await http.get(doc_url)
            resp.raise_for_status()
            return self._extract_sections(resp.text)

    async def _fetch_submissions(self, http: httpx.AsyncClient, cik_padded: str) -> dict:
        url = f"{self.BASE}/submissions/CIK{cik_padded}.json"
        resp = await http.get(url)
        resp.raise_for_status()
        return resp.json()

    @staticmethod
    def _latest_10k_url(submissions: dict, cik_padded: str) -> str:
        recent = submissions["filings"]["recent"]
        for i, form in enumerate(recent["form"]):
            if form == "10-K":
                accession = recent["accessionNumber"][i].replace("-", "")
                doc = recent["primaryDocument"][i]
                cik_int = str(int(cik_padded))
                return f"https://www.sec.gov/Archives/edgar/data/{cik_int}/{accession}/{doc}"
        raise RuntimeError("No 10-K found in recent filings")

    @staticmethod
    def _extract_sections(html: str) -> str:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            soup = BeautifulSoup(html, "lxml")
        text = soup.get_text("\n")
        kept_chunks: list[str] = []
        for start_marker, end_marker in KEEP_ITEMS:
            chunk = EdgarClient._slice_between(text, start_marker, end_marker)
            if chunk:
                kept_chunks.append(chunk.strip())
        return "\n\n---\n\n".join(kept_chunks)

    @staticmethod
    def _slice_between(text: str, start: str, end: str) -> Optional[str]:
        pat = re.compile(
            re.escape(start) + r"(.*?)" + re.escape(end), re.DOTALL | re.IGNORECASE
        )
        m = pat.search(text)
        if not m:
            return None
        return start + m.group(1)
