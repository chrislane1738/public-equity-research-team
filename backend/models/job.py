from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel


class CreateJobRequest(BaseModel):
    ticker: str
    workflow: str = "full-deep-dive"


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
