"""FRED (St. Louis Fed) client with daily TTL filesystem cache.

Used by the Macro agent for macro indicators (10Y UST = DGS10, CPI = CPIAUCSL,
Real GDP growth = A191RL1Q225SBEA, etc.). Series are cached per (series_id, limit)
in `cache_dir/_FRED_<series>_<limit>.json`.
"""
import json
import time
from pathlib import Path
from typing import Any

import httpx


BASE_URL = "https://api.stlouisfed.org/fred/series/observations"
DAILY_TTL_SECONDS = 24 * 60 * 60


class FredClient:
    def __init__(self, api_key: str, cache_dir: Path, ttl_seconds: int = DAILY_TTL_SECONDS):
        self.api_key = api_key
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.ttl_seconds = ttl_seconds

    def _cache_path(self, series_id: str, limit: int) -> Path:
        return self.cache_dir / f"_FRED_{series_id}_{limit}.json"

    def _read_cache(self, path: Path) -> Any | None:
        if not path.exists():
            return None
        if (time.time() - path.stat().st_mtime) > self.ttl_seconds:
            return None
        return json.loads(path.read_text())

    async def get_series(self, series_id: str, limit: int = 60) -> list[dict[str, Any]]:
        """Return up to `limit` most recent observations for `series_id`,
        sorted descending by date. Each observation is {date: str, value: float}.
        Observations whose value FRED reports as "." (missing) are skipped."""
        cache_file = self._cache_path(series_id, limit)
        cached = self._read_cache(cache_file)
        if cached is not None:
            return cached

        params = {
            "series_id": series_id,
            "api_key": self.api_key,
            "file_type": "json",
            "limit": limit,
            "sort_order": "desc",
        }
        async with httpx.AsyncClient(timeout=30.0) as http:
            resp = await http.get(BASE_URL, params=params)
            if resp.status_code != 200:
                raise RuntimeError(f"FRED {series_id} failed: {resp.status_code} {resp.text}")
            raw = resp.json().get("observations", [])

        out: list[dict[str, Any]] = []
        for o in raw:
            v = o.get("value")
            if v in (None, "", "."):
                continue
            out.append({"date": o["date"], "value": float(v)})
        cache_file.write_text(json.dumps(out))
        return out
