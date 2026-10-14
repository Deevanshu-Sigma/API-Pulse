"""
Monitor CRUD + scheduler integration.

Phase 3: encrypted headers / auth
Phase 4: request body + /trigger returns real CheckLogResponse
Phase 5: response assertions wired through create/update/trigger
"""

import base64
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import UUID
from typing import Optional

from app.database import get_db
from app.users.service import get_current_user
from app.monitors.models import Monitor
from app.logs.models import CheckLog
from app.monitors.schemas import AuthConfig, MonitorCreate, MonitorUpdate, MonitorResponse
from app.logs.schemas import CheckLogResponse
from app.monitors.scheduler import add_monitor_job, remove_monitor_job
from app.monitors.service import ping_and_save
from app.alerts.service import send_alerts, send_recovery_alerts
from app.core.security import encrypt_value

router = APIRouter(prefix="/api/monitors", tags=["Monitors"])


# ── Encryption helper ────────────────────────────────────────────────────────

def _build_encrypted_headers(
    raw_headers: Optional[dict],
    auth: Optional[AuthConfig],
) -> Optional[dict]:
    """
    Merge user-supplied raw headers with the auth shortcut and encrypt every
    value with Fernet.

    Encryption convention used throughout the codebase:
        stored value = "enc:" + encrypt_value(plaintext)

    The "enc:" prefix lets service.py know which values need decryption,
    which is important if we ever allow non-sensitive headers like Content-Type
    that don't need to be encrypted.

    Returns None if no headers or auth were provided.
    """
    final: dict[str, str] = dict(raw_headers or {})

    if auth:
        final["X-Kae-Auth-Type"] = auth.type

        if auth.type == "bearer" and auth.token:
            final["Authorization"] = f"Bearer {auth.token}"

        elif auth.type == "basic" and auth.username and auth.password:
            credentials = base64.b64encode(
                f"{auth.username}:{auth.password}".encode()
            ).decode()
            final["Authorization"] = f"Basic {credentials}"

        elif auth.type == "api_key" and auth.key_name and auth.key_value:
            final[auth.key_name] = auth.key_value

    if not final:
        return None

    # Encrypt every header value before writing to DB.
    # Keep X-Kae-Auth-Type unencrypted so we can read it easily without keys.
    encrypted = {}
    for k, v in final.items():
        if k == "X-Kae-Auth-Type":
            encrypted[k] = v
        else:
            encrypted[k] = f"enc:{encrypt_value(v)}"
    return encrypted


def _monitor_to_response(monitor: Monitor) -> MonitorResponse:
    auth_type = monitor.headers.get("X-Kae-Auth-Type") if monitor.headers else None
    
    # has_auth is True if there are headers other than just the type metadata
    has_auth = False
    if monitor.headers:
        has_auth = any(k != "X-Kae-Auth-Type" for k in monitor.headers)
        
    return MonitorResponse(
        id=monitor.id,
        name=monitor.name,
        url=monitor.url,
        method=monitor.method,
        status=monitor.status,
        interval_minutes=monitor.interval_minutes,
        expected_status=monitor.expected_status,
        timeout_seconds=monitor.timeout_seconds,
        is_active=monitor.is_active,
        last_checked_at=monitor.last_checked_at,
        created_at=monitor.created_at,
        has_auth=has_auth,
        auth_type=auth_type,
        has_assertions=bool(monitor.assertions),
        assertions=monitor.assertions,
        body=monitor.body,
    )


# ── CRUD endpoints ───────────────────────────────────────────────────────────

@router.get("", response_model=list[MonitorResponse])
async def list_monitors(
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all monitors belonging to the current user (excluding soft-deleted)."""
    result = await db.execute(
        select(Monitor).where(Monitor.user_id == user_id, Monitor.is_deleted == False)
    )
    return [_monitor_to_response(m) for m in result.scalars().all()]


@router.post("", response_model=MonitorResponse, status_code=status.HTTP_201_CREATED)
async def create_monitor(
    data: MonitorCreate,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Create a new monitor.

    - If 'auth' or 'headers' are provided, values are encrypted with Fernet
      before being saved.  Raw secrets are NEVER written to the database.
    - Immediately registers a scheduler ping job on creation.
    """
    encrypted_headers = _build_encrypted_headers(data.headers, data.auth)

    # Serialize AssertionRule objects to plain dicts for JSONB storage
    serialized_assertions = (
        [a.model_dump() for a in data.assertions] if data.assertions else None
    )

    monitor = Monitor(
        user_id=user_id,
        name=data.name,
        url=data.url,
        method=data.method,
        interval_minutes=data.interval_minutes,
        expected_status=data.expected_status,
        timeout_seconds=data.timeout_seconds,
        headers=encrypted_headers,
        body=data.body,
        assertions=serialized_assertions,  # ← Phase 5
    )
    db.add(monitor)
    await db.commit()
    await db.refresh(monitor)
    add_monitor_job(str(monitor.id), monitor.interval_minutes)
    return _monitor_to_response(monitor)


@router.get("/{monitor_id}", response_model=MonitorResponse)
async def get_monitor(
    monitor_id: UUID,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a single monitor by ID."""
    result = await db.execute(
        select(Monitor).where(
            Monitor.id == monitor_id,
            Monitor.user_id == user_id,
            Monitor.is_deleted == False,
        )
    )
    monitor = result.scalar()
    if not monitor:
        raise HTTPException(status_code=404, detail="Monitor not found")
    return _monitor_to_response(monitor)


@router.patch("/{monitor_id}", response_model=MonitorResponse)
async def update_monitor(
    monitor_id: UUID,
    data: MonitorUpdate,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Update monitor fields.

    - If 'auth' or 'headers' are provided, the stored headers dict is
      REPLACED with the newly encrypted values.
    - If interval_minutes is changed, the scheduler job is re-registered.
    """
    result = await db.execute(
        select(Monitor).where(
            Monitor.id == monitor_id,
            Monitor.user_id == user_id,
            Monitor.is_deleted == False,
        )
    )
    monitor = result.scalar()
    if not monitor:
        raise HTTPException(status_code=404, detail="Monitor not found")

    updates = data.model_dump(exclude_unset=True, exclude={"auth", "headers", "assertions"})
    for field, value in updates.items():
        setattr(monitor, field, value)

    # Handle auth / headers update separately (needs encryption).
    # We use model_fields_set (not `is not None`) so we can distinguish:
    #   - field NOT sent at all     → leave existing headers untouched
    #   - field sent as null        → explicitly clear auth (wipe headers)
    #   - field sent with a value   → replace with newly encrypted headers
    auth_fields_set = data.model_fields_set & {"auth", "headers"}
    if auth_fields_set:
        # At least one of auth / headers was explicitly included in the request.
        # Build new encrypted headers (returns None if both are null/empty → clears auth).
        monitor.headers = _build_encrypted_headers(
            data.headers if "headers" in data.model_fields_set else None,
            data.auth    if "auth"    in data.model_fields_set else None,
        )

    # Handle assertions update separately (needs serialization).
    if "assertions" in data.model_fields_set:
        if data.assertions is None:
            monitor.assertions = None
        else:
            monitor.assertions = [a.model_dump() for a in data.assertions]

    await db.commit()
    await db.refresh(monitor)

    # Re-register job if interval changed and monitor is still active
    if "interval_minutes" in data.model_dump(exclude_unset=True) and monitor.is_active:
        add_monitor_job(str(monitor.id), monitor.interval_minutes)

    return _monitor_to_response(monitor)


@router.delete("/{monitor_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_monitor(
    monitor_id: UUID,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Soft-delete a monitor and cancel its scheduler job."""
    result = await db.execute(
        select(Monitor).where(
            Monitor.id == monitor_id,
            Monitor.user_id == user_id,
            Monitor.is_deleted == False,
        )
    )
    monitor = result.scalar()
    if not monitor:
        raise HTTPException(status_code=404, detail="Monitor not found")
    remove_monitor_job(str(monitor_id))
    monitor.is_deleted = True
    monitor.is_active = False
    await db.commit()


@router.post("/{monitor_id}/pause", response_model=MonitorResponse)
async def pause_monitor(
    monitor_id: UUID,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Pause a monitor: set is_active=False and cancel its scheduler job."""
    result = await db.execute(
        select(Monitor).where(
            Monitor.id == monitor_id,
            Monitor.user_id == user_id,
            Monitor.is_deleted == False,
        )
    )
    monitor = result.scalar()
    if not monitor:
        raise HTTPException(status_code=404, detail="Monitor not found")
    monitor.is_active = False
    await db.commit()
    await db.refresh(monitor)
    remove_monitor_job(str(monitor_id))
    return _monitor_to_response(monitor)


@router.post("/{monitor_id}/resume", response_model=MonitorResponse)
async def resume_monitor(
    monitor_id: UUID,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Resume a paused monitor: set is_active=True and re-register scheduler job."""
    result = await db.execute(
        select(Monitor).where(
            Monitor.id == monitor_id,
            Monitor.user_id == user_id,
            Monitor.is_deleted == False,
        )
    )
    monitor = result.scalar()
    if not monitor:
        raise HTTPException(status_code=404, detail="Monitor not found")
    monitor.is_active = True
    await db.commit()
    await db.refresh(monitor)
    add_monitor_job(str(monitor.id), monitor.interval_minutes)
    return _monitor_to_response(monitor)


@router.post(
    "/{monitor_id}/trigger",
    response_model=CheckLogResponse,
    tags=["Monitors"],
    summary="Trigger an immediate check",
)
async def trigger_check(
    monitor_id: UUID,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Run an immediate on-demand check for this monitor and return the result.

    Unlike waiting for the scheduler, this fires right now and returns
    a full CheckLogResponse (status_code, response_time_ms, is_up,
    error_message) so you can validate your auth config or POST body
    without waiting for the next scheduled interval.

    Alert transitions (up→down, down→up) are fired the same way as the
    scheduled checks.
    """
    result = await db.execute(
        select(Monitor).where(
            Monitor.id == monitor_id,
            Monitor.user_id == user_id,
            Monitor.is_deleted == False,
        )
    )
    monitor = result.scalar()
    if not monitor:
        raise HTTPException(status_code=404, detail="Monitor not found")

    previous_status = monitor.status

    # ping_and_save commits the log and updates monitor.status inside db
    ping_result, log = await ping_and_save(monitor, db)

    # Fire alerts (same transition logic as the scheduler)
    if previous_status != "down" and not ping_result["is_up"]:
        await send_alerts(monitor, ping_result["error_message"])
    elif previous_status == "down" and ping_result["is_up"]:
        await send_recovery_alerts(monitor)

    return log
