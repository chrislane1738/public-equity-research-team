import os
from backend.config import Settings


def test_model_for_returns_default_when_no_override(monkeypatch, tmp_path):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "x")
    monkeypatch.setenv("FMP_API_KEY", "x")
    monkeypatch.setenv("FRED_API_KEY", "x")
    monkeypatch.setenv("SEC_EDGAR_USER_AGENT", "x x@x.com")
    monkeypatch.setenv("RESEARCH_DIR", str(tmp_path))
    for k in list(os.environ):
        if k.startswith("ANTHROPIC_MODEL_"):
            monkeypatch.delenv(k, raising=False)

    s = Settings()
    assert s.model_for("dcf") == s.anthropic_model
    assert s.model_for("memo_builder") == s.anthropic_model


def test_model_for_uses_per_agent_override(monkeypatch, tmp_path):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "x")
    monkeypatch.setenv("FMP_API_KEY", "x")
    monkeypatch.setenv("FRED_API_KEY", "x")
    monkeypatch.setenv("SEC_EDGAR_USER_AGENT", "x x@x.com")
    monkeypatch.setenv("RESEARCH_DIR", str(tmp_path))
    monkeypatch.setenv("ANTHROPIC_MODEL_MACRO", "claude-sonnet-4-6")
    monkeypatch.setenv("ANTHROPIC_MODEL_DECK_BUILDER", "claude-haiku-4-5-20251001")

    s = Settings()
    assert s.model_for("macro") == "claude-sonnet-4-6"
    assert s.model_for("deck_builder") == "claude-haiku-4-5-20251001"
    assert s.model_for("dcf") == s.anthropic_model  # no override


def test_fred_api_key_is_loaded(monkeypatch, tmp_path):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "x")
    monkeypatch.setenv("FMP_API_KEY", "x")
    monkeypatch.setenv("FRED_API_KEY", "fred-secret")
    monkeypatch.setenv("SEC_EDGAR_USER_AGENT", "x x@x.com")
    monkeypatch.setenv("RESEARCH_DIR", str(tmp_path))

    s = Settings()
    assert s.fred_api_key == "fred-secret"


def test_sqlite_path_is_repo_anchored_not_cwd_relative(monkeypatch, tmp_path):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "x")
    monkeypatch.setenv("FMP_API_KEY", "x")
    monkeypatch.setenv("FRED_API_KEY", "x")
    monkeypatch.setenv("SEC_EDGAR_USER_AGENT", "x x@x.com")
    monkeypatch.setenv("RESEARCH_DIR", str(tmp_path))
    monkeypatch.delenv("SQLITE_PATH", raising=False)

    s = Settings()
    # The default must be absolute and anchored at the repo, not CWD-relative.
    assert s.sqlite_path.is_absolute(), f"sqlite_path should be absolute, got {s.sqlite_path}"
    assert s.sqlite_path.name == "research.sqlite"
    assert s.sqlite_path.parent.name == "db"
