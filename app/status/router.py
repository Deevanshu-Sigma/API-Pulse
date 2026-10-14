"""
Public Status Page — Phase 8.

Two endpoints, both require NO authentication:

  GET /status/{username}
      Returns a rendered HTML status page (what customers visit during incidents).
      username = email prefix, e.g. "john" for john@example.com

  GET /api/status/{username}
      Returns the same data as JSON (useful for embedding into other dashboards
      or for recruiters to verify with curl/Postman).
"""

from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.database import get_db
from app.users.models import User
from app.monitors.models import Monitor
from app.logs.models import CheckLog

router = APIRouter(tags=["Public Status Page"])


# ── Helpers ───────────────────────────────────────────────────────────────────

def _time_ago(dt: datetime | None) -> str:
    """Return a human-readable 'X ago' string for a UTC datetime."""
    if dt is None:
        return "never"
    # Make sure dt is offset-aware so we can subtract
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    diff = datetime.now(timezone.utc) - dt
    seconds = int(diff.total_seconds())
    if seconds < 60:
        return f"{seconds}s ago"
    elif seconds < 3600:
        return f"{seconds // 60}m ago"
    elif seconds < 86400:
        return f"{seconds // 3600}h ago"
    else:
        return f"{seconds // 86400}d ago"


async def _get_user_and_monitors(username: str, db: AsyncSession):
    """
    Resolve username → User → active monitors.
    Raises 404 if the username doesn't match any registered email.
    """
    # username is the local part before '@' — case-insensitive match
    result = await db.execute(
        select(User).where(
            func.lower(func.split_part(User.email, "@", 1)) == username.lower()
        )
    )
    user = result.scalar()
    if not user:
        raise HTTPException(status_code=404, detail=f"No status page found for '{username}'")

    result = await db.execute(
        select(Monitor).where(
            Monitor.user_id == user.id,
            Monitor.is_active == True,
            Monitor.is_deleted == False,
        ).order_by(Monitor.created_at)
    )
    monitors = result.scalars().all()
    return user, monitors


# ── JSON API endpoint ─────────────────────────────────────────────────────────

@router.get("/api/status/{username}", summary="Public status — JSON")
async def status_json(
    username: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Public JSON representation of a user's monitor statuses.
    No authentication required.

    Response shape:
    {
      "owner": "john@example.com",
      "overall": "operational" | "degraded" | "outage",
      "monitors": [
        {
          "name": "...",
          "url": "...",
          "status": "up" | "down" | "pending",
          "last_checked_at": "ISO datetime | null",
          "last_checked_ago": "2m ago",
          "response_time_ms": 142
        }
      ]
    }
    """
    user, monitors = await _get_user_and_monitors(username, db)

    monitor_data = []
    for m in monitors:
        # Fetch the most recent log for response time
        log_result = await db.execute(
            select(CheckLog)
            .where(CheckLog.monitor_id == m.id)
            .order_by(CheckLog.checked_at.desc())
            .limit(1)
        )
        latest_log = log_result.scalar()

        monitor_data.append({
            "name": m.name,
            "url": m.url,
            "status": m.status,
            "last_checked_at": m.last_checked_at.isoformat() if m.last_checked_at else None,
            "last_checked_ago": _time_ago(m.last_checked_at),
            "response_time_ms": latest_log.response_time_ms if latest_log else None,
        })

    statuses = [m["status"] for m in monitor_data]
    if all(s == "up" for s in statuses):
        overall = "operational"
    elif any(s == "down" for s in statuses):
        overall = "outage" if all(s == "down" for s in statuses) else "degraded"
    else:
        overall = "pending"

    return {
        "owner": user.email,
        "overall": overall,
        "monitors": monitor_data,
    }


# ── HTML status page ──────────────────────────────────────────────────────────

@router.get("/status/{username}", response_class=HTMLResponse, summary="Public status page")
async def status_page(
    username: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Public HTML status page — no authentication required.
    Customers visit this page during incidents.
    """
    user, monitors = await _get_user_and_monitors(username, db)

    # ── Gather monitor display data ───────────────────────────────────────────
    monitor_rows = []
    for m in monitors:
        log_result = await db.execute(
            select(CheckLog)
            .where(CheckLog.monitor_id == m.id)
            .order_by(CheckLog.checked_at.desc())
            .limit(1)
        )
        latest_log = log_result.scalar()
        response_ms = latest_log.response_time_ms if latest_log else None

        monitor_rows.append({
            "name": m.name,
            "url": m.url,
            "status": m.status,
            "ago": _time_ago(m.last_checked_at),
            "response_ms": response_ms,
        })

    # ── Overall banner ────────────────────────────────────────────────────────
    statuses = [r["status"] for r in monitor_rows]
    if not statuses:
        overall_text  = "No monitors configured"
        overall_color = "#64748b"
        overall_icon  = "⬜"
    elif all(s == "up" for s in statuses):
        overall_text  = "All Systems Operational"
        overall_color = "#22c55e"
        overall_icon  = "✅"
    elif all(s == "down" for s in statuses):
        overall_text  = "Major Outage — All Systems Down"
        overall_color = "#ef4444"
        overall_icon  = "🔴"
    else:
        down_count    = sum(1 for s in statuses if s == "down")
        overall_text  = f"Partial Outage — {down_count} system(s) down"
        overall_color = "#f59e0b"
        overall_icon  = "⚠️"

    # ── Build monitor card HTML ───────────────────────────────────────────────
    def _status_dot_color(status: str) -> str:
        return {"up": "#22c55e", "down": "#ef4444"}.get(status, "#f59e0b")

    def _status_label(status: str) -> str:
        return {"up": "Operational", "down": "Outage", "pending": "Checking…"}.get(status, status.upper())

    cards_html = ""
    for row in monitor_rows:
        dot  = _status_dot_color(row["status"])
        lbl  = _status_label(row["status"])
        ms   = f"{row['response_ms']} ms" if row["response_ms"] is not None else "—"
        cards_html += f"""
        <div class="monitor-card">
          <div class="monitor-left">
            <span class="status-dot" style="background:{dot};box-shadow:0 0 8px {dot}80;"></span>
            <div class="monitor-info">
              <span class="monitor-name">{row['name']}</span>
              <span class="monitor-url">{row['url']}</span>
            </div>
          </div>
          <div class="monitor-right">
            <span class="response-badge">{ms}</span>
            <span class="checked-ago">{row['ago']}</span>
            <span class="status-label" style="color:{dot};">{lbl}</span>
          </div>
        </div>"""

    if not cards_html:
        cards_html = '<p class="no-monitors">No active monitors configured.</p>'

    # ── Render full HTML page ─────────────────────────────────────────────────
    now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Status — {username}</title>
  <meta name="description" content="Live uptime status page for {username}. Check if all systems are operational." />
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet" />
  <style>
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}

    body {{
      font-family: 'Inter', -apple-system, sans-serif;
      background: #080b14;
      color: #f1f5f9;
      min-height: 100vh;
      padding: 40px 20px 80px;
    }}

    .container {{
      max-width: 720px;
      margin: 0 auto;
    }}

    /* ── Header ── */
    .site-header {{
      display: flex;
      align-items: center;
      gap: 12px;
      margin-bottom: 40px;
    }}
    .brand-dot {{
      width: 10px; height: 10px;
      border-radius: 50%;
      background: #6366f1;
      box-shadow: 0 0 12px #6366f180;
    }}
    .brand-name {{
      font-size: 14px;
      font-weight: 600;
      color: #6366f1;
      letter-spacing: 0.5px;
    }}
    .brand-sep {{
      color: #334155;
      margin: 0 4px;
    }}
    .owner-name {{
      font-size: 14px;
      color: #64748b;
    }}

    /* ── Overall banner ── */
    .overall-banner {{
      background: rgba(255,255,255,0.03);
      border: 1px solid rgba(255,255,255,0.07);
      border-radius: 16px;
      padding: 28px 32px;
      margin-bottom: 32px;
      display: flex;
      align-items: center;
      gap: 16px;
    }}
    .overall-icon {{ font-size: 28px; line-height: 1; }}
    .overall-text {{
      font-size: 20px;
      font-weight: 700;
      color: {overall_color};
    }}
    .overall-sub {{
      font-size: 13px;
      color: #64748b;
      margin-top: 4px;
    }}

    /* ── Section heading ── */
    .section-heading {{
      font-size: 12px;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 1px;
      color: #64748b;
      margin-bottom: 12px;
    }}

    /* ── Monitor cards ── */
    .monitor-card {{
      background: rgba(255,255,255,0.03);
      border: 1px solid rgba(255,255,255,0.07);
      border-radius: 12px;
      padding: 16px 20px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
      margin-bottom: 10px;
      transition: border-color 0.2s;
    }}
    .monitor-card:hover {{
      border-color: rgba(255,255,255,0.14);
    }}
    .monitor-left {{
      display: flex;
      align-items: center;
      gap: 14px;
      min-width: 0;
    }}
    .status-dot {{
      width: 11px;
      height: 11px;
      border-radius: 50%;
      flex-shrink: 0;
    }}
    .monitor-info {{
      display: flex;
      flex-direction: column;
      min-width: 0;
    }}
    .monitor-name {{
      font-size: 15px;
      font-weight: 600;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }}
    .monitor-url {{
      font-size: 12px;
      color: #64748b;
      margin-top: 2px;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }}
    .monitor-right {{
      display: flex;
      align-items: center;
      gap: 14px;
      flex-shrink: 0;
    }}
    .response-badge {{
      font-size: 12px;
      font-weight: 500;
      color: #94a3b8;
      background: rgba(255,255,255,0.05);
      border-radius: 6px;
      padding: 3px 8px;
    }}
    .checked-ago {{
      font-size: 12px;
      color: #475569;
    }}
    .status-label {{
      font-size: 13px;
      font-weight: 600;
      min-width: 90px;
      text-align: right;
    }}
    .no-monitors {{
      color: #475569;
      font-size: 14px;
      text-align: center;
      padding: 40px;
    }}

    /* ── Footer ── */
    .page-footer {{
      margin-top: 48px;
      text-align: center;
      font-size: 12px;
      color: #334155;
    }}
    .page-footer a {{
      color: #6366f1;
      text-decoration: none;
    }}
    .last-updated {{
      margin-top: 8px;
      font-size: 11px;
      color: #1e293b;
    }}
  </style>
</head>
<body>
  <div class="container">

    <!-- Header -->
    <header class="site-header">
      <span class="brand-dot"></span>
      <span class="brand-name">Uptime Monitor</span>
      <span class="brand-sep">/</span>
      <span class="owner-name">{username}</span>
    </header>

    <!-- Overall status banner -->
    <div class="overall-banner">
      <span class="overall-icon">{overall_icon}</span>
      <div>
        <div class="overall-text">{overall_text}</div>
        <div class="overall-sub">{len(monitor_rows)} monitor(s) tracked</div>
      </div>
    </div>

    <!-- Monitor list -->
    <p class="section-heading">Services</p>
    {cards_html}

    <!-- Footer -->
    <footer class="page-footer">
      Powered by <a href="/">Uptime Monitor</a>
      <div class="last-updated">Last updated: {now_utc}</div>
    </footer>

  </div>
</body>
</html>"""
