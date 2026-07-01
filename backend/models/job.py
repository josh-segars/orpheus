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


class JobSummary(BaseModel):
    """One row in the client's reports list (GET /jobs, ORPHEUS-81).

    Deliberately lightweight — no result payload. `band` is the composite
    signal band from the scores row, present only for complete jobs (null
    for pending/running/failed, and for complete jobs whose scores row is
    missing — defensive, shouldn't occur in practice).

    No `updated_at`: the jobs table doesn't have that column (it has
    started_at / completed_at). The first deploy selected it and 500'd
    against the live schema — the ORPHEUS-59/61 lesson re-learned.
    """

    id: str
    state: str  # pending | running | complete | failed
    created_at: datetime
    band: Optional[str] = None
    # ORPHEUS-88: true when the report was produced on incomplete/degraded
    # data (allowed-through EMPTY_DATA critical or data-limitation warnings).
    # Denormalized onto the job row by the worker at completion so the
    # reports list can chip it without reading quality_report. Null/false
    # for pre-ORPHEUS-88 jobs and non-complete jobs.
    data_limited: bool = False
