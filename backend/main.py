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
# Plan B: FMP profile-based ticker→CIK lookup (replaces Plan A's _CIK_MAP).
# ---------------------------------------------------------------------------
import asyncio
from backend.cik_resolver import FmpProfileCikResolver
from backend.config import get_settings
from backend.observability.semaphore_client import SemaphoredAnthropicClient
from backend.orchestrator import Orchestrator
from backend.tools.edgar_client import EdgarClient
from backend.tools.fmp_client import FmpClient
from backend.tools.fred_client import FredClient
import anthropic as _anthropic_sdk


def _build_default_app() -> FastAPI:
    settings = get_settings()
    raw_anthropic = _anthropic_sdk.AsyncAnthropic(api_key=settings.anthropic_api_key)
    semaphore = asyncio.Semaphore(settings.max_concurrent_agents)
    anthropic_client = SemaphoredAnthropicClient(raw_anthropic, semaphore)

    fmp_client = FmpClient(api_key=settings.fmp_api_key,
                           cache_dir=settings.research_dir / "_fmp_cache")
    edgar_client = EdgarClient(user_agent=settings.sec_edgar_user_agent)
    fred_client = FredClient(api_key=settings.fred_api_key,
                             cache_dir=settings.research_dir / "_fred_cache")
    cik_resolver = FmpProfileCikResolver(fmp_client)

    orchestrator = Orchestrator(
        anthropic_client=anthropic_client, fmp_client=fmp_client,
        edgar_client=edgar_client, fred_client=fred_client,
        research_dir=settings.research_dir, cik_resolver=cik_resolver,
        settings=settings,
    )
    return build_app(orchestrator=orchestrator, research_dir=settings.research_dir)


# uvicorn loads `app` at module import. Load .env first so the guard sees the
# keys; then only construct `app` if both required keys resolved, so pytest can
# still `from backend.main import build_app` without env vars set.
import os as _os
from dotenv import load_dotenv as _load_dotenv

_load_dotenv()
if _os.environ.get("ANTHROPIC_API_KEY") and _os.environ.get("FMP_API_KEY"):
    app = _build_default_app()
