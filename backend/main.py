"""FastAPI application factory."""
from pathlib import Path
from typing import Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.db.job_repo import JobRepo
from backend.db.sqlite_client import SqliteClient
from backend.job_runner import JobRunner
from backend.observability.event_bus import JobEventBus
from backend.routes.files import build_files_router
from backend.routes.jobs import build_router
from backend.routes.tickers_search import build_tickers_search_router


def build_app(
    orchestrator,
    research_dir: Path,
    sqlite_client,
    event_bus: Optional[JobEventBus] = None,
    fmp_client=None,
) -> FastAPI:
    app = FastAPI(title="Public Equity Research Team — Backend")
    bus = event_bus or JobEventBus()
    job_repo = JobRepo(sqlite_client)
    runner = JobRunner(orchestrator, job_repo, event_bus=bus)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.on_event("startup")
    async def _on_startup():
        await sqlite_client.connect()
        await sqlite_client.init_schema()

    @app.on_event("shutdown")
    async def _on_shutdown():
        await sqlite_client.close()

    app.include_router(build_router(runner=runner, job_repo=job_repo,
                                    event_bus=bus))
    app.include_router(build_files_router(research_dir))
    if fmp_client is not None:
        app.include_router(build_tickers_search_router(fmp_client))

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

    bus = JobEventBus()
    orchestrator = Orchestrator(
        anthropic_client=anthropic_client, fmp_client=fmp_client,
        edgar_client=edgar_client, fred_client=fred_client,
        research_dir=settings.research_dir, cik_resolver=cik_resolver,
        settings=settings, event_bus=bus,
    )
    sqlite = SqliteClient(settings.sqlite_path)
    return build_app(orchestrator=orchestrator,
                     research_dir=settings.research_dir,
                     sqlite_client=sqlite,
                     event_bus=bus,
                     fmp_client=fmp_client)


# uvicorn loads `app` at module import. Load .env first so the guard sees the
# keys; then only construct `app` if both required keys resolved, so pytest can
# still `from backend.main import build_app` without env vars set.
import os as _os
from dotenv import load_dotenv as _load_dotenv

_load_dotenv()
if _os.environ.get("ANTHROPIC_API_KEY") and _os.environ.get("FMP_API_KEY"):
    app = _build_default_app()
