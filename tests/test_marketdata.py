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


def test_market_data_falls_back_to_yfinance_when_fmp_profile_raises():
    fmp = AsyncMock()
    fmp.get_profile.side_effect = RuntimeError("FMP 401")
    yf = MagicMock()
    yf.get_profile.return_value = {"symbol": "NVDA", "company_name": "NVIDIA (yf)"}

    md = MarketData(fmp_client=fmp, yfinance_client=yf)
    profile = md.get_profile("NVDA")

    assert profile["company_name"] == "NVIDIA (yf)"
    yf.get_profile.assert_called_once_with("NVDA")


def test_market_data_falls_back_to_yfinance_when_fmp_quote_raises():
    fmp = AsyncMock()
    fmp.get_quote.side_effect = RuntimeError("FMP quote empty")
    yf = MagicMock()
    yf.get_quote.return_value = {"symbol": "NVDA", "price": 100.0,
                                 "fifty_two_week_high": 150.0}

    md = MarketData(fmp_client=fmp, yfinance_client=yf)
    quote = md.get_quote("NVDA")

    assert quote["price"] == 100.0
    yf.get_quote.assert_called_once_with("NVDA")


def test_market_data_falls_back_to_yfinance_when_fmp_historical_raises():
    fmp = AsyncMock()
    fmp.get_historical_prices.side_effect = RuntimeError("FMP rate-limited")
    yf = MagicMock()
    yf.get_historical_prices.return_value = [
        {"date": "2026-05-15", "open": 1, "high": 2, "low": 1, "close": 2, "volume": 100}
    ]

    md = MarketData(fmp_client=fmp, yfinance_client=yf)
    bars = md.get_historical_prices("NVDA", period="1y")

    assert len(bars) == 1 and bars[0]["close"] == 2
    yf.get_historical_prices.assert_called_once_with("NVDA", period="1y")


# ---------------------------------------------------------------------------
# Short interest
# ---------------------------------------------------------------------------


@patch("tools.marketdata.yfinance.yf")
def test_yfinance_get_short_interest_returns_normalized_shape(mock_yf):
    mock_ticker = MagicMock()
    mock_ticker.info = {
        "symbol": "GME",
        "sharesShort": 50_000_000,
        "shortRatio": 4.5,
        "shortPercentOfFloat": 0.21,
        "sharesShortPriorMonth": 45_000_000,
        "sharesShortPreviousMonthDate": 1_711_843_200,  # 2024-03-31 UTC
        "dateShortInterest": 1_714_435_200,             # 2024-04-30 UTC
        "floatShares": 238_000_000,
        "averageVolume": 11_000_000,
    }
    mock_yf.Ticker.return_value = mock_ticker

    si = YFinanceClient().get_short_interest("GME")

    assert si["symbol"] == "GME"
    assert si["shares_short"] == 50_000_000
    assert si["days_to_cover"] == 4.5
    assert si["short_percent_of_float"] == 0.21
    assert si["prior_shares_short"] == 45_000_000
    assert si["as_of_date"] == "2024-04-30"
    assert si["prior_as_of_date"] == "2024-03-31"
    assert si["source"] == "yfinance"
    # yfinance does not supply a true prior-period float, so this is always None.
    assert si["prior_short_percent_of_float"] is None


@patch("tools.marketdata.yfinance.yf")
def test_yfinance_get_short_interest_computes_days_to_cover_when_missing(mock_yf):
    mock_ticker = MagicMock()
    mock_ticker.info = {
        "symbol": "GME",
        "sharesShort": 50_000_000,
        # no shortRatio — must be computed from sharesShort / averageVolume
        "shortPercentOfFloat": 0.21,
        "averageVolume": 10_000_000,
    }
    mock_yf.Ticker.return_value = mock_ticker

    si = YFinanceClient().get_short_interest("GME")

    assert si["days_to_cover"] == pytest.approx(5.0)


@patch("tools.marketdata.yfinance.yf")
def test_yfinance_get_short_interest_returns_empty_when_no_data(mock_yf):
    mock_ticker = MagicMock()
    mock_ticker.info = {"symbol": "ZZZZ"}  # no short fields
    mock_yf.Ticker.return_value = mock_ticker

    assert YFinanceClient().get_short_interest("ZZZZ") == {}


def test_market_data_short_interest_uses_fmp_when_available():
    fmp = AsyncMock()
    fmp.get_short_interest.return_value = [
        {"symbol": "NVDA", "date": "2026-04-30", "shortInterest": 250_000_000,
         "shortPercentOfFloat": 0.011, "daysToCover": 1.2},
        {"symbol": "NVDA", "date": "2026-04-15", "shortInterest": 240_000_000,
         "shortPercentOfFloat": 0.010, "daysToCover": 1.1},
    ]
    yf = MagicMock()

    md = MarketData(fmp_client=fmp, yfinance_client=yf)
    si = md.get_short_interest("NVDA")

    assert si["source"] == "fmp"
    assert si["shares_short"] == 250_000_000
    assert si["days_to_cover"] == 1.2
    assert si["short_percent_of_float"] == 0.011
    assert si["as_of_date"] == "2026-04-30"
    assert si["prior_shares_short"] == 240_000_000
    assert si["prior_short_percent_of_float"] == 0.010
    assert si["prior_as_of_date"] == "2026-04-15"
    yf.get_short_interest.assert_not_called()


def test_market_data_short_interest_falls_back_to_yfinance_when_fmp_empty():
    fmp = AsyncMock()
    fmp.get_short_interest.return_value = []  # FMP endpoint unavailable / empty
    yf = MagicMock()
    yf.get_short_interest.return_value = {
        "symbol": "GME", "shares_short": 50_000_000, "days_to_cover": 4.5,
        "short_percent_of_float": 0.21, "as_of_date": "2024-04-30",
        "source": "yfinance",
    }

    md = MarketData(fmp_client=fmp, yfinance_client=yf)
    si = md.get_short_interest("GME")

    assert si["source"] == "yfinance"
    assert si["shares_short"] == 50_000_000
    fmp.get_short_interest.assert_called_once_with("GME")
    yf.get_short_interest.assert_called_once_with("GME")


def test_market_data_short_interest_falls_back_to_yfinance_when_fmp_raises():
    fmp = AsyncMock()
    fmp.get_short_interest.side_effect = RuntimeError("FMP boom")
    yf = MagicMock()
    yf.get_short_interest.return_value = {
        "symbol": "GME", "shares_short": 50_000_000, "source": "yfinance",
    }

    md = MarketData(fmp_client=fmp, yfinance_client=yf)
    si = md.get_short_interest("GME")

    assert si["source"] == "yfinance"
    yf.get_short_interest.assert_called_once_with("GME")


# ---------------------------------------------------------------------------
# Scale-contract tests (Fix 1 + Fix 2 — short_percent_of_float always 0.0–1.0)
# ---------------------------------------------------------------------------

from tools.marketdata.fmp import normalize_short_interest  # noqa: E402


def test_fmp_normalize_short_interest_fraction_passthrough():
    """FMP fraction-form input (0.011) is preserved as-is."""
    rows = [
        {"symbol": "NVDA", "date": "2026-04-30", "shortInterest": 250_000_000,
         "shortPercentOfFloat": 0.011, "daysToCover": 1.2},
        {"symbol": "NVDA", "date": "2026-04-15", "shortInterest": 240_000_000,
         "shortPercentOfFloat": 0.010, "daysToCover": 1.1},
    ]
    si = normalize_short_interest(rows)
    pct = si["short_percent_of_float"]
    prior_pct = si["prior_short_percent_of_float"]
    assert 0.0 <= pct <= 1.0, f"short_percent_of_float out of range: {pct}"
    assert 0.0 <= prior_pct <= 1.0, f"prior_short_percent_of_float out of range: {prior_pct}"
    assert pct == pytest.approx(0.011)
    assert prior_pct == pytest.approx(0.010)


def test_fmp_normalize_short_interest_percentage_form_is_divided_by_100():
    """FMP percentage-form input (21.0 for 21%) is scaled down to a fraction (0.21)."""
    rows = [
        {"symbol": "GME", "date": "2026-04-30", "shortInterest": 50_000_000,
         "shortPercentOfFloat": 21.0, "daysToCover": 4.5},
        {"symbol": "GME", "date": "2026-04-15", "shortInterest": 45_000_000,
         "shortPercentOfFloat": 18.9, "daysToCover": 4.0},
    ]
    si = normalize_short_interest(rows)
    pct = si["short_percent_of_float"]
    prior_pct = si["prior_short_percent_of_float"]
    assert pct == pytest.approx(0.21), f"Expected 0.21, got {pct}"
    assert prior_pct == pytest.approx(0.189), f"Expected 0.189, got {prior_pct}"
    assert 0.0 <= pct <= 1.0
    assert 0.0 <= prior_pct <= 1.0


@patch("tools.marketdata.yfinance.yf")
def test_yfinance_normalize_short_interest_fraction_in_range(mock_yf):
    """yfinance short_percent_of_float is always in 0.0–1.0."""
    mock_ticker = MagicMock()
    mock_ticker.info = {
        "symbol": "GME",
        "sharesShort": 50_000_000,
        "shortPercentOfFloat": 0.21,
        "shortRatio": 4.5,
    }
    mock_yf.Ticker.return_value = mock_ticker

    si = YFinanceClient().get_short_interest("GME")
    pct = si["short_percent_of_float"]
    assert 0.0 <= pct <= 1.0, f"short_percent_of_float out of range: {pct}"
    assert pct == pytest.approx(0.21)


@patch("tools.marketdata.yfinance.yf")
def test_yfinance_prior_short_percent_of_float_is_none_when_no_prior_float(mock_yf):
    """yfinance path emits None for prior_short_percent_of_float (no genuine prior float)."""
    mock_ticker = MagicMock()
    mock_ticker.info = {
        "symbol": "GME",
        "sharesShort": 50_000_000,
        "shortPercentOfFloat": 0.21,
        "sharesShortPriorMonth": 45_000_000,  # prior shares present but no prior float
        "floatShares": 238_000_000,           # current float only
        "shortRatio": 4.5,
    }
    mock_yf.Ticker.return_value = mock_ticker

    si = YFinanceClient().get_short_interest("GME")
    assert si["prior_short_percent_of_float"] is None
    # prior_shares_short should still be populated
    assert si["prior_shares_short"] == 45_000_000
