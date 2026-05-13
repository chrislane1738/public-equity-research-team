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
