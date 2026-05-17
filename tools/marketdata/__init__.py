"""MarketData — FMP primary, yfinance fallback. Normalized shapes per interface.py."""
import asyncio
from pathlib import Path
from typing import Any

from tools.marketdata.interface import (
    Estimate, HistoricalBar, KeyMetrics, Profile, Quote, Ratios, ScreenResult,
    ShortInterest,
)


_PERIOD_TO_DAYS = {
    "1mo": 30, "3mo": 90, "6mo": 180,
    "1y": 365, "2y": 730, "3y": 1095, "5y": 1825, "10y": 3650, "max": 7300,
}


class MarketData:
    """Single entry point. Tries FMP first; if empty, falls back to yfinance."""

    def __init__(self, fmp_client: Any = None, yfinance_client: Any = None):
        self.fmp = fmp_client
        self.yfinance = yfinance_client

    @classmethod
    def default(cls) -> "MarketData":
        """Construct with the default FMP + yfinance clients wired up."""
        from tools.marketdata.fmp import FmpClient
        from tools.marketdata.yfinance import YFinanceClient
        from tools.settings import CACHE_DIR, FMP_API_KEY

        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        return cls(
            fmp_client=FmpClient(api_key=FMP_API_KEY, cache_dir=CACHE_DIR),
            yfinance_client=YFinanceClient(),
        )

    def get_profile(self, ticker: str) -> Profile:
        from tools.marketdata.fmp import normalize_profile
        if self.fmp is not None:
            try:
                raw = asyncio.run(self.fmp.get_profile(ticker))
            except Exception:
                raw = None  # FMP error — fall through to yfinance
            # Mocks may already return TypedDict shape; raw FMP responses need normalization.
            result = raw if isinstance(raw, dict) and "company_name" in raw else normalize_profile(raw)
            if result:
                return result
        if self.yfinance is not None:
            return self.yfinance.get_profile(ticker)
        return {}

    def get_quote(self, ticker: str) -> Quote:
        from tools.marketdata.fmp import normalize_quote
        if self.fmp is not None:
            try:
                raw = asyncio.run(self.fmp.get_quote(ticker))
            except Exception:
                raw = None  # FMP error, or empty quote (FmpClient.get_quote raises) — fall through to yfinance
            result = raw if isinstance(raw, dict) and "fifty_two_week_high" in raw else normalize_quote(raw)
            if result:
                return result
        if self.yfinance is not None:
            return self.yfinance.get_quote(ticker)
        return {}

    def get_historical_prices(self, ticker: str, period: str = "1y") -> list[HistoricalBar]:
        from tools.marketdata.fmp import normalize_historical
        if self.fmp is not None:
            days = _PERIOD_TO_DAYS.get(period, 365)
            try:
                raw = asyncio.run(self.fmp.get_historical_prices(ticker, days=days))
            except Exception:
                raw = None  # FMP error (auth, rate-limit, network) — fall through to yfinance
            result = normalize_historical(raw)
            if result:
                return result
        if self.yfinance is not None:
            return self.yfinance.get_historical_prices(ticker, period=period)
        return []

    def get_short_interest(self, ticker: str) -> ShortInterest:
        """Normalized short-interest snapshot — FMP primary, yfinance fallback.

        FMP's short-interest endpoint is plan-dependent; FmpClient.get_short_interest
        already degrades any HTTP error to an empty list, and normalize_short_interest
        returns {} for a row with no usable signal. Either case (or a raised
        exception) falls through to yfinance, matching the other facade methods.
        """
        from tools.marketdata.fmp import normalize_short_interest
        if self.fmp is not None:
            try:
                raw = asyncio.run(self.fmp.get_short_interest(ticker))
            except Exception:
                raw = None
            # Mocks may already return the ShortInterest shape; raw FMP rows need normalization.
            result = raw if isinstance(raw, dict) and "shares_short" in raw \
                else normalize_short_interest(raw)
            if result:
                return result
        if self.yfinance is not None:
            return self.yfinance.get_short_interest(ticker)
        return {}

    def get_peers(self, ticker: str) -> list[str]:
        """FMP-only — yfinance has no peers endpoint."""
        if self.fmp is None:
            return []
        return asyncio.run(self.fmp.get_peers(ticker))

    def screen(self, **criteria: Any) -> list[ScreenResult]:
        """FMP-only — yfinance has no screener endpoint. FmpClient.screen not yet implemented."""
        return []
