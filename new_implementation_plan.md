# Uptime Monitor — Full B2B Product Implementation Plan

**Stack:** FastAPI · PostgreSQL · APScheduler · httpx · Plain HTML/CSS/JS  
**Architecture:** Domain/Feature Modular  
**Goal:** A portfolio-grade, B2B-ready API monitoring product to showcase advanced backend skills to recruiters.

---

## Current Status vs. Target

| Phase | Feature Area | Current State | Target |
|---|---|---|---|
| Phase 0 | Environment & Setup | ✅ Done | — |
| Phase 1 | DB Schema + Auth | ✅ Done | — |
| Phase 2 | Monitor CRUD + Pinger Engine | ✅ Done | ✅ Complete |
| **Phase 3** | **Auth/Headers for Private APIs** | ❌ Missing | ✅ Complete |
| **Phase 4** | **POST/PUT Payload Support** | ❌ Missing | ✅ Complete |
| **Phase 5** | **Response Assertions** | ❌ Missing | ✅ Complete |
| **Phase 6** | **Alert Integrations** | ✅ Done | ✅ Complete |
| **Phase 7** | **Frontend Dashboard** | ⚠️ Partially Done (Missing B2B UI) | ✅ Complete |
| **Phase 8** | **Public Status Page** | ❌ Missing | ✅ Complete |
| **Phase 9** | **Docker + Deployment** | ❌ Missing | ✅ Complete |

---

## Corrections to the Existing Plan

> [!WARNING]
> **Fix #1 — `datetime.utcnow()` is deprecated.** Replace all uses with `datetime.now(timezone.utc)` throughout `models.py`, `scheduler.py`, and `router.py`. Python 3.12 will emit deprecation warnings.

> [!WARNING]
> **Fix #2 — `ping_url()` signature mismatch.** The scheduler calls `ping_url(url, method, timeout, expected_status)` but the function signature in `service.py` needs to match exactly. Verify positional vs. keyword args.

> [!IMPORTANT]
> **Fix #3 — Alembic migration needed for new columns.** Every new column added to `monitors` (headers, body, assertions) requires a new Alembic migration. Never edit the initial migration file directly.

> [!NOTE]
> **Fix #4 — `update_monitor` must re-schedule.** If `interval_minutes` is PATCH'd, the APScheduler job must be replaced with the new interval via `add_monitor_job(..., replace_existing=True)`.

> [!NOTE]
> **Fix #5 — Secrets must not be logged.** The `headers` / `auth_config` column will contain API keys. Never log their values in the pinger or scheduler. Log only key names (e.g. `"Authorization header present"`).

---

## Complete Project Folder Structure (Final)

```
D:\MonitoringEngine\
│
├── app/
│   ├── main.py                     ← FastAPI + lifespan (scheduler)
│   ├── database.py                 ← Async engine + AsyncSessionLocal
│   ├── __init__.py
│   │
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py               ← Pydantic Settings from .env
│   │   └── security.py             ← encrypt/decrypt helpers (Fernet)
│   │
│   ├── users/                      ← Auth domain
│   │   ├── __init__.py
│   │   ├── models.py               ← User ORM model
│   │   ├── schemas.py              ← UserRegister, UserLogin, Token, UserResponse
│   │   ├── service.py              ← hash_password, JWT, get_current_user
│   │   └── router.py               ← /api/auth/register, /login, /me
│   │
│   ├── monitors/                   ← Monitor domain
│   │   ├── __init__.py
│   │   ├── models.py               ← Monitor ORM (+ headers, body, assertions cols)
│   │   ├── schemas.py              ← MonitorCreate, MonitorUpdate, MonitorResponse
│   │   ├── service.py              ← ping_url() — injects headers, body, runs assertions
│   │   ├── scheduler.py            ← APScheduler singleton + run_check()
│   │   └── router.py               ← CRUD + /pause /resume /test
│   │
│   ├── logs/                       ← Check history domain
│   │   ├── __init__.py
│   │   ├── models.py               ← CheckLog ORM (+ region, assertion_results cols)
│   │   ├── schemas.py              ← CheckLogResponse
│   │   └── router.py               ← GET /logs, GET /logs/stats
│   │
│   ├── alerts/                     ← Alert channels domain
│   │   ├── __init__.py
│   │   ├── models.py               ← AlertChannel ORM
│   │   ├── schemas.py              ← AlertChannelCreate, AlertChannelResponse
│   │   ├── service.py              ← send_slack, send_discord, send_email
│   │   └── router.py               ← /api/monitors/{id}/alerts CRUD
│   │
│   └── status/                     ← Public status page domain [NEW]
│       ├── __init__.py
│       └── router.py               ← GET /status/{username} (no auth)
│
├── alembic/
│   ├── env.py
│   └── versions/
│       ├── 9c9ec2f1bf16_create_initial_tables.py     ← existing
│       ├── 0002_add_auth_headers_to_monitors.py       ← Phase 3
│       ├── 0003_add_body_assertions_to_monitors.py    ← Phase 4+5
│       └── 0004_add_region_to_check_logs.py           ← Phase 9+
│
├── frontend/
│   ├── index.html                  ← Login page
│   ├── register.html               ← Register page
│   ├── dashboard.html              ← Monitor cards grid
│   ├── monitor.html                ← Monitor detail page
│   ├── css/
│   │   └── styles.css              ← Dark theme design system
│   └── js/
│       ├── api.js                  ← All fetch() calls
│       ├── auth.js                 ← Login / register logic
│       ├── dashboard.js            ← Load monitors, add, delete
│       └── monitor.js              ← Detail page, charts
│
├── .env
├── .gitignore
├── alembic.ini
├── Dockerfile
├── docker-compose.yml
└── requirements.txt
```

---

## Full API Route Map (Final)

| Method | Route | Auth | Description |
|---|---|---|---|
| POST | `/api/auth/register` | No | Register + get JWT |
| POST | `/api/auth/login` | No | Login + get JWT |
| GET | `/api/auth/me` | JWT | Current user profile |
| GET | `/api/monitors` | JWT | List all monitors |
| POST | `/api/monitors` | JWT | Create monitor (with headers/auth/body) |
| GET | `/api/monitors/{id}` | JWT | Get single monitor |
| PATCH | `/api/monitors/{id}` | JWT | Update monitor |
| DELETE | `/api/monitors/{id}` | JWT | Delete monitor |
| POST | `/api/monitors/{id}/pause` | JWT | Pause monitor |
| POST | `/api/monitors/{id}/resume` | JWT | Resume monitor |
| POST | `/api/monitors/{id}/test` | JWT | **[NEW]** Run a one-off check right now |
| GET | `/api/monitors/{id}/logs` | JWT | Get check history |
| GET | `/api/monitors/{id}/logs/stats` | JWT | Uptime %, avg ms |
| POST | `/api/monitors/{id}/alerts` | JWT | Add alert channel |
| GET | `/api/monitors/{id}/alerts` | JWT | List alert channels |
| DELETE | `/api/monitors/{id}/alerts/{cid}` | JWT | Remove alert channel |
| GET | `/status/{username}` | No | **[NEW]** Public status page |

---

## Updated Requirements (requirements.txt)

```
fastapi==0.115.0
uvicorn[standard]==0.30.6
sqlalchemy[asyncio]==2.0.36
asyncpg==0.30.0
alembic==1.13.3
pydantic[email]==2.9.2
pydantic-settings==2.5.2
python-jose[cryptography]==3.3.0
bcrypt==4.2.1
httpx==0.27.2
apscheduler==3.10.4
twilio==9.3.7
aiosmtplib==3.0.1
python-multipart==0.0.12
python-dotenv==1.0.1
cryptography==43.0.3
```

> `cryptography` is added for Fernet symmetric encryption of stored API keys/tokens.

---

## Updated .env File

```env
DATABASE_URL=postgresql+asyncpg://postgres:yourpassword@localhost:5432/monitoring_db
SECRET_KEY=your-random-64-char-secret
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440

# Encryption key for stored API credentials (generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
ENCRYPTION_KEY=your-fernet-key-here

SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your@gmail.com
SMTP_PASSWORD=your-gmail-app-password
SMTP_FROM=alerts@uptimemonitor.com

TWILIO_SID=
TWILIO_TOKEN=
TWILIO_PHONE=
```

---

---

# PHASE 2 — Monitor CRUD + Scheduler + Pinger Engine ⬜ IMPLEMENT FIRST

**Goal:** Users can add monitors. Backend pings URLs on schedule, saves results to `check_logs`.

This phase is already fully designed in `implementation_plan_phase2`. Implement it exactly as documented there. The only correction is using `datetime.now(timezone.utc)` instead of `datetime.utcnow()`.

### Phase 2 Checklist
- [ ] `app/monitors/scheduler.py` created
- [ ] `app/main.py` updated with lifespan (scheduler start/stop + job reload on restart)
- [ ] `monitors/router.py` — create/delete/pause/resume all call scheduler hooks
- [ ] `logs/router.py` — `/logs/stats` endpoint added
- [ ] `POST /api/monitors` creates monitor + scheduler job registered
- [ ] After interval, `check_logs` has new rows + monitor `status` = `"up"` or `"down"`
- [ ] Server restart re-registers all active jobs

---

---

# PHASE 3 — Auth/Headers for Private APIs 🔐

**Goal:** Users can monitor private/authenticated APIs by providing API keys, Bearer tokens, or Basic Auth credentials. Credentials are encrypted at rest.

This is the **#1 B2B feature** — without it, the product can only monitor public URLs.

---

## Why Encrypt Credentials?

If you store raw API keys in the DB and the DB is ever breached, all your customers' secrets are exposed. Using Fernet symmetric encryption, we encrypt credentials before writing to DB and decrypt just before the HTTP request. The `ENCRYPTION_KEY` env var is the master key — keep it in a secrets manager in production.

---

## Step 1 — Add `app/core/security.py` [NEW]

```python
from cryptography.fernet import Fernet
from app.core.config import settings

_fernet = Fernet(settings.ENCRYPTION_KEY.encode())

def encrypt_value(value: str) -> str:
    """Encrypt a plaintext string. Returns a base64 token."""
    return _fernet.encrypt(value.encode()).decode()

def decrypt_value(token: str) -> str:
    """Decrypt a Fernet token back to plaintext."""
    return _fernet.decrypt(token.encode()).decode()
```

---

## Step 2 — Update `app/core/config.py`

Add `ENCRYPTION_KEY: str` to the `Settings` class.

```python
class Settings(BaseSettings):
    DATABASE_URL: str
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440
    ENCRYPTION_KEY: str          # ← ADD THIS
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = ""
    TWILIO_SID: str = ""
    TWILIO_TOKEN: str = ""
    TWILIO_PHONE: str = ""

    class Config:
        env_file = ".env"
```

---

## Step 3 — Add `headers` Column to `monitors` Table

### Update `app/monitors/models.py`

Add one JSONB column to store encrypted headers:

```python
from sqlalchemy.dialects.postgresql import UUID, JSONB

class Monitor(Base):
    __tablename__ = "monitors"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String, nullable=False)
    url: Mapped[str] = mapped_column(String, nullable=False)
    method: Mapped[str] = mapped_column(String, default="GET")
    interval_minutes: Mapped[int] = mapped_column(Integer, default=5)
    expected_status: Mapped[int] = mapped_column(Integer, default=200)
    timeout_seconds: Mapped[int] = mapped_column(Integer, default=10)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    status: Mapped[str] = mapped_column(String, default="pending")
    last_checked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    
    # Phase 3 — Auth/Headers
    headers: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    # ^ Stored as: {"Authorization": "enc:TOKEN", "x-api-key": "enc:KEY"}
    # Values prefixed with "enc:" are Fernet-encrypted. Plain values are stored as-is (for non-sensitive headers like Content-Type).
    
    # Phase 4 — Request Body (added in next phase)
    body: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    
    # Phase 5 — Response Assertions (added in next phase)
    assertions: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)
    
    user: Mapped["User"] = relationship("User", back_populates="monitors")
    check_logs: Mapped[list["CheckLog"]] = relationship("CheckLog", back_populates="monitor", cascade="all, delete-orphan")
    alert_channels: Mapped[list["AlertChannel"]] = relationship("AlertChannel", back_populates="monitor", cascade="all, delete-orphan")
```

> [!NOTE]
> We add `body` and `assertions` in the model now (all in one migration) even though they're used in Phase 4 and 5. This avoids multiple separate migrations.

### Alembic Migration

```bash
alembic revision --autogenerate -m "add_headers_body_assertions_to_monitors"
alembic upgrade head
```

---

## Step 4 — Update `app/monitors/schemas.py`

```python
from pydantic import BaseModel, HttpUrl
from typing import Optional, Any
from uuid import UUID
from datetime import datetime

class AuthConfig(BaseModel):
    """Helper model for the 'auth' shortcut in the request body."""
    type: str  # "bearer" | "basic" | "api_key"
    token: Optional[str] = None       # for bearer
    username: Optional[str] = None    # for basic
    password: Optional[str] = None    # for basic
    key_name: Optional[str] = None    # for api_key, e.g. "x-api-key"
    key_value: Optional[str] = None   # for api_key

class AssertionRule(BaseModel):
    """A single response assertion rule."""
    type: str   # "json_field" | "response_time_ms" | "header_contains"
    path: Optional[str] = None        # JSON path, e.g. "data.status"
    operator: str                     # "eq" | "contains" | "lt" | "gt" | "exists"
    value: Optional[Any] = None       # Expected value

class MonitorCreate(BaseModel):
    name: str
    url: str
    method: str = "GET"
    interval_minutes: int = 5
    expected_status: int = 200
    timeout_seconds: int = 10
    
    # Auth/Headers — user provides these in the create request
    headers: Optional[dict[str, str]] = None   # Raw headers; we encrypt sensitive ones
    auth: Optional[AuthConfig] = None           # Shortcut for common auth patterns
    
    # Phase 4
    body: Optional[dict] = None
    
    # Phase 5
    assertions: Optional[list[AssertionRule]] = None

class MonitorUpdate(BaseModel):
    name: Optional[str] = None
    url: Optional[str] = None
    method: Optional[str] = None
    interval_minutes: Optional[int] = None
    expected_status: Optional[int] = None
    timeout_seconds: Optional[int] = None
    headers: Optional[dict[str, str]] = None
    auth: Optional[AuthConfig] = None
    body: Optional[dict] = None
    assertions: Optional[list[AssertionRule]] = None

class MonitorResponse(BaseModel):
    id: UUID
    name: str
    url: str
    method: str
    interval_minutes: int
    expected_status: int
    timeout_seconds: int
    is_active: bool
    status: str
    last_checked_at: Optional[datetime]
    created_at: datetime
    # NOTE: headers/auth are NOT returned in the response for security.
    # We only show whether auth is configured, not the actual values.
    has_auth: bool = False

    class Config:
        from_attributes = True
```

---

## Step 5 — Auth Injection Logic in `app/monitors/router.py`

The router is responsible for **encrypting** credentials before saving and **building** the final headers dict from the `auth` shortcut.

```python
import base64
from app.core.security import encrypt_value

def _build_headers(
    raw_headers: Optional[dict],
    auth: Optional[AuthConfig]
) -> Optional[dict]:
    """
    Merges user-provided raw_headers with the auth shortcut.
    Encrypts all header values for secure storage.
    Returns a dict of {header_name: "enc:<encrypted_value>"}.
    """
    final = dict(raw_headers or {})

    if auth:
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

    # Encrypt every value before storing
    return {k: f"enc:{encrypt_value(v)}" for k, v in final.items()}


@router.post("", response_model=MonitorResponse, status_code=201)
async def create_monitor(
    data: MonitorCreate,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    encrypted_headers = _build_headers(data.headers, data.auth)
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
        assertions=[a.model_dump() for a in data.assertions] if data.assertions else None,
    )
    db.add(monitor)
    await db.commit()
    await db.refresh(monitor)
    add_monitor_job(str(monitor.id), monitor.interval_minutes)
    return monitor
```

---

## Step 6 — Decrypt Headers in `app/monitors/service.py`

The `ping_url()` function must decrypt headers before passing them to `httpx`:

```python
import httpx
from typing import Optional
from datetime import datetime, timezone
from app.core.security import decrypt_value

def _resolve_headers(stored_headers: Optional[dict]) -> dict:
    """Decrypt stored headers back to plaintext for the HTTP request."""
    if not stored_headers:
        return {}
    resolved = {}
    for k, v in stored_headers.items():
        if isinstance(v, str) and v.startswith("enc:"):
            resolved[k] = decrypt_value(v[4:])  # strip "enc:" prefix
        else:
            resolved[k] = v
    return resolved


async def ping_url(
    url: str,
    method: str = "GET",
    timeout: int = 10,
    expected_status: int = 200,
    headers: Optional[dict] = None,    # ← Encrypted headers from DB
    body: Optional[dict] = None,
    assertions: Optional[list] = None,
) -> dict:
    """
    Performs an HTTP check. Decrypts headers, sends the request,
    runs assertions, and returns a result dict.
    """
    live_headers = _resolve_headers(headers)
    start = datetime.now(timezone.utc)
    
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.request(
                method=method,
                url=url,
                headers=live_headers,
                json=body if body else None,
            )
        
        elapsed_ms = int(
            (datetime.now(timezone.utc) - start).total_seconds() * 1000
        )
        is_up = response.status_code == expected_status
        
        # Run assertions (Phase 5)
        assertion_failures = []
        if assertions and is_up:
            assertion_failures = _run_assertions(response, assertions)
            if assertion_failures:
                is_up = False
        
        return {
            "status_code": response.status_code,
            "response_time_ms": elapsed_ms,
            "is_up": is_up,
            "error_message": "; ".join(assertion_failures) if assertion_failures else None,
        }
    
    except httpx.TimeoutException:
        return {"status_code": None, "response_time_ms": None, "is_up": False, "error_message": "Request timed out"}
    except Exception as e:
        return {"status_code": None, "response_time_ms": None, "is_up": False, "error_message": str(e)}
```

---

## Step 7 — Update `app/monitors/scheduler.py`

Pass headers/body/assertions from the Monitor object to `ping_url()`:

```python
ping_result = await ping_url(
    url=monitor.url,
    method=monitor.method,
    timeout=monitor.timeout_seconds,
    expected_status=monitor.expected_status,
    headers=monitor.headers,       # ← encrypted dict from DB
    body=monitor.body,
    assertions=monitor.assertions,
)
```

---

## Phase 3 Checklist
- [ ] `app/core/security.py` created with `encrypt_value` / `decrypt_value`
- [ ] `ENCRYPTION_KEY` added to `.env` and `config.py`
- [ ] `headers`, `body`, `assertions` columns added to `monitors` model
- [ ] Alembic migration `0002_add_headers_body_assertions_to_monitors` created and applied
- [ ] `_build_headers()` in router encrypts and merges auth shortcuts
- [ ] `ping_url()` accepts and decrypts headers before request
- [ ] Scheduler passes `monitor.headers`, `monitor.body`, `monitor.assertions` to `ping_url()`
- [ ] Test: create a monitor targeting `https://httpbin.org/bearer` with `auth: {type: "bearer", token: "test123"}` → returns `is_up: true`
- [ ] Test: `GET /api/monitors/{id}` response does NOT expose raw API key values

---

---

# PHASE 4 — POST/PUT Request Body Support 📦

**Goal:** Allow monitors to send JSON request bodies (e.g., test a login endpoint by POSTing credentials).

This is mostly handled by the schema/model changes in Phase 3 (`body` field). The remaining work is:

1. **Validation** — `body` should only be allowed for `POST`, `PUT`, `PATCH` methods. Add a Pydantic validator:

```python
from pydantic import model_validator

class MonitorCreate(BaseModel):
    # ... existing fields ...
    
    @model_validator(mode="after")
    def check_body_requires_post(self) -> "MonitorCreate":
        if self.body and self.method not in ("POST", "PUT", "PATCH"):
            raise ValueError("Request body is only valid for POST, PUT, or PATCH methods.")
        return self
```

2. **`ping_url()`** already handles `json=body` from Phase 3.

3. **Test endpoint** — Add a one-off test endpoint so users can validate their config immediately without waiting for the scheduler:

```python
@router.post("/{monitor_id}/test", response_model=CheckLogResponse)
async def test_monitor_now(
    monitor_id: UUID,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Run an immediate one-off check and return the result."""
    monitor = await _get_monitor_or_404(monitor_id, user_id, db)
    result = await ping_url(
        url=monitor.url, method=monitor.method,
        timeout=monitor.timeout_seconds, expected_status=monitor.expected_status,
        headers=monitor.headers, body=monitor.body, assertions=monitor.assertions,
    )
    log = CheckLog(monitor_id=monitor.id, **result)
    db.add(log)
    monitor.last_checked_at = datetime.now(timezone.utc)
    monitor.status = "up" if result["is_up"] else "down"
    await db.commit()
    await db.refresh(log)
    return log
```

## Phase 4 Checklist
- [ ] `body` field is validated — only allows POST/PUT/PATCH
- [ ] `POST /api/monitors/{id}/test` endpoint exists and works
- [ ] Test: create a monitor for `https://httpbin.org/post` with method `POST` and `body: {"user": "test"}` → `is_up: true`, status 200

---

---

# PHASE 5 — Response Assertions ✅

**Goal:** Check the actual response content, not just the HTTP status code. This is the feature that separates a real monitoring product from a basic ping tool.

## Assertion Types

| type | path | operator | value | Example use case |
|---|---|---|---|---|
| `json_field` | `data.status` | `eq` | `"active"` | API must return `{"data": {"status": "active"}}` |
| `json_field` | `user.id` | `exists` | — | Field must exist in response |
| `response_time_ms` | — | `lt` | `500` | Response must be under 500ms |
| `header_contains` | `content-type` | `contains` | `application/json` | Must return JSON content type |

## `_run_assertions()` in `app/monitors/service.py`

```python
import json

def _run_assertions(response: httpx.Response, assertions: list[dict]) -> list[str]:
    """
    Runs each assertion rule against the response.
    Returns a list of failure messages (empty list = all passed).
    """
    failures = []
    
    for rule in assertions:
        rule_type = rule.get("type")
        operator = rule.get("operator")
        expected = rule.get("value")
        
        try:
            if rule_type == "json_field":
                actual = _get_json_path(response.json(), rule.get("path", ""))
                if operator == "eq" and actual != expected:
                    failures.append(f"JSON field '{rule['path']}': expected '{expected}', got '{actual}'")
                elif operator == "contains" and expected not in str(actual):
                    failures.append(f"JSON field '{rule['path']}': '{expected}' not found in '{actual}'")
                elif operator == "exists" and actual is None:
                    failures.append(f"JSON field '{rule['path']}' does not exist in response")
                elif operator == "gt" and not (actual > expected):
                    failures.append(f"JSON field '{rule['path']}': {actual} is not > {expected}")
                elif operator == "lt" and not (actual < expected):
                    failures.append(f"JSON field '{rule['path']}': {actual} is not < {expected}")
            
            elif rule_type == "response_time_ms":
                # This is evaluated in ping_url() after getting elapsed_ms
                pass  # Handled separately
            
            elif rule_type == "header_contains":
                header_val = response.headers.get(rule.get("path", ""), "")
                if operator == "contains" and expected not in header_val:
                    failures.append(f"Header '{rule['path']}': '{expected}' not found in '{header_val}'")
                elif operator == "eq" and header_val != expected:
                    failures.append(f"Header '{rule['path']}': expected '{expected}', got '{header_val}'")
        
        except Exception as e:
            failures.append(f"Assertion error for rule {rule}: {str(e)}")
    
    return failures


def _get_json_path(data: dict, path: str) -> Any:
    """Traverse a dot-notation path in a dict. e.g. 'data.user.id'"""
    keys = path.split(".")
    current = data
    for key in keys:
        if isinstance(current, dict) and key in current:
            current = current[key]
        else:
            return None
    return current
```

## Update `app/logs/models.py` — Add `assertion_results`

```python
class CheckLog(Base):
    __tablename__ = "check_logs"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    monitor_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("monitors.id", ondelete="CASCADE"))
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)
    status_code: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    response_time_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    is_up: Mapped[bool] = mapped_column(Boolean, nullable=False)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    assertion_results: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)  # ← NEW
    monitor: Mapped["Monitor"] = relationship("Monitor", back_populates="check_logs")
```

## Phase 5 Checklist
- [ ] `_run_assertions()` implemented in `service.py`
- [ ] `_get_json_path()` helper handles dot-notation paths
- [ ] `assertion_results` column added to `check_logs` model
- [ ] Alembic migration applied
- [ ] Test: create monitor for `https://httpbin.org/json` with assertion `{type: "json_field", path: "slideshow.title", operator: "eq", value: "Sample Slide Show"}` → `is_up: true`
- [ ] Test: same with wrong expected value → `is_up: false`, `error_message` explains failure

---

---

# PHASE 6 — Alert Integrations 🔔

**Goal:** When a monitor goes DOWN, notify via Slack, Discord, or Email. Alert only on `up → down` transition (no alert storms).

## `app/alerts/service.py`

```python
import httpx
import aiosmtplib
from email.message import EmailMessage
from sqlalchemy import select
from app.alerts.models import AlertChannel
from app.core.config import settings


async def send_alerts(monitor, error: str, db) -> None:
    """Fetch all alert channels for this monitor and dispatch notifications."""
    result = await db.execute(
        select(AlertChannel).where(AlertChannel.monitor_id == monitor.id)
    )
    channels = result.scalars().all()
    
    for channel in channels:
        try:
            if channel.channel_type == "slack":
                await send_slack(channel.config["webhook_url"], monitor.name, monitor.url, error)
            elif channel.channel_type == "discord":
                await send_discord(channel.config["webhook_url"], monitor.name, monitor.url, error)
            elif channel.channel_type == "email":
                await send_email(channel.config["to"], monitor.name, monitor.url, error)
        except Exception as e:
            # Log the failure but don't crash the scheduler
            print(f"[ALERT ERROR] channel={channel.channel_type} error={e}")


async def send_slack(webhook_url: str, name: str, url: str, error: str) -> None:
    payload = {
        "text": f"🔴 *{name}* is DOWN\nURL: {url}\nError: {error}"
    }
    async with httpx.AsyncClient() as client:
        await client.post(webhook_url, json=payload)


async def send_discord(webhook_url: str, name: str, url: str, error: str) -> None:
    payload = {
        "embeds": [{
            "title": f"🔴 {name} is DOWN",
            "description": f"**URL:** {url}\n**Error:** {error}",
            "color": 15158332  # Red
        }]
    }
    async with httpx.AsyncClient() as client:
        await client.post(webhook_url, json=payload)


async def send_email(to: str, name: str, url: str, error: str) -> None:
    message = EmailMessage()
    message["Subject"] = f"🔴 ALERT: {name} is DOWN"
    message["From"] = settings.SMTP_FROM
    message["To"] = to
    message.set_content(
        f"Monitor: {name}\nURL: {url}\nError: {error}\n\nThis is an automated alert."
    )
    await aiosmtplib.send(
        message,
        hostname=settings.SMTP_HOST,
        port=settings.SMTP_PORT,
        username=settings.SMTP_USER,
        password=settings.SMTP_PASSWORD,
        start_tls=True,
    )
```

## `app/alerts/router.py`

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import UUID
from app.database import get_db
from app.users.service import get_current_user
from app.alerts.models import AlertChannel
from app.alerts.schemas import AlertChannelCreate, AlertChannelResponse

router = APIRouter(prefix="/api/monitors", tags=["Alerts"])

@router.post("/{monitor_id}/alerts", response_model=AlertChannelResponse, status_code=201)
async def create_alert_channel(
    monitor_id: UUID,
    data: AlertChannelCreate,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    channel = AlertChannel(monitor_id=monitor_id, **data.model_dump())
    db.add(channel)
    await db.commit()
    await db.refresh(channel)
    return channel

@router.get("/{monitor_id}/alerts", response_model=list[AlertChannelResponse])
async def list_alert_channels(
    monitor_id: UUID,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(AlertChannel).where(AlertChannel.monitor_id == monitor_id)
    )
    return result.scalars().all()

@router.delete("/{monitor_id}/alerts/{channel_id}", status_code=204)
async def delete_alert_channel(
    monitor_id: UUID,
    channel_id: UUID,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(AlertChannel).where(
            AlertChannel.id == channel_id,
            AlertChannel.monitor_id == monitor_id
        )
    )
    channel = result.scalar()
    if not channel:
        raise HTTPException(status_code=404, detail="Alert channel not found")
    await db.delete(channel)
    await db.commit()
```

## Phase 6 Checklist
- [ ] Slack webhook alert fires when monitor goes DOWN
- [ ] Email alert fires (configure Gmail App Password in .env)
- [ ] Alert does NOT fire when monitor comes back UP
- [ ] Alert does NOT fire on second DOWN check (alert storms prevented)
- [ ] `POST /api/monitors/{id}/alerts` with `{"channel_type": "slack", "config": {"webhook_url": "..."}}`

---

---

# PHASE 7 — Frontend Dashboard 🖥️

**Goal:** A visually impressive dark-theme dashboard that showcases all B2B features. This is what the recruiter will SEE.

## Design Tokens (css/styles.css)

```css
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

:root {
  --bg: #080b14;
  --surface: #0e1420;
  --card-bg: rgba(255, 255, 255, 0.03);
  --border: rgba(255, 255, 255, 0.07);
  --accent: #6366f1;         /* Indigo — primary brand color */
  --accent-glow: rgba(99, 102, 241, 0.3);
  --up: #22c55e;
  --up-glow: rgba(34, 197, 94, 0.2);
  --down: #ef4444;
  --down-glow: rgba(239, 68, 68, 0.2);
  --pending: #f59e0b;
  --text: #f1f5f9;
  --text-muted: #64748b;
  --text-secondary: #94a3b8;
  --font: 'Inter', -apple-system, sans-serif;
  --radius: 12px;
  --radius-sm: 8px;
  --shadow: 0 4px 24px rgba(0,0,0,0.4);
}
```

## Pages Required

| File | Content |
|---|---|
| `frontend/index.html` | Login form with JWT auth |
| `frontend/register.html` | Registration form |
| `frontend/dashboard.html` | Monitor cards grid, Add Monitor modal with auth fields |
| `frontend/monitor.html` | Detail page with Chart.js, log table, assertions display |

## Key Feature: "Add Monitor" Modal

The modal must include an **Auth Configuration** section with tab-style selection:

```
[ No Auth ] [ Bearer Token ] [ API Key ] [ Basic Auth ]

Bearer Token:
  Token: [__________________________]

API Key:
  Header Name: [x-api-key___________]
  Value:       [my-secret-key_______]

Basic Auth:
  Username: [_________________________]
  Password: [_________________________]
```

And an **Assertions** section (collapsible/advanced):

```
+ Add Assertion

[ JSON Field ▼ ]  Path: [data.status___]  [ equals ▼ ]  Value: [active___]
[ Header      ▼]  Path: [content-type__]  [ contains ▼] Value: [json____]
```

## Monitor Card Design

```
┌─────────────────────────────────────────────┐
│ ● UP          api.example.com/health         │
│   "Production API Health"                    │
│                                              │
│  ⏱ 142ms    🕐 2 min ago    ✓ 99.8%         │
│                                              │
│  🔐 Bearer Auth    [Test Now] [Pause] [⋮]   │
└─────────────────────────────────────────────┘
```

## Phase 7 Checklist
- [ ] Login page: JWT stored in `localStorage`, redirect on success
- [ ] Dashboard: all monitor cards load on page load
- [ ] Auth type badge shows on cards (🔐 Bearer, 🔑 API Key, etc.)
- [ ] "Add Monitor" modal submits with auth config and assertions
- [ ] "Test Now" button calls `POST /api/monitors/{id}/test` and shows result immediately
- [ ] Pause/Resume toggles correctly
- [ ] Delete with confirmation dialog

---

---

# PHASE 8 — Public Status Page 🌐

**Goal:** Each user gets a public-facing status page at `/status/{username}` that anyone can visit without logging in. This is the feature that companies share with their customers during incidents.

## `app/status/router.py` [NEW]

```python
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.users.models import User
from app.monitors.models import Monitor

router = APIRouter(tags=["Status Page"])

@router.get("/status/{username}", response_class=HTMLResponse)
async def public_status_page(
    username: str,
    db: AsyncSession = Depends(get_db)
):
    """Public status page — no authentication required."""
    # Find user by email prefix (username is the part before @)
    result = await db.execute(
        select(User).where(User.email.ilike(f"{username}@%"))
    )
    user = result.scalar()
    if not user:
        raise HTTPException(status_code=404, detail="Status page not found")
    
    result = await db.execute(
        select(Monitor).where(
            Monitor.user_id == user.id,
            Monitor.is_active == True
        )
    )
    monitors = result.scalars().all()
    
    # Render inline HTML (no template engine needed)
    all_up = all(m.status == "up" for m in monitors)
    overall = "All Systems Operational" if all_up else "⚠️ Some Systems Down"
    
    cards = ""
    for m in monitors:
        dot = "#22c55e" if m.status == "up" else "#ef4444" if m.status == "down" else "#f59e0b"
        label = m.status.upper()
        cards += f"""
        <div class="card">
          <div class="dot" style="background:{dot}"></div>
          <div class="info">
            <strong>{m.name}</strong>
            <span>{m.url}</span>
          </div>
          <div class="status" style="color:{dot}">{label}</div>
        </div>"""
    
    return f"""<!DOCTYPE html>
<html>
<head>
  <title>Status — {username}</title>
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600&display=swap" rel="stylesheet">
  <style>
    body {{ font-family: 'Inter', sans-serif; background: #080b14; color: #f1f5f9; margin: 0; padding: 40px 20px; }}
    .container {{ max-width: 700px; margin: 0 auto; }}
    h1 {{ font-size: 28px; margin-bottom: 4px; }}
    .overall {{ color: {'#22c55e' if all_up else '#ef4444'}; font-size: 18px; margin-bottom: 32px; }}
    .card {{ background: rgba(255,255,255,0.04); border: 1px solid rgba(255,255,255,0.08); border-radius: 12px; padding: 16px 20px; display: flex; align-items: center; gap: 14px; margin-bottom: 12px; }}
    .dot {{ width: 12px; height: 12px; border-radius: 50%; flex-shrink: 0; }}
    .info {{ flex: 1; }}
    .info strong {{ display: block; font-size: 15px; }}
    .info span {{ font-size: 13px; color: #64748b; }}
    .status {{ font-weight: 600; font-size: 14px; }}
  </style>
</head>
<body>
  <div class="container">
    <h1>🔍 {username} Status</h1>
    <p class="overall">{overall}</p>
    {cards if cards else "<p>No monitors configured.</p>"}
    <p style="color:#64748b;font-size:12px;margin-top:32px">Powered by Uptime Monitor</p>
  </div>
</body>
</html>"""
```

Register in `main.py`:
```python
from app.status.router import router as status_router
app.include_router(status_router)
```

## Phase 8 Checklist
- [ ] `/status/{username}` returns public HTML page with no auth
- [ ] All active monitors shown with current status
- [ ] Overall "All Systems Operational" / "Some Systems Down" banner
- [ ] Works for a non-existent username (404)

---

---

# PHASE 9 — Docker + Deployment 🚀

**Goal:** The entire stack runs with a single `docker-compose up` command. Then deploy to Railway.app or Render.

## Dockerfile

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Run Alembic migrations then start server
CMD alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## docker-compose.yml

```yaml
version: "3.9"

services:
  db:
    image: postgres:15-alpine
    restart: unless-stopped
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-yourpassword}
      POSTGRES_DB: monitoring_db
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 5s
      timeout: 5s
      retries: 5

  backend:
    build: .
    restart: unless-stopped
    ports:
      - "8000:8000"
    depends_on:
      db:
        condition: service_healthy
    env_file:
      - .env

  frontend:
    image: nginx:alpine
    restart: unless-stopped
    ports:
      - "80:80"
    volumes:
      - ./frontend:/usr/share/nginx/html:ro

volumes:
  postgres_data:
```

> [!IMPORTANT]
> The `depends_on: condition: service_healthy` ensures the backend won't start before PostgreSQL is actually ready to accept connections — a common source of startup failures.

## Deployment Options

| Platform | Cost | Best For |
|---|---|---|
| **Railway.app** | Free tier, ~$5/mo | Easiest — GitHub auto-deploy, no config |
| **Render.com** | Free tier | Free PostgreSQL, good for portfolio |
| **DigitalOcean App Platform** | $5-12/mo | More control, good docs |
| **Fly.io** | Free tier | Docker-native, global regions |

## Phase 9 Checklist
- [ ] `docker-compose up --build` starts all 3 services cleanly
- [ ] `http://localhost` serves the frontend
- [ ] `http://localhost:8000/docs` shows Swagger
- [ ] Alembic runs automatically on container start
- [ ] App pushed to GitHub
- [ ] Deployed to Railway/Render with public URL

---

---

# Build Order Summary

This is the exact order to implement everything:

```
(DONE)   →  PHASE 3  →  PHASE 4  →  PHASE 5  →  (DONE)  →  PHASE 7  →  PHASE 8  →  PHASE 9
Scheduler    Auth/Headers  POST body  Assertions   Alerts     Frontend    Status Page  Docker
```
*(Phase 2 and Phase 6 are already complete. Phase 7 has the basic UI done, but needs the new B2B Auth/Assertions modal)*

## Final Project Checklist

- [x] Phase 0 — Environment set up, FastAPI running
- [x] Phase 1 — Auth working (register, login, JWT, 4 DB tables)
- [x] Phase 2 — Monitors pinged on schedule, logs saved
- [ ] Phase 3 — Private API auth (headers, Bearer, Basic, API key) with encryption
- [ ] Phase 4 — POST/PUT body support + `/test` endpoint
- [ ] Phase 5 — Response assertions (JSON field, headers, timing)
- [x] Phase 6 — Alerts firing on Slack / Discord / Email
- [ ] Phase 7 — Dashboard UI with auth config and assertion builder
- [ ] Phase 8 — Public status page at `/status/{username}`
- [ ] Phase 9 — Docker deployed, publicly accessible URL

---

## Recruiter-Facing Feature Summary

When presenting this project, these are the talking points:

| Feature | Skill Demonstrated |
|---|---|
| JWT Auth + bcrypt | Security fundamentals |
| APScheduler async jobs | Background task management |
| Fernet encryption of API keys | At-rest encryption, secrets management |
| httpx async HTTP client | Async I/O, HTTP internals |
| Response assertions engine | Test framework design, JSON path traversal |
| Alembic migrations | Schema evolution, production DB management |
| up→down transition detection | State machine thinking, alert storm prevention |
| Docker + docker-compose | Containerization, service orchestration |
| Public status page | Multi-tenant SaaS pattern |
| Domain-modular FastAPI structure | Clean architecture, separation of concerns |
