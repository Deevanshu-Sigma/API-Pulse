"""
APScheduler engine.

run_check() is the job function fired by the scheduler.  It uses
ping_and_save() from service.py so the ping + persist logic is
defined in exactly one place (not duplicated between here and /trigger).
"""

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.monitors.models import Monitor
from app.monitors.service import ping_and_save
from app.alerts.service import send_alerts, send_recovery_alerts

scheduler = AsyncIOScheduler()

# Grace period: if the scheduler is busy when a job fires, allow it to run
# up to 30 seconds late before skipping it entirely.
_MISFIRE_GRACE_SECONDS = 30


async def run_check(monitor_id: str) -> None:
    """
    Ping a monitor URL, persist the CheckLog, and update monitor status.

    Alert behaviour (state machine):
    - up/pending → down : fire DOWN alerts
    - down → up         : fire RECOVERY alerts
    - anything else     : silent (prevents alert storms on sustained failures)
    """
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Monitor).where(Monitor.id == monitor_id))
        monitor = result.scalar()
        if not monitor or not monitor.is_active:
            return

        previous_status = monitor.status

        # ping_and_save handles ping_url + CheckLog insert + monitor.status update
        ping_result, _log = await ping_and_save(monitor, db)
        # db session committed inside ping_and_save; do NOT use it after this line

    # Fire alerts AFTER the session is closed (alert service opens its own session)
    if previous_status != "down" and not ping_result["is_up"]:
        await send_alerts(monitor, ping_result["error_message"])
    elif previous_status == "down" and ping_result["is_up"]:
        await send_recovery_alerts(monitor)


def add_monitor_job(monitor_id: str, interval_minutes: int) -> None:
    """Register (or replace) a recurring ping job for the given monitor.

    replace_existing=True makes it safe to call on resume or interval update.
    When called for an interval update the current in-progress run is NOT
    interrupted — APScheduler finishes it then adopts the new interval.
    """
    scheduler.add_job(
        run_check,
        trigger="interval",
        minutes=interval_minutes,
        id=str(monitor_id),
        replace_existing=True,
        misfire_grace_time=_MISFIRE_GRACE_SECONDS,
        args=[str(monitor_id)],
    )


def remove_monitor_job(monitor_id: str) -> None:
    """Cancel the scheduler job for a monitor. No-op if the job doesn't exist."""
    try:
        scheduler.remove_job(str(monitor_id))
    except Exception:
        pass
