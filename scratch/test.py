import asyncio
import httpx
import time

BASE_URL = "http://127.0.0.1:8000"

# ── Color helpers ────────────────────────────────────────────────────────────
GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
RESET  = "\033[0m"

def ok(msg):      print(f"  {GREEN}[PASS]{RESET}  {msg}")
def fail(msg):    print(f"  {RED}[FAIL]{RESET}  {msg}")
def info(msg):    print(f"  {CYAN}[INFO]{RESET}  {msg}")
def section(title): print(f"\n{YELLOW}{'-'*60}{RESET}\n{YELLOW}  {title}{RESET}\n{YELLOW}{'-'*60}{RESET}")

async def register_and_get_token(client: httpx.AsyncClient) -> str:
    """Register a fresh user and return the JWT access token."""
    email = f"test_{int(time.time())}@test.com"
    res = await client.post(
        f"{BASE_URL}/api/auth/register",
        json={"email": email, "password": "password123"},
    )
    if res.status_code != 201:
        raise RuntimeError(f"Registration failed: {res.status_code} {res.text}")
    token = res.json().get("access_token")
    if not token:
        raise RuntimeError(f"No token in response: {res.text}")
    info(f"Registered as {email}")
    return token


async def create_monitor(
    client, headers, name: str,
    auth_config: dict | None = None,
    url: str = "http://httpbin.org/anything",
    expected_status: int = 200,
):
    """
    Create a monitor with the given auth config; return monitor id or None.
    `url` should be an endpoint that actually validates the auth (e.g. httpbin.org/bearer).
    """
    monitor_data = {
        "name": name,
        "url": url,
        "method": "GET",
        "interval_minutes": 60,
        "expected_status": expected_status,
        "timeout_seconds": 10,
    }
    if auth_config:
        monitor_data["auth"] = auth_config

    res = await client.post(f"{BASE_URL}/api/monitors", json=monitor_data, headers=headers)
    if res.status_code not in (200, 201):
        fail(f"[{name}] Create monitor failed: {res.status_code} {res.text}")
        return None
    monitor_id = res.json().get("id")
    ok(f"[{name}] Monitor created  id={monitor_id}")
    return monitor_id


async def trigger_and_check(
    client, headers, monitor_id: str, name: str,
    expect_up: bool = True,
):
    """
    Trigger an immediate check.
    - expect_up=True  → PASS only if the remote URL returned the expected status
    - expect_up=False → PASS only if the remote URL rejected the request (wrong/missing auth)
    """
    res = await client.post(
        f"{BASE_URL}/api/monitors/{monitor_id}/trigger",
        headers=headers,
        timeout=30,
    )
    if res.status_code != 200:
        fail(f"[{name}] Trigger API call failed: {res.status_code} {res.text}")
        return
    data  = res.json()
    is_up = data.get("is_up")
    sc    = data.get("status_code")
    rt    = data.get("response_time_ms")
    err   = data.get("error_message")

    if expect_up:
        if is_up:
            ok(f"[{name}] Check UP (expected)  status={sc}  rt={rt}ms")
        else:
            fail(f"[{name}] Expected UP but got DOWN  status={sc}  error={err}")
    else:
        # We expect the remote to reject the request (wrong/missing auth)
        if not is_up:
            ok(f"[{name}] Check DOWN (expected – auth rejected by server)  status={sc}")
        else:
            fail(f"[{name}] Expected DOWN (bad auth) but monitor reported UP  status={sc}")


async def test_get_monitor(client, headers, monitor_id: str, name: str):
    """GET a single monitor and verify auth metadata is returned."""
    res = await client.get(f"{BASE_URL}/api/monitors/{monitor_id}", headers=headers)
    if res.status_code != 200:
        fail(f"[{name}] GET monitor failed: {res.status_code}")
        return
    data      = res.json()
    has_auth  = data.get("has_auth")
    auth_type = data.get("auth_type")
    if has_auth:
        ok(f"[{name}] GET monitor  has_auth=True  auth_type={auth_type}")
    else:
        fail(f"[{name}] GET monitor  has_auth should be True but got {has_auth}")


async def test_unauthorized_access(client):
    """Verify that hitting a protected endpoint without a token returns 401."""
    section("Security – Unauthorized access (no token)")
    res = await client.get(f"{BASE_URL}/api/monitors")
    if res.status_code == 401:
        ok("GET /api/monitors without token -> 401 Unauthorized")
    else:
        fail(f"Expected 401, got {res.status_code}")


async def test_wrong_token(client):
    """Verify that a bad token returns 401."""
    section("Security – Invalid/bad token")
    bad_headers = {"Authorization": "Bearer totally.invalid.token"}
    res = await client.get(f"{BASE_URL}/api/monitors", headers=bad_headers)
    if res.status_code == 401:
        ok("GET /api/monitors with bad token -> 401 Unauthorized")
    else:
        fail(f"Expected 401, got {res.status_code}")


async def main():
    print(f"\n{CYAN}{'='*60}{RESET}")
    print(f"{CYAN}  Authorization Test Suite – MonitoringEngine{RESET}")
    print(f"{CYAN}{'='*60}{RESET}")

    async with httpx.AsyncClient() as client:

        # ── Server health ────────────────────────────────────────────────────
        section("1. Server health check")
        try:
            res = await client.get(f"{BASE_URL}/", timeout=5)
            ok(f"Server reachable  status={res.status_code}  body={res.json()}")
        except httpx.ConnectError:
            fail("Cannot reach server at 127.0.0.1:8000 – start with: uvicorn app.main:app --reload")
            return

        # ── Registration & JWT ───────────────────────────────────────────────
        section("2. User registration & JWT token")
        token = await register_and_get_token(client)
        ok("JWT token received")
        headers = {"Authorization": f"Bearer {token}"}

        # ── Security sanity checks ───────────────────────────────────────────
        await test_unauthorized_access(client)
        await test_wrong_token(client)

        # ── Basic Auth: correct credentials ──────────────────────────────────
        # httpbin.org/basic-auth/admin/secret returns 200 only when the
        # correct username+password are sent via Basic auth.
        section("3a. Basic Auth – CORRECT credentials (expect UP)")
        mid = await create_monitor(
            client, headers,
            name="Basic Auth – Correct",
            auth_config={"type": "basic", "username": "admin", "password": "secret"},
            url="http://httpbin.org/basic-auth/admin/secret",
        )
        if mid:
            await test_get_monitor(client, headers, mid, "Basic Auth – Correct")
            await trigger_and_check(client, headers, mid, "Basic Auth – Correct", expect_up=True)

        # ── Basic Auth: wrong credentials ────────────────────────────────────
        # Same URL but wrong password → httpbin returns 401 → monitor DOWN.
        section("3b. Basic Auth – WRONG credentials (expect DOWN)")
        mid = await create_monitor(
            client, headers,
            name="Basic Auth – Wrong",
            auth_config={"type": "basic", "username": "admin", "password": "WRONGPASSWORD"},
            url="http://httpbin.org/basic-auth/admin/secret",
        )
        if mid:
            await trigger_and_check(client, headers, mid, "Basic Auth – Wrong", expect_up=False)

        # ── Bearer Token: valid token (any bearer accepted by httpbin) ────────
        # httpbin.org/bearer returns 200 when Authorization: Bearer <anything>
        # header is present, and 401 when it is missing entirely.
        section("4a. Bearer Token – VALID token present (expect UP)")
        mid = await create_monitor(
            client, headers,
            name="Bearer – Valid",
            auth_config={"type": "bearer", "token": "my-valid-bearer-token"},
            url="http://httpbin.org/bearer",
        )
        if mid:
            await test_get_monitor(client, headers, mid, "Bearer – Valid")
            await trigger_and_check(client, headers, mid, "Bearer – Valid", expect_up=True)

        # ── Bearer Token: NO auth → server returns 401 → monitor DOWN ────────
        # We create a monitor with NO auth pointing at httpbin.org/bearer.
        # Since no Authorization header is sent, httpbin returns 401, which
        # doesn't match expected_status=200, so is_up should be False.
        section("4b. Bearer Token – NO token / missing auth (expect DOWN)")
        mid = await create_monitor(
            client, headers,
            name="Bearer – Missing",
            auth_config=None,                    # deliberately no auth
            url="http://httpbin.org/bearer",     # endpoint that REQUIRES bearer
        )
        if mid:
            await trigger_and_check(client, headers, mid, "Bearer – Missing", expect_up=False)

        # ── API Key monitor ──────────────────────────────────────────────────
        # httpbin.org/anything echoes back all headers; we verify the monitor
        # is stored with has_auth=True and that the check reaches the server.
        section("5. Monitor with API Key Auth")
        mid = await create_monitor(
            client, headers,
            name="API Key",
            auth_config={"type": "api_key", "key_name": "X-Api-Key", "key_value": "my-api-key-12345"},
        )
        if mid:
            await test_get_monitor(client, headers, mid, "API Key")
            await trigger_and_check(client, headers, mid, "API Key", expect_up=True)

        # ── No-Auth monitor (sanity) ─────────────────────────────────────────
        section("6. Monitor with No Auth (sanity check)")
        mid = await create_monitor(
            client, headers,
            name="No Auth",
            url="http://httpbin.org/get",
        )
        if mid:
            res_get = await client.get(f"{BASE_URL}/api/monitors/{mid}", headers=headers)
            has_auth = res_get.json().get("has_auth") if res_get.status_code == 200 else "?"
            ok(f"No-auth monitor created  has_auth={has_auth}")
            await trigger_and_check(client, headers, mid, "No Auth", expect_up=True)

        # ── List all monitors ────────────────────────────────────────────────
        section("7. List monitors")
        res = await client.get(f"{BASE_URL}/api/monitors", headers=headers)
        if res.status_code == 200:
            ok(f"Listed {len(res.json())} monitor(s)")
        else:
            fail(f"List monitors failed: {res.status_code} {res.text}")

    print(f"\n{CYAN}{'='*60}{RESET}")
    print(f"{CYAN}  All tests complete!{RESET}")
    print(f"{CYAN}{'='*60}{RESET}\n")


asyncio.run(main())
