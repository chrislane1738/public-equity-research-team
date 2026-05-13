import pytest
import respx
from httpx import Response

from backend.tools.fred_client import FredClient


@pytest.fixture
def client(tmp_path):
    return FredClient(api_key="fake-fred", cache_dir=tmp_path)


@respx.mock(using="httpx")
async def test_get_series_returns_observations(respx_mock, client):
    respx_mock.get("https://api.stlouisfed.org/fred/series/observations").mock(
        return_value=Response(
            200,
            json={"observations": [
                {"date": "2026-05-09", "value": "4.25"},
                {"date": "2026-05-08", "value": "4.20"},
            ]},
        )
    )
    obs = await client.get_series("DGS10", limit=2)
    assert obs[0]["date"] == "2026-05-09"
    assert obs[0]["value"] == 4.25
    assert len(obs) == 2


@respx.mock(using="httpx")
async def test_get_series_skips_dot_observations(respx_mock, client):
    respx_mock.get("https://api.stlouisfed.org/fred/series/observations").mock(
        return_value=Response(
            200,
            json={"observations": [
                {"date": "2026-05-09", "value": "."},
                {"date": "2026-05-08", "value": "4.20"},
            ]},
        )
    )
    obs = await client.get_series("DGS10", limit=2)
    assert len(obs) == 1
    assert obs[0]["value"] == 4.20


@respx.mock(using="httpx")
async def test_get_series_uses_cache(respx_mock, client):
    route = respx_mock.get("https://api.stlouisfed.org/fred/series/observations").mock(
        return_value=Response(200, json={"observations": [{"date": "2026-05-09", "value": "1"}]})
    )
    await client.get_series("DGS10", limit=1)
    await client.get_series("DGS10", limit=1)
    assert route.call_count == 1


@respx.mock(using="httpx")
async def test_get_series_raises_on_http_error(respx_mock, client):
    respx_mock.get("https://api.stlouisfed.org/fred/series/observations").mock(
        return_value=Response(403, json={"error": "bad key"})
    )
    with pytest.raises(RuntimeError, match="403"):
        await client.get_series("DGS10")
