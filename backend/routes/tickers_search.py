"""Ticker autocomplete — proxies FMP /stable/search-symbol, filtered + capped."""
from fastapi import APIRouter, Query

_ALLOWED_EXCHANGES = {"NASDAQ", "NYSE", "AMEX", "BATS", "ARCA", "NYSEARCA"}
_MAX_RESULTS = 20


def build_tickers_search_router(fmp_client) -> APIRouter:
    router = APIRouter()

    @router.get("/tickers/search")
    async def search(q: str = Query(...)):
        q = (q or "").strip().upper()
        if not q:
            return {"results": []}
        # Ask FMP for a few extra so the exchange filter has headroom.
        rows = await fmp_client.search_symbols(q, limit=_MAX_RESULTS * 2)
        results = []
        for row in rows:
            sym = (row.get("symbol") or "").upper()
            ex = (row.get("exchange") or "").upper()
            if not sym or ex not in _ALLOWED_EXCHANGES:
                continue
            results.append({
                "symbol": sym,
                "name": row.get("name", ""),
                "exchange": ex,
            })
            if len(results) >= _MAX_RESULTS:
                break
        return {"results": results}

    return router
