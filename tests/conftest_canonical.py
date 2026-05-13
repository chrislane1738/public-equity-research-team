"""Helpers to build mock FMP/EDGAR/FRED clients backed by tests/canonical/."""
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock


CANONICAL = Path(__file__).parent / "canonical"


def load(ticker: str, name: str):
    return json.loads((CANONICAL / ticker / name).read_text())


def fixtures_dir(ticker: str) -> Path:
    return CANONICAL / ticker


def build_fixture_fmp(ticker: str) -> MagicMock:
    fin = load(ticker, "financials.json")
    profile = load(ticker, "profile.json")
    quote = load(ticker, "quote.json")
    peers = load(ticker, "peers.json")
    history = load(ticker, "historical.json")["historical"]
    treasury = load(ticker, "treasury.json")

    fmp = MagicMock()
    fmp.get_financials = AsyncMock(return_value=fin)
    fmp.get_profile = AsyncMock(return_value=profile)
    fmp.get_quote = AsyncMock(return_value=quote)
    fmp.get_peers = AsyncMock(return_value=peers)
    fmp.get_historical_prices = AsyncMock(return_value=history)
    fmp.get_10y_treasury_rate = AsyncMock(return_value=treasury[0]["year10"])
    fmp.get_key_metrics = AsyncMock(return_value=[])
    fmp.get_ratios = AsyncMock(return_value=[])
    fmp.get_estimates = AsyncMock(return_value=[])
    return fmp


def build_fixture_edgar(ticker: str) -> MagicMock:
    html_path = CANONICAL / ticker / "10k.html"
    e = MagicMock()
    e.fetch_10k_excerpt = AsyncMock(return_value=html_path.read_text())
    return e


def build_fixture_fred(ticker: str) -> MagicMock:
    bundle = load(ticker, "fred.json")
    f = MagicMock()

    async def _get(series_id, limit=12):
        return [{"date": o["date"], "value": float(o["value"])} for o in bundle.get(series_id, [])]

    f.get_series = AsyncMock(side_effect=_get)
    return f
