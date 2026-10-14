import uuid
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import String, Boolean, Integer, ForeignKey, DateTime
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class Monitor(Base):
    __tablename__ = "monitors"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    url: Mapped[str] = mapped_column(String, nullable=False)
    method: Mapped[str] = mapped_column(String, default="GET")
    interval_minutes: Mapped[int] = mapped_column(Integer, default=5)
    expected_status: Mapped[int] = mapped_column(Integer, default=200)
    timeout_seconds: Mapped[int] = mapped_column(Integer, default=10)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String, default="pending")
    last_checked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    # ── Phase 3: Auth / Custom Headers ──────────────────────────────────────
    # Stored as a JSON dict where every value is Fernet-encrypted, prefixed
    # with "enc:". Example: {"Authorization": "enc:gAAA...", "x-api-key": "enc:..."}
    # The plaintext is NEVER written to the database.
    headers: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    # ── Phase 4: Request Body ────────────────────────────────────────────────
    # JSON body sent with POST / PUT / PATCH monitors.
    body: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    # ── Phase 5: Response Assertions ────────────────────────────────────────
    # List of assertion rules. Example:
    # [{"type": "json_field", "path": "data.status", "operator": "eq", "value": "active"}]
    assertions: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)

    user: Mapped["User"] = relationship("User", back_populates="monitors")
    check_logs: Mapped[list["CheckLog"]] = relationship(
        "CheckLog", back_populates="monitor", cascade="all, delete-orphan"
    )
    alert_channels: Mapped[list["AlertChannel"]] = relationship(
        "AlertChannel", back_populates="monitor", cascade="all, delete-orphan"
    )
