from pydantic import BaseModel
from uuid import UUID
from datetime import datetime
from typing import Optional, Any


class CheckLogResponse(BaseModel):
    id: UUID
    monitor_id: UUID
    checked_at: datetime
    status_code: Optional[int]
    response_time_ms: Optional[int]
    is_up: bool
    error_message: Optional[str]

    # Phase 5 — per-assertion pass/fail detail
    # Each item: {"rule": {...}, "passed": bool, "detail": str | null}
    assertion_results: Optional[list[dict[str, Any]]] = None

    class Config:
        from_attributes = True
