"""Filesystem-backed routes for the right panel.

Lists ticker subdirectories under RESEARCH_DIR, walks one ticker's folder tree,
and serves individual artifact files with the right MIME type. Path traversal
is rejected at the boundary (no `..`, no absolute paths, no symlink escape).
"""
import mimetypes
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse

# Office formats are not registered by default on every system.
mimetypes.add_type("application/vnd.openxmlformats-officedocument.presentationml.presentation", ".pptx")
mimetypes.add_type("application/vnd.openxmlformats-officedocument.wordprocessingml.document", ".docx")
mimetypes.add_type("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", ".xlsx")
mimetypes.add_type("text/markdown", ".md")


def build_files_router(research_dir: Path) -> APIRouter:
    router = APIRouter()
    base = Path(research_dir).resolve()

    @router.get("/tickers")
    def list_tickers():
        if not base.exists():
            return {"tickers": []}
        out = []
        for entry in sorted(base.iterdir()):
            if not entry.is_dir() or entry.name.startswith("_") or entry.name.startswith("."):
                continue
            out.append(entry.name)
        return {"tickers": out}

    @router.get("/tickers/{ticker}/files")
    def list_ticker_files(ticker: str):
        ticker_dir = (base / ticker).resolve()
        if not _is_within(base, ticker_dir) or not ticker_dir.exists():
            raise HTTPException(404, "ticker not found")
        return {"ticker": ticker, "tree": _walk(ticker_dir, base)}

    @router.get("/files")
    def get_file(path: str = Query(..., description="path relative to RESEARCH_DIR")):
        if not path or path.startswith("/") or ".." in Path(path).parts:
            raise HTTPException(400, "invalid path")
        target = (base / path).resolve()
        if not _is_within(base, target):
            raise HTTPException(400, "invalid path")
        if not target.exists() or not target.is_file():
            raise HTTPException(404, "file not found")
        media_type, _ = mimetypes.guess_type(target.name)
        return FileResponse(target, media_type=media_type or "application/octet-stream",
                            filename=target.name)

    return router


def _walk(node: Path, base: Path) -> list[dict]:
    out = []
    for entry in sorted(node.iterdir()):
        if entry.name.startswith("."):
            continue
        rel = entry.relative_to(base).as_posix()
        if entry.is_dir():
            out.append({
                "name": entry.name,
                "path": rel,
                "kind": "dir",
                "children": _walk(entry, base),
            })
        else:
            out.append({
                "name": entry.name,
                "path": rel,
                "kind": "file",
                "size": entry.stat().st_size,
                "ext": entry.suffix.lower().lstrip("."),
            })
    return out


def _is_within(base: Path, target: Path) -> bool:
    try:
        target.relative_to(base)
    except ValueError:
        return False
    return True
