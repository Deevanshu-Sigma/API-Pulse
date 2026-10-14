from pydantic import BaseModel, model_validator
from uuid import UUID
from datetime import datetime
from typing import Optional, Any


# ── Auth helper schema ───────────────────────────────────────────────────────

class AuthConfig(BaseModel):
    """
    Convenience shortcut so users don't have to construct the Authorization
    header by hand.  The router converts this into the final headers dict
    before saving to the database.

    Supported types:
      "bearer"  — sets  Authorization: Bearer <token>
      "basic"   — sets  Authorization: Basic base64(username:password)
      "api_key" — sets  <key_name>: <key_value>  (e.g. x-api-key: ...)
    """
    type: str                          # "bearer" | "basic" | "api_key"
    token: Optional[str] = None        # bearer only
    username: Optional[str] = None     # basic only
    password: Optional[str] = None     # basic only
    key_name: Optional[str] = None     # api_key only  (the header name)
    key_value: Optional[str] = None    # api_key only  (the header value)


# ── Phase 5: Assertion rule schema ───────────────────────────────────────────

class AssertionRule(BaseModel):
    """
    A single rule that is evaluated against the HTTP response after each ping.

    If any rule fails, is_up is set to False for that check log entry, and
    the failure reason is stored in error_message and assertion_results.

    Supported types and their required fields
    -----------------------------------------
    "json_field"
        Evaluate a dot-notation path in the JSON response body.
        path     : required  — e.g. "data.user.status"
        operator : "eq" | "neq" | "contains" | "exists" | "gt" | "lt"
        value    : required for eq/neq/contains/gt/lt, omit for exists

    "response_time_ms"
        Compare the round-trip time in milliseconds.
        operator : "lt" | "gt"
        value    : required  — integer threshold in ms

    "status_code"
        Check the HTTP status code (in addition to expected_status).
        operator : "eq" | "neq" | "lt" | "gt"
        value    : required  — integer status code

    "header"
        Inspect a response header value.
        path     : required  — header name, e.g. "content-type"
        operator : "eq" | "contains" | "exists"
        value    : required for eq/contains, omit for exists

    Operators
    ---------
    "eq"       — exact equality
    "neq"      — not equal
    "contains" — substring or list membership
    "exists"   — field/header must be present (ignores value)
    "gt"       — greater than (numeric)
    "lt"       — less than (numeric)
    """
    type: str                        # "json_field" | "response_time_ms" | "status_code" | "header"
    path: Optional[str] = None       # JSON dot path or header name
    operator: str                    # see docstring above
    value: Optional[Any] = None      # expected value (omit for "exists")


# ── Monitor CRUD schemas ─────────────────────────────────────────────────────

class MonitorCreate(BaseModel):
    name: str
    url: str
    method: str = "GET"
    interval_minutes: int = 5
    expected_status: int = 200
    timeout_seconds: int = 10

    # Phase 3 — Auth / Custom Headers
    auth: Optional[AuthConfig] = None
    headers: Optional[dict[str, str]] = None

    # Phase 4 — Request Body (POST / PUT / PATCH monitors only)
    body: Optional[dict] = None

    # Phase 5 — Response Assertions
    assertions: Optional[list[AssertionRule]] = None

    @model_validator(mode="after")
    def body_requires_post_method(self) -> "MonitorCreate":
        if self.body and self.method not in ("POST", "PUT", "PATCH"):
            raise ValueError(
                "A request body can only be used with POST, PUT, or PATCH monitors."
            )
        return self


class MonitorUpdate(BaseModel):
    name: Optional[str] = None
    url: Optional[str] = None
    method: Optional[str] = None
    interval_minutes: Optional[int] = None
    expected_status: Optional[int] = None
    timeout_seconds: Optional[int] = None

    # Phase 3
    auth: Optional[AuthConfig] = None
    headers: Optional[dict[str, str]] = None

    # Phase 4
    body: Optional[dict] = None

    # Phase 5
    assertions: Optional[list[AssertionRule]] = None


class MonitorResponse(BaseModel):
    id: UUID
    name: str
    url: str
    method: str
    status: str
    interval_minutes: int
    expected_status: int
    timeout_seconds: int
    is_active: bool
    last_checked_at: Optional[datetime]
    created_at: datetime

    # Phase 3 — whether encrypted headers are stored (never expose raw values)
    has_auth: bool = False
    auth_type: Optional[str] = None

    # Phase 5 — whether assertion rules are configured
    has_assertions: bool = False
    assertions: Optional[list[AssertionRule]] = None
    body: Optional[dict] = None

    class Config:
        from_attributes = True
