import json
import time
from pathlib import Path

import pytest
import respx
from httpx import Response

from backend.tools.fmp_client import FmpClient


FIXTURE = json.loads(
    (Path(__file__).parent / "fixtures" / "fmp_nvda_financials.json").read_text()
)

FMP_BASE = "https://financialmodelingprep.com/stable"


@pytest.fixture
def client(tmp_path):
    return FmpClient(api_key="fake-key", cache_dir=tmp_path)


@respx.mock(using="httpx")
async def test_get_financials_fetches_three_statements(client, respx_mock):
    respx_mock.get(f"{FMP_BASE}/income-statement").mock(
        return_value=Response(200, json=FIXTURE["income"])
    )
    respx_mock.get(f"{FMP_BASE}/balance-sheet-statement").mock(
        return_value=Response(200, json=FIXTURE["balance"])
    )
    respx_mock.get(f"{FMP_BASE}/cash-flow-statement").mock(
        return_value=Response(200, json=FIXTURE["cash"])
    )

    result = await client.get_financials("NVDA")

    assert result["income"][0]["revenue"] == 60922000000
    assert result["balance"][0]["totalAssets"] == 65728000000
    assert result["cash"][0]["freeCashFlow"] == 27021000000


@respx.mock(using="httpx")
async def test_get_financials_uses_cache_on_second_call(client, respx_mock):
    route = respx_mock.get(f"{FMP_BASE}/income-statement").mock(
        return_value=Response(200, json=FIXTURE["income"])
    )
    respx_mock.get(f"{FMP_BASE}/balance-sheet-statement").mock(
        return_value=Response(200, json=FIXTURE["balance"])
    )
    respx_mock.get(f"{FMP_BASE}/cash-flow-statement").mock(
        return_value=Response(200, json=FIXTURE["cash"])
    )

    await client.get_financials("NVDA")
    await client.get_financials("NVDA")

    # only one network call per endpoint despite two get_financials() calls
    assert route.call_count == 1


@respx.mock(using="httpx")
async def test_get_financials_raises_on_http_error(client, respx_mock):
    respx_mock.get(f"{FMP_BASE}/income-statement").mock(
        return_value=Response(429, json={"error": "rate limited"})
    )

    with pytest.raises(Exception, match="429"):
        await client.get_financials("NVDA")
