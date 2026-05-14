"""Settings load FMP/FRED/EDGAR keys from .env without requiring FastAPI-era fields."""
import importlib
import os

import pytest


def test_settings_loads_required_keys(monkeypatch, tmp_path):
    monkeypatch.setenv("FMP_API_KEY", "test-fmp")
    monkeypatch.setenv("FRED_API_KEY", "test-fred")
    monkeypatch.setenv("SEC_EDGAR_USER_AGENT", "Test User test@example.com")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    from tools import settings as s
    importlib.reload(s)

    assert s.FMP_API_KEY == "test-fmp"
    assert s.FRED_API_KEY == "test-fred"
    assert s.SEC_EDGAR_USER_AGENT == "Test User test@example.com"
    assert s.RESEARCH_DIR.name == "equity-research"


def test_settings_research_dir_override(monkeypatch, tmp_path):
    monkeypatch.setenv("FMP_API_KEY", "x")
    monkeypatch.setenv("SEC_EDGAR_USER_AGENT", "x")
    monkeypatch.setenv("RESEARCH_DIR", str(tmp_path / "custom"))

    from tools import settings as s
    importlib.reload(s)

    assert s.RESEARCH_DIR == tmp_path / "custom"


def test_settings_missing_fmp_key_raises(monkeypatch):
    monkeypatch.delenv("FMP_API_KEY", raising=False)
    monkeypatch.setenv("SEC_EDGAR_USER_AGENT", "x")
    from tools import settings as s
    with pytest.raises(RuntimeError, match="FMP_API_KEY"):
        importlib.reload(s)
