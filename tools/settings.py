"""Application settings — dotenv-loaded keys only.

Replaces backend/config.py (which carried FastAPI-era fields like SQLITE_PATH,
PORT_BACKEND, MAX_CONCURRENT_AGENTS). The new architecture is in-process inside
Claude Code; no server, no DB, no concurrency primitives.
"""
import os
from pathlib import Path

from dotenv import load_dotenv

_REPO_ROOT = Path(__file__).resolve().parent.parent

# Load .env into os.environ with override=False so that values already present
# in os.environ (e.g. set by tests via monkeypatch) are preserved.  We mark
# the sentinel _DOTENV_LOADED in os.environ so that importlib.reload() skips
# the load_dotenv call — this ensures monkeypatch.delenv() is respected across
# reloads without the file re-populating the deleted key.
if not os.environ.get("_TOOLS_SETTINGS_LOADED"):
    load_dotenv(_REPO_ROOT / ".env", override=False)
    os.environ["_TOOLS_SETTINGS_LOADED"] = "1"


def _required(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(
            f"{name} is required. Set it in .env at the repo root. "
            f"See .env.example for the template."
        )
    return value


FMP_API_KEY: str = _required("FMP_API_KEY")
FRED_API_KEY: str = os.environ.get("FRED_API_KEY", "")
SEC_EDGAR_USER_AGENT: str = _required("SEC_EDGAR_USER_AGENT")
ANTHROPIC_API_KEY: str = os.environ.get("ANTHROPIC_API_KEY", "")  # optional, unused in skill arch

RESEARCH_DIR: Path = Path(
    os.environ.get("RESEARCH_DIR", str(Path.home() / "Documents" / "equity-research"))
).expanduser()
CACHE_DIR: Path = RESEARCH_DIR / "_cache"
