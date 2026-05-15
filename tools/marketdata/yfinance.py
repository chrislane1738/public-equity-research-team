"""yfinance fallback — keyless Yahoo Finance scraping, normalized to FMP shapes."""
from datetime import datetime, timezone
from typing import Any

import yfinance as yf  # type: ignore[import-untyped]

from tools.marketdata.interface import HistoricalBar, Profile, Quote, ShortInterest


def _yf_date(value) -> str:
    """Coerce a yfinance date field to ISO yyyy-mm-dd.

    yfinance reports short-interest dates as a Unix epoch (seconds, UTC), but
    occasionally as an ISO string already — handle both, return "" otherwise.
    """
    if value in (None, ""):
        return ""
    if isinstance(value, str):
        return value[:10]
    try:
        return datetime.fromtimestamp(int(value), tz=timezone.utc).strftime("%Y-%m-%d")
    except (TypeError, ValueError, OSError, OverflowError):
        return ""


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

    def get_short_interest(self, ticker: str) -> ShortInterest:
        """Short interest from ``yf.Ticker(ticker).info``.

        Yahoo exposes ``sharesShort``, ``shortRatio`` (days-to-cover),
        ``shortPercentOfFloat``, ``sharesShortPriorMonth`` and the corresponding
        dates. days-to-cover falls back to ``sharesShort / averageVolume`` when
        ``shortRatio`` is absent. The prior period's short % of float is not
        published directly, so it is derived from ``sharesShortPriorMonth /
        floatShares`` when float is available. Returns ``{}`` when Yahoo carries
        no short-interest signal at all.
        """
        info = yf.Ticker(ticker).info or {}
        shares_short = info.get("sharesShort")
        pct_float = info.get("shortPercentOfFloat")
        if shares_short in (None, "") and pct_float in (None, ""):
            return {}

        shares_short_f = float(shares_short) if shares_short not in (None, "") else None
        days_to_cover = info.get("shortRatio")
        days_to_cover_f = float(days_to_cover) if days_to_cover not in (None, "") else None
        if days_to_cover_f is None:
            avg_vol = info.get("averageVolume")
            if shares_short_f is not None and avg_vol:
                days_to_cover_f = shares_short_f / float(avg_vol)

        prior_shares = info.get("sharesShortPriorMonth")
        prior_shares_f = float(prior_shares) if prior_shares not in (None, "") else None
        prior_pct_float = None
        float_shares = info.get("floatShares")
        if prior_shares_f is not None and float_shares:
            prior_pct_float = prior_shares_f / float(float_shares)

        return {
            "symbol": info.get("symbol", ticker),
            "shares_short": shares_short_f,
            "short_percent_of_float": float(pct_float) if pct_float not in (None, "") else None,
            "days_to_cover": days_to_cover_f,
            "as_of_date": _yf_date(info.get("dateShortInterest")),
            "prior_shares_short": prior_shares_f,
            "prior_short_percent_of_float": prior_pct_float,
            "prior_as_of_date": _yf_date(info.get("sharesShortPreviousMonthDate")),
            "source": "yfinance",
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
