from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.cik_resolver import FmpProfileCikResolver


@pytest.fixture
def fmp():
    f = MagicMock()
    f.get_profile = AsyncMock(return_value={"symbol": "NVDA", "cik": "1045810"})
    return f


async def test_resolve_pads_cik_to_10_digits(fmp):
    resolver = FmpProfileCikResolver(fmp)
    cik = await resolver.resolve("NVDA")
    assert cik == "0001045810"


async def test_resolve_uppercases_ticker_in_lookup(fmp):
    resolver = FmpProfileCikResolver(fmp)
    await resolver.resolve("nvda")
    fmp.get_profile.assert_awaited_once_with("NVDA")


async def test_resolve_raises_when_cik_missing():
    f = MagicMock()
    f.get_profile = AsyncMock(return_value={"symbol": "NVDA"})  # no cik
    resolver = FmpProfileCikResolver(f)
    with pytest.raises(RuntimeError, match="CIK"):
        await resolver.resolve("NVDA")
