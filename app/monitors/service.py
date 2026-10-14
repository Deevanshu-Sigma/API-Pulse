"""
HTTP ping service — Phase 3, 4 & 5.

Functions
---------
_resolve_headers(stored_headers)
    Decrypts Fernet-encrypted header values just before the HTTP request.

_get_json_path(data, path)
    Traverses a dot-notation path through a nested dict.
    e.g. "data.user.status" → data["data"]["user"]["status"]

_evaluate_assertion(rule, response, elapsed_ms)
    Evaluates ONE assertion rule against an httpx.Response.
    Returns {"rule": ..., "passed": bool, "detail": str | None}.

run_assertions(rules, response, elapsed_ms)
    Evaluates ALL assertion rules and returns the list of result dicts.

ping_url(url, method, timeout, expected_status, headers, body)
    Pure async HTTP check — no DB access.  Returns a result dict.
    Now also accepts 'assertions' and runs them after the request.

ping_and_save(monitor, db)
    Runs ping_url() using the monitor's stored config, persists a CheckLog
    (with assertion_results), and updates monitor.status / last_checked_at.
    Used by BOTH the scheduler and the /trigger endpoint.
"""

import httpx
import time
from datetime import datetime, timezone
from typing import Optional, Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decrypt_value


# ── Header decryption ─────────────────────────────────────────────────────────

def _resolve_headers(stored_headers: Optional[dict]) -> dict:
    """Decrypt stored header values back to plaintext for the outgoing request."""
    if not stored_headers:
        return {}
    resolved: dict[str, str] = {}
    for key, value in stored_headers.items():
        if key == "X-Kae-Auth-Type":
            continue
        if isinstance(value, str) and value.startswith("enc:"):
            resolved[key] = decrypt_value(value[4:])
        else:
            resolved[key] = value
    return resolved


# ── Assertions engine ─────────────────────────────────────────────────────────

def _get_json_path(data: Any, path: str) -> Any:
    """
    Traverse a dot-notation path in a nested dict/list structure.

    Examples:
        _get_json_path({"a": {"b": 1}}, "a.b")  → 1
        _get_json_path({"a": [1, 2]}, "a")       → [1, 2]
        _get_json_path({"a": 1}, "a.b.c")        → None  (missing key)
    """
    if not path:
        return data
    current = data
    for key in path.split("."):
        if isinstance(current, dict):
            if key not in current:
                return None
            current = current[key]
        else:
            return None
    return current


def _evaluate_assertion(
    rule: dict,
    response: httpx.Response,
    elapsed_ms: int,
) -> dict:
    """
    Evaluate a single assertion rule against an httpx.Response.

    Returns a result dict:
        {
            "rule":   <the original rule dict>,
            "passed": bool,
            "detail": str | None  (failure message, or None if passed)
        }
    """
    rule_type = rule.get("type")
    operator  = rule.get("operator", "eq")
    path      = rule.get("path")
    expected  = rule.get("value")

    passed = False
    detail = None

    try:
        # ── json_field ───────────────────────────────────────────────────────
        if rule_type == "json_field":
            try:
                body = response.json()
            except Exception:
                return {
                    "rule": rule, "passed": False,
                    "detail": "Response body is not valid JSON",
                }
            actual = _get_json_path(body, path or "")

            if operator == "exists":
                passed = actual is not None
                if not passed:
                    detail = f"JSON path '{path}' does not exist in response"

            elif operator == "eq":
                passed = actual == expected
                if not passed:
                    detail = f"JSON path '{path}': expected {expected!r}, got {actual!r}"

            elif operator == "neq":
                passed = actual != expected
                if not passed:
                    detail = f"JSON path '{path}': expected value != {expected!r}, got {actual!r}"

            elif operator == "contains":
                if isinstance(actual, (list, str)):
                    passed = expected in actual
                else:
                    passed = False
                if not passed:
                    detail = f"JSON path '{path}': {expected!r} not found in {actual!r}"

            elif operator == "gt":
                passed = actual is not None and actual > expected
                if not passed:
                    detail = f"JSON path '{path}': {actual!r} is not > {expected!r}"

            elif operator == "lt":
                passed = actual is not None and actual < expected
                if not passed:
                    detail = f"JSON path '{path}': {actual!r} is not < {expected!r}"

            else:
                detail = f"Unknown operator '{operator}' for type '{rule_type}'"

        # ── response_time_ms ─────────────────────────────────────────────────
        elif rule_type == "response_time_ms":
            if operator == "lt":
                passed = elapsed_ms < expected
                if not passed:
                    detail = f"response_time_ms {elapsed_ms} is not < {expected}"
            elif operator == "gt":
                passed = elapsed_ms > expected
                if not passed:
                    detail = f"response_time_ms {elapsed_ms} is not > {expected}"
            else:
                detail = f"Unknown operator '{operator}' for type 'response_time_ms' (use 'lt' or 'gt')"

        # ── status_code ──────────────────────────────────────────────────────
        elif rule_type == "status_code":
            actual = response.status_code
            if operator == "eq":
                passed = actual == expected
                if not passed:
                    detail = f"status_code {actual} is not == {expected}"
            elif operator == "neq":
                passed = actual != expected
                if not passed:
                    detail = f"status_code {actual} is not != {expected}"
            elif operator == "lt":
                passed = actual < expected
                if not passed:
                    detail = f"status_code {actual} is not < {expected}"
            elif operator == "gt":
                passed = actual > expected
                if not passed:
                    detail = f"status_code {actual} is not > {expected}"
            else:
                detail = f"Unknown operator '{operator}' for type 'status_code'"

        # ── header ───────────────────────────────────────────────────────────
        elif rule_type == "header":
            header_val = response.headers.get(path or "", None)

            if operator == "exists":
                passed = header_val is not None
                if not passed:
                    detail = f"Response header '{path}' is not present"

            elif operator == "eq":
                passed = header_val == expected
                if not passed:
                    detail = f"Header '{path}': expected {expected!r}, got {header_val!r}"

            elif operator == "contains":
                if header_val is not None:
                    passed = expected in header_val
                if not passed:
                    detail = f"Header '{path}': {expected!r} not found in {header_val!r}"

            else:
                detail = f"Unknown operator '{operator}' for type 'header'"

        else:
            detail = f"Unknown assertion type '{rule_type}'"

    except Exception as exc:
        passed = False
        detail = f"Assertion evaluation error: {exc}"

    return {"rule": rule, "passed": passed, "detail": detail}


def run_assertions(
    rules: list[dict],
    response: httpx.Response,
    elapsed_ms: int,
) -> list[dict]:
    """
    Evaluate all assertion rules and return the full results list.

    Each item in the returned list:
        {"rule": <rule_dict>, "passed": bool, "detail": str | None}
    """
    return [_evaluate_assertion(rule, response, elapsed_ms) for rule in rules]


# ── Pure HTTP ping ────────────────────────────────────────────────────────────

async def ping_url(
    url: str,
    method: str,
    timeout: int,
    expected_status: int,
    headers: Optional[dict] = None,
    body: Optional[dict] = None,
    assertions: Optional[list] = None,
) -> dict:
    """
    Send an HTTP request and return a result dict:
        is_up            (bool)
        status_code      (int | None)
        response_time_ms (int | None)
        error_message    (str | None)
        assertion_results (list | None)  ← Phase 5

    Phase 5: if assertions are provided they are evaluated after the request.
    A single failing assertion marks is_up=False even if the status code matched.
    """
    live_headers = _resolve_headers(headers)

    start = time.monotonic()
    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            response = await client.request(
                method,
                url,
                headers=live_headers if live_headers else None,
                json=body if body else None,
            )
        elapsed_ms = int((time.monotonic() - start) * 1000)

        # Primary status-code check
        status_ok = response.status_code == expected_status

        # Assertion checks (only run if status code passed — pointless otherwise)
        assertion_results = None
        failed_assertions: list[str] = []

        if assertions and status_ok:
            assertion_results = run_assertions(assertions, response, elapsed_ms)
            failed_assertions = [
                r["detail"] for r in assertion_results if not r["passed"]
            ]

        is_up = status_ok and not failed_assertions

        # Build error_message
        if not status_ok:
            error_message = f"Expected {expected_status}, got {response.status_code}"
        elif failed_assertions:
            error_message = "; ".join(f for f in failed_assertions if f)
        else:
            error_message = None

        return {
            "is_up": is_up,
            "status_code": response.status_code,
            "response_time_ms": elapsed_ms,
            "error_message": error_message,
            "assertion_results": assertion_results,
        }

    except httpx.TimeoutException:
        return {
            "is_up": False,
            "status_code": None,
            "response_time_ms": None,
            "error_message": "Request timed out",
            "assertion_results": None,
        }
    except Exception as e:
        return {
            "is_up": False,
            "status_code": None,
            "response_time_ms": None,
            "error_message": str(e),
            "assertion_results": None,
        }


# ── Ping + persist (shared between scheduler and /trigger endpoint) ───────────

async def ping_and_save(monitor, db: AsyncSession) -> tuple[dict, object]:
    """
    Run a full check cycle for *monitor*:
      1. Call ping_url() with stored config (auth + body + assertions).
      2. Persist a CheckLog row (including assertion_results).
      3. Update monitor.status and monitor.last_checked_at.
      4. Commit.

    Returns (ping_result, log).
    The CALLER is responsible for firing alerts.
    """
    from app.logs.models import CheckLog  # local import avoids circular deps

    ping_result = await ping_url(
        url=monitor.url,
        method=monitor.method,
        timeout=monitor.timeout_seconds,
        expected_status=monitor.expected_status,
        headers=monitor.headers,
        body=monitor.body,
        assertions=monitor.assertions,  # ← Phase 5
    )

    # CheckLog now accepts assertion_results — pop it from ping_result so
    # **ping_result unpacking doesn't fail on older DB rows without the column.
    log = CheckLog(monitor_id=monitor.id, **ping_result)
    db.add(log)

    monitor.status = "up" if ping_result["is_up"] else "down"
    monitor.last_checked_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(log)

    return ping_result, log
