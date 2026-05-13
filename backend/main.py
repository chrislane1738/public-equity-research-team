"""FastAPI application factory."""
from pathlib import Path

from fastapi import FastAPI

from backend.routes.jobs import build_router


def build_app(orchestrator, research_dir: Path) -> FastAPI:
    app = FastAPI(title="Public Equity Research Team — Backend")
    app.include_router(build_router(orchestrator))

    @app.get("/healthz")
    async def healthz():
        return {"status": "ok"}

    return app


# ---------------------------------------------------------------------------
# uvicorn entrypoint: build the app with real clients from Settings.
# Plan A: hard-code a small CIK map. Plan B will add an FMP ticker→CIK lookup.
# ---------------------------------------------------------------------------
from backend.config import get_settings
from backend.orchestrator import Orchestrator
from backend.tools.edgar_client import EdgarClient
from backend.tools.fmp_client import FmpClient
import anthropic as _anthropic_sdk


_CIK_MAP = {"NVDA": "0001045810", "AAPL": "0000320193", "MSFT": "0000789019"}


def _build_default_app() -> FastAPI:
    settings = get_settings()
    anthropic_client = _anthropic_sdk.AsyncAnthropic(api_key=settings.anthropic_api_key)
    fmp_client = FmpClient(
        api_key=settings.fmp_api_key,
        cache_dir=settings.research_dir / "_fmp_cache",
    )
    edgar_client = EdgarClient(user_agent=settings.sec_edgar_user_agent)
    orchestrator = Orchestrator(
        anthropic_client=anthropic_client,
        fmp_client=fmp_client,
        edgar_client=edgar_client,
        research_dir=settings.research_dir,
        ticker_to_cik=_CIK_MAP,
        opus_model=settings.anthropic_model,
        sonnet_model="claude-sonnet-4-6",
    )
    return build_app(orchestrator=orchestrator, research_dir=settings.research_dir)


# uvicorn loads `app` at module import. We only construct it if env vars are
# present so that `pytest` can `from backend.main import build_app` without
# needing ANTHROPIC_API_KEY/FMP_API_KEY set in the shell.
import os as _os
if _os.environ.get("ANTHROPIC_API_KEY") and _os.environ.get("FMP_API_KEY"):
    app = _build_default_app()
