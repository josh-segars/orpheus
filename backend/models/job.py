from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class Job(BaseModel):
    id: str
    state: str  # pending | running | complete | failed
    created_at: datetime
    updated_at: Optional[datetime] = None
    client_id: Optional[str] = None
    result: Optional[dict] = None
    error: Optional[str] = None
