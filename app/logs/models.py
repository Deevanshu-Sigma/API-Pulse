import uuid
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import Boolean, Integer, ForeignKey, DateTime, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class CheckLog(Base):
    __tablename__ = "check_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    monitor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("monitors.id", ondelete="CASCADE"), nullable=False
    )
    checked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )
    status_code: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    response_time_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    is_up: Mapped[bool] = mapped_column(Boolean, nullable=False)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # ── Phase 5: Assertion results ───────────────────────────────────────────
    # Stores the per-rule outcome from the assertions engine.
    # Example value:
    # [
    #   {"rule": {"type": "json_field", "path": "status", "operator": "eq", "value": "ok"},
    #    "passed": true, "detail": null},
    #   {"rule": {"type": "response_time_ms", "operator": "lt", "value": 500},
    #    "passed": false, "detail": "response_time_ms 720 is not < 500"}
    # ]
    assertion_results: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)

    monitor: Mapped["Monitor"] = relationship("Monitor", back_populates="check_logs")
