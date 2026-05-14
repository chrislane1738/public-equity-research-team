"""Return-shape spec for MarketData methods.

Plain TypedDicts — keep dependency-light. FMP responses are normalized to these
shapes; yfinance responses are also normalized to these shapes by the yfinance
client. Skills consume these and never see raw FMP/yfinance payloads.
"""
from typing import TypedDict


class Profile(TypedDict, total=False):
    symbol: str
    company_name: str
    industry: str
    sector: str
    sic_code: str
    market_cap: float
    beta: float
    description: str
    exchange: str


class Quote(TypedDict, total=False):
    symbol: str
    price: float
    shares_outstanding: float
    fifty_two_week_high: float
    fifty_two_week_low: float


class HistoricalBar(TypedDict):
    date: str  # ISO yyyy-mm-dd
    open: float
    high: float
    low: float
    close: float
    volume: float


class KeyMetrics(TypedDict, total=False):
    symbol: str
    pe_ratio: float
    ev_to_ebitda: float
    ev_to_revenue: float
    debt_to_equity: float
    return_on_equity: float


class Ratios(TypedDict, total=False):
    symbol: str
    gross_margin: float
    operating_margin: float
    net_margin: float
    asset_turnover: float


class Estimate(TypedDict, total=False):
    symbol: str
    fiscal_year: int
    revenue_estimate: float
    eps_estimate: float


class ScreenResult(TypedDict, total=False):
    symbol: str
    company_name: str
    market_cap: float
    industry: str
    sector: str
