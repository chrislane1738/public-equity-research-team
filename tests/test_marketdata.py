"""MarketData abstraction — FMP primary, yfinance fallback, normalized shapes."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tools.marketdata import MarketData
from tools.marketdata.interface import (
    Profile, Quote, HistoricalBar, KeyMetrics, Ratios, Estimate,
)


def test_market_data_constructs_with_dependencies():
    md = MarketData(fmp_client=MagicMock(), yfinance_client=MagicMock())
    assert md.fmp is not None
    assert md.yfinance is not None


from tools.marketdata.yfinance import YFinanceClient


@patch("tools.marketdata.yfinance.yf")
def test_yfinance_get_profile_returns_normalized_shape(mock_yf):
    mock_ticker = MagicMock()
    mock_ticker.info = {
        "symbol": "NVDA",
        "longName": "NVIDIA Corporation",
        "industry": "Semiconductors",
        "sector": "Technology",
        "marketCap": 3_000_000_000_000,
        "beta": 1.7,
        "longBusinessSummary": "GPU maker.",
        "exchange": "NASDAQ",
    }
    mock_yf.Ticker.return_value = mock_ticker

    client = YFinanceClient()
    profile = client.get_profile("NVDA")

    assert profile["symbol"] == "NVDA"
    assert profile["company_name"] == "NVIDIA Corporation"
    assert profile["industry"] == "Semiconductors"
    assert profile["market_cap"] == 3_000_000_000_000
    assert profile["beta"] == 1.7


@patch("tools.marketdata.yfinance.yf")
def test_yfinance_get_historical_prices_returns_normalized_bars(mock_yf):
    import pandas as pd
    mock_ticker = MagicMock()
    df = pd.DataFrame(
        {
            "Open": [100.0, 101.0],
            "High": [102.0, 103.0],
            "Low": [99.0, 100.0],
            "Close": [101.5, 102.5],
            "Volume": [1_000_000, 1_100_000],
        },
        index=pd.to_datetime(["2025-01-01", "2025-01-02"]),
    )
    mock_ticker.history.return_value = df
    mock_yf.Ticker.return_value = mock_ticker

    client = YFinanceClient()
    bars = client.get_historical_prices("NVDA", period="2d")

    assert len(bars) == 2
    assert bars[0]["date"] == "2025-01-01"
    assert bars[0]["close"] == 101.5
    assert bars[1]["volume"] == 1_100_000


def test_market_data_falls_back_to_yfinance_when_fmp_returns_empty():
    fmp = AsyncMock()
    fmp.get_profile.return_value = {}
    yf = MagicMock()
    yf.get_profile.return_value = {"symbol": "NVDA", "company_name": "NVIDIA"}

    md = MarketData(fmp_client=fmp, yfinance_client=yf)
    profile = md.get_profile("NVDA")

    assert profile["company_name"] == "NVIDIA"
    fmp.get_profile.assert_called_once_with("NVDA")
    yf.get_profile.assert_called_once_with("NVDA")


def test_market_data_uses_fmp_when_available():
    fmp = AsyncMock()
    fmp.get_profile.return_value = {"symbol": "NVDA", "company_name": "NVIDIA (FMP)"}
    yf = MagicMock()

    md = MarketData(fmp_client=fmp, yfinance_client=yf)
    profile = md.get_profile("NVDA")

    assert profile["company_name"] == "NVIDIA (FMP)"
    yf.get_profile.assert_not_called()
