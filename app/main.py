import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select
from app.monitors.scheduler import scheduler, add_monitor_job
from app.database import AsyncSessionLocal
from app.monitors.models import Monitor
from app.users.router import router as users_router
from app.monitors.router import router as monitors_router
from app.logs.router import router as logs_router
from app.alerts.router import router as alerts_router
from app.status.router import router as status_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start scheduler on boot, re-register all active monitor jobs, shut down cleanly."""
    scheduler.start()

    # Re-register jobs for all active monitors after a server restart.
    # APScheduler jobs are in-memory only; they don't survive restarts.
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Monitor).where(Monitor.is_active == True))
        for m in result.scalars().all():
            add_monitor_job(str(m.id), m.interval_minutes)

    yield

    scheduler.shutdown()


app = FastAPI(title="Uptime Monitor API", version="1.0.0", lifespan=lifespan)

# ── CORS ── Allow all origins for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register all domain routers
app.include_router(users_router)
app.include_router(monitors_router)
app.include_router(logs_router)
app.include_router(alerts_router)
app.include_router(status_router)   # Phase 8 — public status page (no auth)

# ── Serve frontend ── Only mount when running locally (in Docker, Nginx serves frontend)
# In Docker, frontend/ is excluded from the image — Nginx handles it via volume mount.
if os.path.isdir("frontend"):
    app.mount("/ui", StaticFiles(directory="frontend", html=True), name="frontend")


@app.get("/", tags=["Health"])
async def root():
    return {"message": "Uptime Monitor API is running!"}
