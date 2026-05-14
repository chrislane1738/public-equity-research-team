"""MarketData — FMP primary, yfinance fallback. Normalized shapes per interface.py."""
from pathlib import Path
from typing import Any

from tools.marketdata.interface import (
    Estimate, HistoricalBar, KeyMetrics, Profile, Quote, Ratios, ScreenResult,
)


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
        if self.fmp is not None:
            result = self.fmp.get_profile(ticker)
            if result:
                return result
        if self.yfinance is not None:
            return self.yfinance.get_profile(ticker)
        return {}

    def get_quote(self, ticker: str) -> Quote:
        if self.fmp is not None:
            result = self.fmp.get_quote(ticker)
            if result:
                return result
        if self.yfinance is not None:
            return self.yfinance.get_quote(ticker)
        return {}

    def get_historical_prices(self, ticker: str, period: str = "1y") -> list[HistoricalBar]:
        if self.fmp is not None:
            result = self.fmp.get_historical_prices(ticker, period=period)
            if result:
                return result
        if self.yfinance is not None:
            return self.yfinance.get_historical_prices(ticker, period=period)
        return []

    def get_peers(self, ticker: str) -> list[str]:
        """FMP-only — yfinance has no peers endpoint."""
        if self.fmp is None:
            return []
        return self.fmp.get_peers(ticker)

    def screen(self, **criteria: Any) -> list[ScreenResult]:
        """FMP-only — yfinance has no screener endpoint."""
        if self.fmp is None:
            return []
        return self.fmp.screen(**criteria)
