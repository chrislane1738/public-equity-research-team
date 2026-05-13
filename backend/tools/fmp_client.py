"""FMP HTTP client with daily TTL filesystem cache."""
import json
import time
from pathlib import Path
from typing import Any

import httpx


# FMP migrated off /api/v3 on 2025-08-31; /stable/ is the current path.
# Ticker is now a query param (?symbol=NVDA) instead of a path segment.
BASE_URL = "https://financialmodelingprep.com/stable"
DAILY_TTL_SECONDS = 24 * 60 * 60


class FmpClient:
    def __init__(self, api_key: str, cache_dir: Path, ttl_seconds: int = DAILY_TTL_SECONDS):
        self.api_key = api_key
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.ttl_seconds = ttl_seconds

    def _cache_path(self, endpoint: str, ticker: str) -> Path:
        return self.cache_dir / f"{ticker.upper()}_{endpoint}.json"

    def _read_cache(self, path: Path) -> Any | None:
        if not path.exists():
            return None
        age = time.time() - path.stat().st_mtime
        if age > self.ttl_seconds:
            return None
        return json.loads(path.read_text())

    async def _get(self, endpoint: str, ticker: str) -> Any:
        cache_file = self._cache_path(endpoint, ticker)
        cached = self._read_cache(cache_file)
        if cached is not None:
            return cached

        url = f"{BASE_URL}/{endpoint}"
        async with httpx.AsyncClient(timeout=30.0) as http:
            resp = await http.get(url, params={"symbol": ticker.upper(), "apikey": self.api_key})
            if resp.status_code != 200:
                raise RuntimeError(f"FMP {endpoint} failed: {resp.status_code} {resp.text}")
            data = resp.json()
            cache_file.write_text(json.dumps(data))
            return data

    async def get_financials(self, ticker: str) -> dict[str, Any]:
        return {
            "income": await self._get("income-statement", ticker),
            "balance": await self._get("balance-sheet-statement", ticker),
            "cash": await self._get("cash-flow-statement", ticker),
        }
