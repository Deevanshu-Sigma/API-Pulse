from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import UUID
from typing import Annotated
from pydantic import Field
from app.database import get_db
from app.users.service import get_current_user
from app.monitors.models import Monitor
from app.alerts.models import AlertChannel
from app.alerts.schemas import (
    AlertChannelCreateSlack,
    AlertChannelCreateDiscord,
    AlertChannelCreateEmail,
    AlertChannelResponse,
)
from typing import Union

router = APIRouter(prefix="/api/monitors", tags=["Alerts"])

# Discriminated union type alias for use in the endpoint signature
AlertChannelCreate = Annotated[
    Union[AlertChannelCreateSlack, AlertChannelCreateDiscord, AlertChannelCreateEmail],
    Field(discriminator="channel_type"),
]


@router.post("/{monitor_id}/alerts", response_model=AlertChannelResponse, status_code=201)
async def add_alert_channel(
    monitor_id: UUID,
    data: AlertChannelCreate,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Add a Slack / Discord / Email alert channel to a monitor.

    - **slack**: `{"channel_type": "slack", "config": {"webhook_url": "https://hooks.slack.com/..."}}`
    - **discord**: `{"channel_type": "discord", "config": {"webhook_url": "https://discord.com/api/webhooks/..."}}`
    - **email**: `{"channel_type": "email", "config": {"to": "you@example.com"}}`
    """
    result = await db.execute(
        select(Monitor).where(Monitor.id == monitor_id, Monitor.user_id == user_id)
    )
    if not result.scalar():
        raise HTTPException(status_code=404, detail="Monitor not found")

    # Serialize validated Pydantic config model to plain dict for JSONB storage
    config_dict = data.config.model_dump(mode="json")

    channel = AlertChannel(
        monitor_id=monitor_id,
        channel_type=data.channel_type,
        config=config_dict,
    )
    db.add(channel)
    await db.commit()
    await db.refresh(channel)
    return channel


@router.get("/{monitor_id}/alerts", response_model=list[AlertChannelResponse])
async def list_alert_channels(
    monitor_id: UUID,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all alert channels for a monitor (sensitive config values are masked)."""
    result = await db.execute(
        select(AlertChannel).where(AlertChannel.monitor_id == monitor_id)
    )
    return result.scalars().all()


@router.delete("/{monitor_id}/alerts/{channel_id}", status_code=204)
async def delete_alert_channel(
    monitor_id: UUID,
    channel_id: UUID,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Remove an alert channel."""
    result = await db.execute(
        select(AlertChannel).where(
            AlertChannel.id == channel_id,
            AlertChannel.monitor_id == monitor_id,
        )
    )
    channel = result.scalar()
    if not channel:
        raise HTTPException(status_code=404, detail="Alert channel not found")
    await db.delete(channel)
    await db.commit()
