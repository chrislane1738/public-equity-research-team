"""MarketData — single entry point for market data.

FMP is the primary source; yfinance is the fallback. Both are normalized to the
shapes in interface.py. Skills import `from tools.marketdata import MarketData`
and never need to know which source delivered any field.
"""
from typing import Optional


class MarketData:
    def __init__(self, fmp_client=None, yfinance_client=None):
        self.fmp = fmp_client
        self.yfinance = yfinance_client
