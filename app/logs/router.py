from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import UUID
from app.database import get_db
from app.users.service import get_current_user
from app.logs.models import CheckLog
from app.logs.schemas import CheckLogResponse

router = APIRouter(prefix="/api/monitors", tags=["Logs"])


# NOTE: /stats route must be declared BEFORE /{monitor_id}/logs to prevent
# FastAPI from treating the literal "stats" string as a UUID path param.
@router.get("/{monitor_id}/logs/stats")
async def get_stats(
    monitor_id: UUID,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return uptime %, average response time, and total check count for a monitor."""
    result = await db.execute(
        select(CheckLog).where(CheckLog.monitor_id == monitor_id)
    )
    logs = result.scalars().all()

    if not logs:
        return {"uptime_percent": 0, "avg_response_ms": 0, "total_checks": 0}

    total = len(logs)
    up_count = sum(1 for log in logs if log.is_up)
    valid_ms = [log.response_time_ms for log in logs if log.response_time_ms is not None]
    avg_ms = sum(valid_ms) / len(valid_ms) if valid_ms else 0

    return {
        "uptime_percent": round((up_count / total) * 100, 2),
        "avg_response_ms": round(avg_ms),
        "total_checks": total,
    }


@router.get("/{monitor_id}/logs", response_model=list[CheckLogResponse])
async def get_logs(
    monitor_id: UUID,
    limit: int = 50,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return the last N check logs for a monitor, newest first."""
    result = await db.execute(
        select(CheckLog)
        .where(CheckLog.monitor_id == monitor_id)
        .order_by(CheckLog.checked_at.desc())
        .limit(limit)
    )
    return result.scalars().all()
