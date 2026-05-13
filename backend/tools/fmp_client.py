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
