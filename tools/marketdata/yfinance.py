"""yfinance fallback — keyless Yahoo Finance scraping, normalized to FMP shapes."""
from typing import Any

import yfinance as yf  # type: ignore[import-untyped]

from tools.marketdata.interface import HistoricalBar, Profile, Quote


class YFinanceClient:
    """Keyless Yahoo Finance fallback. All methods return interface-shaped dicts."""

    def get_profile(self, ticker: str) -> Profile:
        info = yf.Ticker(ticker).info or {}
        if not info or not info.get("symbol"):
            return {}
        return {
            "symbol": info.get("symbol", ticker),
            "company_name": info.get("longName") or info.get("shortName") or "",
            "industry": info.get("industry", ""),
            "sector": info.get("sector", ""),
            "sic_code": "",  # yfinance doesn't expose SIC
            "market_cap": float(info.get("marketCap", 0) or 0),
            "beta": float(info.get("beta", 0) or 0),
            "description": info.get("longBusinessSummary", ""),
            "exchange": info.get("exchange", ""),
        }

    def get_quote(self, ticker: str) -> Quote:
        info = yf.Ticker(ticker).info or {}
        if not info:
            return {}
        price = info.get("currentPrice") or info.get("regularMarketPrice") or 0
        return {
            "symbol": info.get("symbol", ticker),
            "price": float(price),
            "shares_outstanding": float(info.get("sharesOutstanding", 0) or 0),
            "fifty_two_week_high": float(info.get("fiftyTwoWeekHigh", 0) or 0),
            "fifty_two_week_low": float(info.get("fiftyTwoWeekLow", 0) or 0),
        }

    def get_historical_prices(self, ticker: str, period: str = "1y") -> list[HistoricalBar]:
        df = yf.Ticker(ticker).history(period=period)
        if df is None or df.empty:
            return []
        bars: list[HistoricalBar] = []
        for idx, row in df.iterrows():
            bars.append(
                {
                    "date": idx.strftime("%Y-%m-%d"),
                    "open": float(row["Open"]),
                    "high": float(row["High"]),
                    "low": float(row["Low"]),
                    "close": float(row["Close"]),
                    "volume": float(row["Volume"]),
                }
            )
        return bars
