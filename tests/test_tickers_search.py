from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from backend.db.sqlite_client import SqliteClient
from backend.main import build_app
from backend.observability.event_bus import JobEventBus


@pytest.fixture
def client(tmp_path: Path):
    fmp = MagicMock()
    fmp.get_stock_list = AsyncMock(return_value=[
        {"symbol": "NVDA", "name": "NVIDIA Corporation", "exchange": "NASDAQ"},
        {"symbol": "NVTS", "name": "Navitas Semiconductor", "exchange": "NASDAQ"},
        {"symbol": "AAPL", "name": "Apple Inc.", "exchange": "NASDAQ"},
        {"symbol": "GOOGL", "name": "Alphabet", "exchange": "NASDAQ"},
        {"symbol": "MSFT", "name": "Microsoft", "exchange": "NASDAQ"},
        {"symbol": "XYZ",  "name": "Random Bond",        "exchange": "OTC"},
    ])
    sqlite = SqliteClient(tmp_path / "test.sqlite")
    app = build_app(orchestrator=MagicMock(), research_dir=tmp_path,
                    sqlite_client=sqlite, event_bus=JobEventBus(),
                    fmp_client=fmp)
    with TestClient(app) as c:
        yield c, fmp


def test_search_prefix_match(client):
    c, _ = client
    r = c.get("/tickers/search", params={"q": "NV"})
    assert r.status_code == 200
    matches = [m["symbol"] for m in r.json()["results"]]
    assert "NVDA" in matches
    assert "NVTS" in matches
    assert "AAPL" not in matches


def test_search_filters_non_equity_exchanges(client):
    c, _ = client
    r = c.get("/tickers/search", params={"q": "X"})
    assert r.json()["results"] == []  # XYZ is OTC, excluded


def test_search_caps_results_at_20(client):
    c, fmp = client
    fmp.get_stock_list.return_value = [
        {"symbol": f"AAA{i:03d}", "name": f"A{i}", "exchange": "NASDAQ"}
        for i in range(50)
    ]
    r = c.get("/tickers/search", params={"q": "A"})
    assert len(r.json()["results"]) == 20


def test_search_empty_query_returns_empty(client):
    c, _ = client
    r = c.get("/tickers/search", params={"q": ""})
    assert r.json()["results"] == []


def test_search_is_case_insensitive(client):
    c, _ = client
    r = c.get("/tickers/search", params={"q": "nv"})
    matches = [m["symbol"] for m in r.json()["results"]]
    assert "NVDA" in matches
