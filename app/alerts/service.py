import httpx
import aiosmtplib
from email.mime.text import MIMEText
from app.core.config import settings


async def send_alerts(monitor, error: str) -> None:
    """Dispatch DOWN alerts to all configured channels for this monitor.

    Opens its own fresh DB session to avoid using the scheduler's
    already-committed/expired session.
    """
    from sqlalchemy import select
    from app.alerts.models import AlertChannel
    from app.database import AsyncSessionLocal

    print(f"[alerter] DOWN alert triggered for monitor '{monitor.name}' ({monitor.id})")

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(AlertChannel).where(AlertChannel.monitor_id == monitor.id)
        )
        channels = result.scalars().all()

    print(f"[alerter] Found {len(channels)} alert channel(s) for monitor '{monitor.name}'")

    for channel in channels:
        print(f"[alerter] Sending {channel.channel_type} DOWN alert to config={channel.config}")
        try:
            if channel.channel_type == "slack":
                await send_slack(
                    str(channel.config["webhook_url"]),
                    monitor.name,
                    monitor.url,
                    error,
                )
            elif channel.channel_type == "discord":
                await send_discord(
                    str(channel.config["webhook_url"]),
                    monitor.name,
                    monitor.url,
                    error,
                )
            elif channel.channel_type == "email":
                await send_email(
                    channel.config["to"],
                    monitor.name,
                    monitor.url,
                    error,
                )
            print(f"[alerter] {channel.channel_type} DOWN alert sent OK")
        except Exception as e:
            print(f"[alerter] FAILED to send {channel.channel_type} DOWN alert: {type(e).__name__}: {e}")


async def send_recovery_alerts(monitor) -> None:
    """Dispatch UP/recovery alerts when a monitor transitions from down → up.

    Opens its own fresh DB session (same pattern as send_alerts).
    """
    from sqlalchemy import select
    from app.alerts.models import AlertChannel
    from app.database import AsyncSessionLocal

    print(f"[alerter] RECOVERY alert triggered for monitor '{monitor.name}' ({monitor.id})")

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(AlertChannel).where(AlertChannel.monitor_id == monitor.id)
        )
        channels = result.scalars().all()

    print(f"[alerter] Found {len(channels)} alert channel(s) for monitor '{monitor.name}'")

    for channel in channels:
        print(f"[alerter] Sending {channel.channel_type} RECOVERY alert")
        try:
            if channel.channel_type == "slack":
                await send_slack_recovery(
                    str(channel.config["webhook_url"]),
                    monitor.name,
                    monitor.url,
                )
            elif channel.channel_type == "discord":
                await send_discord_recovery(
                    str(channel.config["webhook_url"]),
                    monitor.name,
                    monitor.url,
                )
            elif channel.channel_type == "email":
                await send_email_recovery(
                    channel.config["to"],
                    monitor.name,
                    monitor.url,
                )
            print(f"[alerter] {channel.channel_type} RECOVERY alert sent OK")
        except Exception as e:
            print(f"[alerter] FAILED to send {channel.channel_type} RECOVERY alert: {type(e).__name__}: {e}")


# ---------------------------------------------------------------------------
# DOWN alert senders
# ---------------------------------------------------------------------------

async def send_slack(webhook_url: str, name: str, url: str, error: str) -> None:
    async with httpx.AsyncClient() as client:
        await client.post(webhook_url, json={
            "text": f"🔴 *Monitor DOWN*: {name}\n*URL:* {url}\n*Error:* {error}"
        })


async def send_discord(webhook_url: str, name: str, url: str, error: str) -> None:
    async with httpx.AsyncClient() as client:
        await client.post(webhook_url, json={
            "content": f"🔴 **Monitor DOWN**: {name}\nURL: {url}\nError: {error}"
        })


async def send_email(to: str, name: str, url: str, error: str) -> None:
    message = MIMEText(
        f"Your monitor '{name}' is DOWN.\nURL: {url}\nError: {error}", "plain"
    )
    message["Subject"] = f"[DOWN] {name} is not responding"
    message["From"] = settings.SMTP_FROM
    message["To"] = to
    await aiosmtplib.send(
        message,
        hostname=settings.SMTP_HOST,
        port=settings.SMTP_PORT,
        username=settings.SMTP_USER,
        password=settings.SMTP_PASSWORD,
        start_tls=True,
    )


# ---------------------------------------------------------------------------
# RECOVERY alert senders
# ---------------------------------------------------------------------------

async def send_slack_recovery(webhook_url: str, name: str, url: str) -> None:
    async with httpx.AsyncClient() as client:
        await client.post(webhook_url, json={
            "text": f"🟢 *Monitor RECOVERED*: {name}\n*URL:* {url}\n*Status:* Back online ✅"
        })


async def send_discord_recovery(webhook_url: str, name: str, url: str) -> None:
    async with httpx.AsyncClient() as client:
        await client.post(webhook_url, json={
            "content": f"🟢 **Monitor RECOVERED**: {name}\nURL: {url}\nStatus: Back online ✅"
        })


async def send_email_recovery(to: str, name: str, url: str) -> None:
    message = MIMEText(
        f"Good news! Your monitor '{name}' has recovered.\nURL: {url}\nStatus: Back online ✅",
        "plain",
    )
    message["Subject"] = f"[RECOVERED] {name} is back online"
    message["From"] = settings.SMTP_FROM
    message["To"] = to
    await aiosmtplib.send(
        message,
        hostname=settings.SMTP_HOST,
        port=settings.SMTP_PORT,
        username=settings.SMTP_USER,
        password=settings.SMTP_PASSWORD,
        start_tls=True,
    )
