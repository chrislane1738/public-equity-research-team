"""MarketData abstraction — FMP primary, yfinance fallback, normalized shapes."""
from unittest.mock import MagicMock

import pytest

from tools.marketdata import MarketData
from tools.marketdata.interface import (
    Profile, Quote, HistoricalBar, KeyMetrics, Ratios, Estimate,
)


def test_market_data_constructs_with_dependencies():
    md = MarketData(fmp_client=MagicMock(), yfinance_client=MagicMock())
    assert md.fmp is not None
    assert md.yfinance is not None
