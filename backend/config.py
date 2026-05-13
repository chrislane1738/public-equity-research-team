"""Application settings loaded from environment variables."""
import os
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    anthropic_api_key: str
    fmp_api_key: str
    fred_api_key: str = ""
    sec_edgar_user_agent: str

    research_dir: Path = Path.home() / "Documents" / "equity-research"
    anthropic_model: str = "claude-opus-4-7"
    sqlite_path: Path = Path("./backend/db/research.sqlite")

    port_backend: int = 8000
    port_frontend: int = 3000
    max_concurrent_agents: int = 5
    daily_spend_warn_usd: float = 10.0

    @field_validator("research_dir", "sqlite_path", mode="before")
    @classmethod
    def expand_user(cls, v):
        return Path(str(v)).expanduser()

    def ticker_dir(self, ticker: str) -> Path:
        return self.research_dir / ticker.upper()

    def model_for(self, agent: str) -> str:
        """Return the Anthropic model id for `agent`, honoring ANTHROPIC_MODEL_<AGENT> env override."""
        env_key = f"ANTHROPIC_MODEL_{agent.upper()}"
        return os.environ.get(env_key) or self.anthropic_model


def get_settings() -> Settings:
    return Settings()
