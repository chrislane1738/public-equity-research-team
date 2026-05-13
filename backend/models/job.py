from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel


class CreateJobRequest(BaseModel):
    ticker: Optional[str] = None
    tickers: Optional[list[str]] = None
    workflow: str = "full-deep-dive"
    question: Optional[str] = None  # used by thesis-check


class JobState(BaseModel):
    id: str
    ticker: str
    workflow: str
    status: str
    current_stage: Optional[str] = None
    stages: dict[str, str] = {}
    rating: Optional[str] = None
    error: Optional[str] = None
    created_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
