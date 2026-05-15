"""FMP HTTP client with daily TTL filesystem cache.

Endpoints use FMP /stable (post-2025-08-31). All paths take ?symbol= as a
query param. Per-call response is cached in `cache_dir/<TICKER>_<endpoint>.json`
with a daily TTL.
"""
import json
import time
from pathlib import Path
from typing import Any

import httpx


BASE_URL = "https://financialmodelingprep.com/stable"
DAILY_TTL_SECONDS = 24 * 60 * 60


class FmpClient:
    def __init__(self, api_key: str, cache_dir: Path, ttl_seconds: int = DAILY_TTL_SECONDS):
        self.api_key = api_key
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.ttl_seconds = ttl_seconds

    # ----- cache helpers -----

    def _cache_path(self, endpoint: str, ticker: str) -> Path:
        slug = endpoint.replace("/", "_")
        return self.cache_dir / f"{ticker.upper()}_{slug}.json"

    def _read_cache(self, path: Path) -> Any | None:
        if not path.exists():
            return None
        if (time.time() - path.stat().st_mtime) > self.ttl_seconds:
            return None
        return json.loads(path.read_text())

    async def _get(self, endpoint: str, ticker: str, extra_params: dict | None = None) -> Any:
        cache_file = self._cache_path(endpoint, ticker)
        cached = self._read_cache(cache_file)
        if cached is not None:
            return cached

        params = {"symbol": ticker.upper(), "apikey": self.api_key}
        if extra_params:
            params.update(extra_params)
        url = f"{BASE_URL}/{endpoint}"
        async with httpx.AsyncClient(timeout=30.0) as http:
            resp = await http.get(url, params=params)
            if resp.status_code != 200:
                raise RuntimeError(f"FMP {endpoint} failed: {resp.status_code} {resp.text}")
            data = resp.json()
            cache_file.write_text(json.dumps(data))
            return data

    # ----- Plan A endpoints -----

    async def get_financials(self, ticker: str) -> dict[str, Any]:
        return {
            "income": await self._get("income-statement", ticker),
            "balance": await self._get("balance-sheet-statement", ticker),
            "cash": await self._get("cash-flow-statement", ticker),
        }

    # ----- Plan B extensions -----

    async def get_profile(self, ticker: str) -> dict[str, Any]:
        rows = await self._get("profile", ticker)
        if not rows:
            raise RuntimeError(f"FMP profile empty for {ticker}")
        return rows[0] if isinstance(rows, list) else rows

    async def get_quote(self, ticker: str) -> dict[str, Any]:
        rows = await self._get("quote", ticker)
        if not rows:
            raise RuntimeError(f"FMP quote empty for {ticker}")
        return rows[0] if isinstance(rows, list) else rows

    async def get_historical_prices(self, ticker: str, days: int = 365) -> list[dict[str, Any]]:
        body = await self._get("historical-price-eod/full", ticker)
        history = body.get("historical", []) if isinstance(body, dict) else body
        return list(history)[:days]

    async def get_peers(self, ticker: str) -> list[str]:
        rows = await self._get("stock-peers", ticker)
        if not rows:
            return []
        rec = rows[0] if isinstance(rows, list) else rows
        peers = rec.get("peers", [])
        return [p for p in peers if p.upper() != ticker.upper()]

    async def get_key_metrics(self, ticker: str) -> list[dict[str, Any]]:
        rows = await self._get("key-metrics", ticker)
        return list(rows) if rows else []

    async def get_ratios(self, ticker: str) -> list[dict[str, Any]]:
        rows = await self._get("ratios", ticker)
        return list(rows) if rows else []

    async def get_estimates(self, ticker: str) -> list[dict[str, Any]]:
        rows = await self._get("analyst-estimates", ticker)
        return list(rows) if rows else []

    async def get_short_interest(self, ticker: str) -> list[dict[str, Any]]:
        """Short-interest history (FINRA bi-monthly settlement cycle).

        FMP exposes short interest via the ``short-interest`` endpoint. The exact
        endpoint name is plan-dependent and may not exist on every FMP tier, so
        this method degrades cleanly: any HTTP error (404, 403, 429, ...) or an
        empty body yields ``[]`` rather than raising, letting the MarketData
        facade fall through to the yfinance fallback. Rows are returned newest
        first, matching FMP's other history endpoints.
        """
        try:
            rows = await self._get("short-interest", ticker)
        except Exception:
            return []
        return list(rows) if rows else []

    async def get_10y_treasury_rate(self) -> float:
        """Return the latest 10-year UST rate as a percent (e.g. 4.25 for 4.25%)."""
        cache_file = self.cache_dir / "_TREASURY_RATES.json"
        cached = self._read_cache(cache_file)
        if cached is None:
            url = f"{BASE_URL}/treasury-rates"
            async with httpx.AsyncClient(timeout=30.0) as http:
                resp = await http.get(url, params={"apikey": self.api_key})
                if resp.status_code != 200:
                    raise RuntimeError(f"FMP treasury-rates failed: {resp.status_code} {resp.text}")
                cached = resp.json()
                cache_file.write_text(json.dumps(cached))
        if not cached:
            raise RuntimeError("FMP treasury-rates empty")
        return float(cached[0]["year10"])

    async def search_symbols(self, query: str, limit: int = 20) -> list[dict[str, Any]]:
        """Live FMP symbol search.

        Returns rows with `{symbol, name, exchange, exchangeFullName, currency, ...}`.
        Cached per-query for 1 hour at `_SEARCH_<QUERY>_<LIMIT>.json` — autocomplete
        results don't need to be real-time, and a cache lets repeated keystrokes
        avoid FMP round-trips.
        """
        q = (query or "").strip().upper()
        if not q:
            return []
        cache_file = self.cache_dir / f"_SEARCH_{q}_{limit}.json"
        # 1-hour TTL for search; bypass the default 24h
        if cache_file.exists() and (time.time() - cache_file.stat().st_mtime) < 3600:
            return json.loads(cache_file.read_text())
        url = f"{BASE_URL}/search-symbol"
        async with httpx.AsyncClient(timeout=30.0) as http:
            resp = await http.get(url, params={
                "query": q, "limit": limit, "apikey": self.api_key,
            })
            if resp.status_code != 200:
                raise RuntimeError(
                    f"FMP search-symbol failed: {resp.status_code} {resp.text}")
            data = resp.json() or []
            cache_file.write_text(json.dumps(data))
            return list(data)


# ---------------------------------------------------------------------------
# Normalization helpers — map FMP response shapes → interface TypedDicts
# ---------------------------------------------------------------------------

from tools.marketdata.interface import (  # noqa: E402
    HistoricalBar, Profile, Quote, ShortInterest, _to_float,
)


def normalize_profile(raw: dict) -> Profile:
    """FMP /stable/profile → Profile shape."""
    if not raw:
        return {}
    if isinstance(raw, list):
        raw = raw[0] if raw else {}
    return {
        "symbol": raw.get("symbol", ""),
        "company_name": raw.get("companyName", ""),
        "industry": raw.get("industry", ""),
        "sector": raw.get("sector", ""),
        "sic_code": str(raw.get("sicCode", "") or ""),
        "market_cap": float(raw.get("marketCap", raw.get("mktCap", 0)) or 0),
        "beta": float(raw.get("beta", 0) or 0),
        "description": raw.get("description", ""),
        "exchange": raw.get("exchange", raw.get("exchangeShortName", "")),
    }


def normalize_quote(raw: dict) -> Quote:
    if isinstance(raw, list):
        raw = raw[0] if raw else {}
    if not raw:
        return {}
    return {
        "symbol": raw.get("symbol", ""),
        "price": float(raw.get("price", 0) or 0),
        "shares_outstanding": float(raw.get("sharesOutstanding", 0) or 0),
        "fifty_two_week_high": float(raw.get("yearHigh", 0) or 0),
        "fifty_two_week_low": float(raw.get("yearLow", 0) or 0),
    }


def normalize_short_interest(rows) -> ShortInterest:
    """FMP /stable/short-interest (list, newest first) → ShortInterest shape.

    FMP returns a history of FINRA bi-monthly settlement records. The first row
    is the current data point; the second (if present) is the prior period.
    Field names vary slightly across FMP tiers, so each is resolved against a
    handful of known aliases. Returns ``{}`` when nothing usable is present.
    """
    if isinstance(rows, dict):
        rows = [rows]
    if not rows:
        return {}

    def _pick(rec: dict, *keys):
        for k in keys:
            if k in rec and rec[k] not in (None, ""):
                return rec[k]
        return None

    cur = rows[0]
    prior = rows[1] if len(rows) > 1 else {}

    shares_short = _to_float(_pick(cur, "shortInterest", "sharesShort", "totalShortInterest"))
    pct_float = _to_float(_pick(cur, "shortPercentOfFloat", "shortInterestRatio", "shortFloatPercent"))
    days_to_cover = _to_float(_pick(cur, "daysToCover", "shortRatio", "daysToCoverShort"))
    if days_to_cover is None:
        avg_vol = _to_float(_pick(cur, "averageVolume", "avgDailyVolume", "volume"))
        if shares_short is not None and avg_vol:
            days_to_cover = shares_short / avg_vol

    # FMP's scale for shortPercentOfFloat is unverified — some tiers return a
    # percentage (21.0 for 21%) while yfinance returns a fraction (0.21).
    # Guard: if the value is >1.0, divide by 100 to normalise to a fraction.
    # A genuine short interest above 100% of float is effectively impossible,
    # so this clamp is safe and keeps both paths on the same 0.0–1.0 contract.
    def _frac(v: float | None) -> float | None:
        if v is not None and v > 1.0:
            return v / 100.0
        return v

    prior_pct_float = _to_float(
        _pick(prior, "shortPercentOfFloat", "shortInterestRatio", "shortFloatPercent"))

    si: ShortInterest = {
        "symbol": str(_pick(cur, "symbol") or "").upper(),
        "shares_short": shares_short,
        "short_percent_of_float": _frac(pct_float),
        "days_to_cover": days_to_cover,
        "as_of_date": str(_pick(cur, "date", "settlementDate", "recordDate") or ""),
        "prior_shares_short": _to_float(
            _pick(prior, "shortInterest", "sharesShort", "totalShortInterest")),
        "prior_short_percent_of_float": _frac(prior_pct_float),
        "prior_as_of_date": str(_pick(prior, "date", "settlementDate", "recordDate") or ""),
        "source": "fmp",
    }
    # Reject a row carrying no actual short-interest signal so the facade
    # can fall through to the yfinance fallback.
    if si["shares_short"] is None and si["short_percent_of_float"] is None:
        return {}
    return si


def normalize_historical(raw) -> list[HistoricalBar]:
    items = raw.get("historical", []) if isinstance(raw, dict) else (raw or [])
    return [
        {
            "date": x.get("date", ""),
            "open": float(x.get("open", 0) or 0),
            "high": float(x.get("high", 0) or 0),
            "low": float(x.get("low", 0) or 0),
            "close": float(x.get("close", 0) or 0),
            "volume": float(x.get("volume", 0) or 0),
        }
        for x in items
    ]
