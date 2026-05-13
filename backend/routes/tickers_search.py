"""Ticker autocomplete — proxies FMP /stable/stock-list, filtered + capped."""
from fastapi import APIRouter, Query

_ALLOWED_EXCHANGES = {"NASDAQ", "NYSE", "AMEX", "BATS", "ARCA", "NYSEARCA"}


def build_tickers_search_router(fmp_client) -> APIRouter:
    router = APIRouter()

    @router.get("/tickers/search")
    async def search(q: str = Query(...)):
        q = (q or "").strip().upper()
        if not q:
            return {"results": []}
        all_tickers = await fmp_client.get_stock_list()
        results = []
        for row in all_tickers:
            sym = (row.get("symbol") or "").upper()
            ex = (row.get("exchange") or "").upper()
            if not sym or ex not in _ALLOWED_EXCHANGES:
                continue
            if sym.startswith(q):
                results.append({
                    "symbol": sym,
                    "name": row.get("name", ""),
                    "exchange": ex,
                })
                if len(results) >= 20:
                    break
        return {"results": results}

    return router
