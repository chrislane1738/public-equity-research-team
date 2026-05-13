import os
from pathlib import Path
from backend.config import Settings


def test_settings_loads_required_env(monkeypatch, tmp_path):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-anthropic-key")
    monkeypatch.setenv("FMP_API_KEY", "test-fmp-key")
    monkeypatch.setenv("RESEARCH_DIR", str(tmp_path))
    monkeypatch.setenv("SEC_EDGAR_USER_AGENT", "Test test@example.com")

    settings = Settings()

    assert settings.anthropic_api_key == "test-anthropic-key"
    assert settings.fmp_api_key == "test-fmp-key"
    assert settings.research_dir == tmp_path
    assert settings.anthropic_model == "claude-opus-4-7"


def test_settings_resolves_tilde_in_research_dir(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "x")
    monkeypatch.setenv("FMP_API_KEY", "x")
    monkeypatch.setenv("RESEARCH_DIR", "~/Documents/equity-research")
    monkeypatch.setenv("SEC_EDGAR_USER_AGENT", "x x@x.com")

    settings = Settings()

    assert settings.research_dir == Path.home() / "Documents" / "equity-research"


def test_ticker_dir_creates_subfolder_path(monkeypatch, tmp_path):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "x")
    monkeypatch.setenv("FMP_API_KEY", "x")
    monkeypatch.setenv("RESEARCH_DIR", str(tmp_path))
    monkeypatch.setenv("SEC_EDGAR_USER_AGENT", "x x@x.com")

    settings = Settings()
    path = settings.ticker_dir("NVDA")

    assert path == tmp_path / "NVDA"
