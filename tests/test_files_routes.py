import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from backend.db.sqlite_client import SqliteClient
from backend.main import build_app
from backend.observability.event_bus import JobEventBus


@pytest.fixture
def client(tmp_path: Path):
    # Seed a fake research dir.
    nvda = tmp_path / "NVDA"
    (nvda / "fundamentals").mkdir(parents=True)
    (nvda / "fundamentals" / "section.md").write_text("# NVDA fundamentals\n")
    (nvda / "fundamentals" / "kpis.json").write_text(json.dumps({"dc": 100}))
    (nvda / "reports").mkdir()
    (nvda / "reports" / "memo.docx").write_bytes(b"\x50\x4b\x03\x04docx")
    (tmp_path / "AAPL" / "fundamentals").mkdir(parents=True)

    sqlite = SqliteClient(tmp_path / "test.sqlite")
    orch = MagicMock()
    app = build_app(orchestrator=orch, research_dir=tmp_path,
                    sqlite_client=sqlite, event_bus=JobEventBus())
    with TestClient(app) as c:
        yield c, tmp_path


def test_list_tickers(client):
    c, _ = client
    r = c.get("/tickers")
    assert r.status_code == 200
    assert sorted(r.json()["tickers"]) == ["AAPL", "NVDA"]


def test_list_tickers_skips_underscore_prefixed_dirs(tmp_path: Path):
    sqlite = SqliteClient(tmp_path / "test.sqlite")
    (tmp_path / "_fmp_cache").mkdir()
    (tmp_path / "_fred_cache").mkdir()
    (tmp_path / "MSFT").mkdir()
    app = build_app(orchestrator=MagicMock(), research_dir=tmp_path,
                    sqlite_client=sqlite, event_bus=JobEventBus())
    with TestClient(app) as c:
        assert c.get("/tickers").json()["tickers"] == ["MSFT"]


def test_files_for_ticker(client):
    c, _ = client
    r = c.get("/tickers/NVDA/files")
    assert r.status_code == 200
    body = r.json()
    names = [n["name"] for n in body["tree"]]
    assert "fundamentals" in names
    assert "reports" in names
    fund = next(n for n in body["tree"] if n["name"] == "fundamentals")
    file_names = sorted(child["name"] for child in fund["children"])
    assert file_names == ["kpis.json", "section.md"]


def test_files_for_unknown_ticker_returns_404(client):
    c, _ = client
    r = c.get("/tickers/UNKNOWN/files")
    assert r.status_code == 404


def test_get_file_returns_content_with_correct_mime(client):
    c, _ = client
    r = c.get("/files", params={"path": "NVDA/fundamentals/section.md"})
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/")
    assert "NVDA fundamentals" in r.text


def test_get_file_rejects_path_traversal(client):
    c, _ = client
    r = c.get("/files", params={"path": "../../etc/passwd"})
    assert r.status_code == 400


def test_get_file_404_for_missing(client):
    c, _ = client
    r = c.get("/files", params={"path": "NVDA/fundamentals/nope.md"})
    assert r.status_code == 404


def test_get_file_rejects_symlink_escape(tmp_path: Path):
    """A symlink inside RESEARCH_DIR pointing outside must not be readable."""
    import os
    sqlite = SqliteClient(tmp_path / "test.sqlite")
    research_dir = tmp_path / "research"
    outside_dir = tmp_path / "outside"
    research_dir.mkdir()
    outside_dir.mkdir()
    (research_dir / "NVDA").mkdir()
    secret = outside_dir / "secret.txt"
    secret.write_text("classified")
    # Create a symlink at NVDA/leak -> ../../outside/secret.txt
    os.symlink(secret, research_dir / "NVDA" / "leak.txt")

    app = build_app(orchestrator=MagicMock(), research_dir=research_dir,
                    sqlite_client=sqlite, event_bus=JobEventBus())
    with TestClient(app) as c:
        r = c.get("/files", params={"path": "NVDA/leak.txt"})
    assert r.status_code == 400, f"expected 400, got {r.status_code}: {r.text}"
