"""FMP-backed ticker → CIK lookup. Replaces Plan A's hard-coded _CIK_MAP."""


class FmpProfileCikResolver:
    """Resolves a ticker to its 10-digit zero-padded CIK by reading FMP /profile."""

    def __init__(self, fmp_client):
        self.fmp = fmp_client

    async def resolve(self, ticker: str) -> str:
        profile = await self.fmp.get_profile(ticker.upper())
        cik = profile.get("cik")
        if not cik:
            raise RuntimeError(f"No CIK in FMP profile for {ticker}")
        return str(cik).zfill(10)
