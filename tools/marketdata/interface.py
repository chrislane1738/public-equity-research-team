"""Return-shape spec for MarketData methods.

Plain TypedDicts — keep dependency-light. FMP responses are normalized to these
shapes; yfinance responses are also normalized to these shapes by the yfinance
client. Skills consume these and never see raw FMP/yfinance payloads.
"""
from typing import TypedDict


def _to_float(value) -> float | None:
    """Coerce *value* to a plain float, or ``None`` when the value is absent/blank.

    Handles the ``"None"``-string case that bare ``float()`` would raise on.
    Both the FMP and yfinance normalizers import this from here so the
    coercion logic lives in exactly one place.
    """
    if value in (None, "", "None"):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


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


class ShortInterest(TypedDict, total=False):
    """Normalized short-interest snapshot for a single ticker.

    ``short_percent_of_float`` is always a fraction (0.0–1.0), e.g. 0.042 == 4.2%
    of float.  Both the FMP and yfinance normalizers guarantee this range.

    ``days_to_cover`` is the short ratio (shares short / avg daily volume); ``None``
    if neither the provider supplies it nor average daily volume is available.

    The ``prior_*`` fields represent the previous FINRA settlement period (~30 days
    back) and are used by callers to compute a short-interest trend/delta.

    ``prior_short_percent_of_float`` may be ``None`` when a provider does not
    supply a true prior-period float (e.g. yfinance).  In that case, callers
    should compute the trend from ``shares_short`` vs ``prior_shares_short``
    rather than relying on the percent-of-float comparison.
    """
    symbol: str
    short_percent_of_float: float        # fraction of float sold short
    days_to_cover: float                 # short ratio (days)
    shares_short: float                  # absolute shares sold short
    as_of_date: str                      # ISO yyyy-mm-dd of the current data point
    prior_shares_short: float            # shares short, prior period
    prior_short_percent_of_float: float  # short % of float, prior period; may be None
    prior_as_of_date: str                # ISO yyyy-mm-dd of the prior data point
    source: str                          # "fmp" or "yfinance"
