import pytest
import respx
from httpx import Response

from backend.tools.fmp_client import FmpClient


@pytest.fixture
def client(tmp_path):
    return FmpClient(api_key="fake-key", cache_dir=tmp_path)


@respx.mock(using="httpx")
async def test_get_profile_returns_first_record(respx_mock, client):
    respx_mock.get("https://financialmodelingprep.com/stable/profile").mock(
        return_value=Response(
            200,
            json=[{"symbol": "NVDA", "cik": "0001045810", "beta": 1.65,
                   "mktCap": 3_000_000_000_000, "sector": "Technology"}],
        )
    )
    profile = await client.get_profile("NVDA")
    assert profile["cik"] == "0001045810"
    assert profile["beta"] == 1.65


@respx.mock(using="httpx")
async def test_get_quote_returns_first_record(respx_mock, client):
    respx_mock.get("https://financialmodelingprep.com/stable/quote").mock(
        return_value=Response(
            200,
            json=[{"symbol": "NVDA", "price": 1100.0, "yearLow": 400.0,
                   "yearHigh": 1200.0, "marketCap": 3e12, "sharesOutstanding": 2.5e9}],
        )
    )
    q = await client.get_quote("NVDA")
    assert q["price"] == 1100.0
    assert q["yearHigh"] == 1200.0


@respx.mock(using="httpx")
async def test_get_historical_prices_returns_history_list(respx_mock, client):
    respx_mock.get(
        "https://financialmodelingprep.com/stable/historical-price-eod/full"
    ).mock(
        return_value=Response(
            200,
            json={
                "symbol": "NVDA",
                "historical": [
                    {"date": "2026-05-09", "close": 1100.0, "volume": 200_000_000},
                    {"date": "2026-05-08", "close": 1090.0, "volume": 180_000_000},
                ],
            },
        )
    )
    rows = await client.get_historical_prices("NVDA", days=2)
    assert len(rows) == 2
    assert rows[0]["close"] == 1100.0


@respx.mock(using="httpx")
async def test_get_peers_returns_symbols(respx_mock, client):
    respx_mock.get("https://financialmodelingprep.com/stable/stock-peers").mock(
        return_value=Response(200, json=[{"symbol": "NVDA",
                                          "peers": ["AMD", "INTC", "AVGO", "QCOM"]}]),
    )
    peers = await client.get_peers("NVDA")
    assert "AMD" in peers
    assert "QCOM" in peers
    assert "NVDA" not in peers  # peers exclude self


@respx.mock(using="httpx")
async def test_get_key_metrics_returns_records(respx_mock, client):
    respx_mock.get("https://financialmodelingprep.com/stable/key-metrics").mock(
        return_value=Response(200, json=[{"date": "2024-01-28", "enterpriseValue": 2.9e12,
                                          "evToEbitda": 45.0, "peRatio": 80.0}]),
    )
    rows = await client.get_key_metrics("NVDA")
    assert rows[0]["evToEbitda"] == 45.0


@respx.mock(using="httpx")
async def test_get_ratios_returns_records(respx_mock, client):
    respx_mock.get("https://financialmodelingprep.com/stable/ratios").mock(
        return_value=Response(200, json=[{"date": "2024-01-28", "grossProfitMargin": 0.73,
                                          "returnOnEquity": 0.65, "debtToEquity": 0.25}]),
    )
    rows = await client.get_ratios("NVDA")
    assert rows[0]["returnOnEquity"] == 0.65


@respx.mock(using="httpx")
async def test_get_estimates_returns_records(respx_mock, client):
    respx_mock.get("https://financialmodelingprep.com/stable/analyst-estimates").mock(
        return_value=Response(200, json=[{"date": "2026-01-31", "estimatedRevenueAvg": 250e9,
                                          "estimatedEpsAvg": 50.0}]),
    )
    rows = await client.get_estimates("NVDA")
    assert rows[0]["estimatedRevenueAvg"] == 250e9


@respx.mock(using="httpx")
async def test_get_treasury_rates_returns_latest(respx_mock, client):
    respx_mock.get("https://financialmodelingprep.com/stable/treasury-rates").mock(
        return_value=Response(200, json=[{"date": "2026-05-09", "year10": 4.25, "year30": 4.45},
                                         {"date": "2026-05-08", "year10": 4.20, "year30": 4.40}]),
    )
    rate = await client.get_10y_treasury_rate()
    assert rate == 4.25


@respx.mock(using="httpx")
async def test_extension_endpoints_use_cache(respx_mock, client):
    route = respx_mock.get("https://financialmodelingprep.com/stable/profile").mock(
        return_value=Response(200, json=[{"symbol": "NVDA", "cik": "0001045810"}])
    )
    await client.get_profile("NVDA")
    await client.get_profile("NVDA")
    assert route.call_count == 1


@respx.mock(using="httpx")
async def test_get_profile_raises_on_empty_response(respx_mock, client):
    respx_mock.get("https://financialmodelingprep.com/stable/profile").mock(
        return_value=Response(200, json=[])
    )
    with pytest.raises(RuntimeError, match="profile empty"):
        await client.get_profile("ZZZZ")


@respx.mock(using="httpx")
async def test_get_quote_raises_on_empty_response(respx_mock, client):
    respx_mock.get("https://financialmodelingprep.com/stable/quote").mock(
        return_value=Response(200, json=[])
    )
    with pytest.raises(RuntimeError, match="quote empty"):
        await client.get_quote("ZZZZ")


@respx.mock(using="httpx")
async def test_get_10y_treasury_rate_uses_cache(respx_mock, client):
    route = respx_mock.get("https://financialmodelingprep.com/stable/treasury-rates").mock(
        return_value=Response(200, json=[{"date": "2026-05-09", "year10": 4.25, "year30": 4.45}])
    )
    await client.get_10y_treasury_rate()
    await client.get_10y_treasury_rate()
    assert route.call_count == 1
