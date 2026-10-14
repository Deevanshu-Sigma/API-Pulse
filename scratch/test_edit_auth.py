"""
Quick test: verify that PATCH /api/monitors/{id} correctly
updates / clears / preserves authentication configuration.
"""
import asyncio
import httpx
import time

BASE = "http://127.0.0.1:8000"
G = "\033[92m"  # green
R = "\033[91m"  # red
C = "\033[96m"  # cyan
E = "\033[0m"   # reset

def ok(msg):   print(f"  {G}[PASS]{E}  {msg}")
def fail(msg): print(f"  {R}[FAIL]{E}  {msg}")
def info(msg): print(f"  {C}[INFO]{E}  {msg}")


async def test():
    print(f"\n{C}{'='*60}{E}")
    print(f"{C}  Edit-Monitor Auth Test{E}")
    print(f"{C}{'='*60}{E}")

    async with httpx.AsyncClient() as c:
        # ── Register ─────────────────────────────────────────────
        email = f"edit_test_{int(time.time())}@test.com"
        r = await c.post(f"{BASE}/api/auth/register",
                         json={"email": email, "password": "pass123"})
        assert r.status_code == 201, f"Register failed: {r.text}"
        token = r.json()["access_token"]
        h = {"Authorization": f"Bearer {token}"}
        info(f"Registered as {email}")

        # ── Create monitor with Basic Auth ────────────────────────
        r = await c.post(f"{BASE}/api/monitors", headers=h, json={
            "name": "Edit Test",
            "url": "http://httpbin.org/basic-auth/admin/secret",
            "method": "GET",
            "interval_minutes": 60,
            "expected_status": 200,
            "auth": {"type": "basic", "username": "admin", "password": "secret"},
        })
        assert r.status_code == 201, f"Create failed: {r.text}"
        mid = r.json()["id"]
        d   = r.json()
        ok(f"Created  has_auth={d['has_auth']}  auth_type={d['auth_type']}")
        assert d["auth_type"] == "basic", f"Expected basic, got {d['auth_type']}"

        # ── PATCH: change auth type basic -> bearer ────────────────
        r = await c.patch(f"{BASE}/api/monitors/{mid}", headers=h,
                          json={"auth": {"type": "bearer", "token": "my-new-bearer"}})
        assert r.status_code == 200, f"PATCH bearer failed: {r.text}"
        d = r.json()
        if d["auth_type"] == "bearer":
            ok(f"basic -> bearer  has_auth={d['has_auth']}  auth_type={d['auth_type']}")
        else:
            fail(f"Expected bearer, got '{d['auth_type']}' — auth type did NOT change!")

        # ── PATCH: change bearer -> api_key ───────────────────────
        r = await c.patch(f"{BASE}/api/monitors/{mid}", headers=h,
                          json={"auth": {"type": "api_key",
                                         "key_name": "X-Api-Key",
                                         "key_value": "abc123"}})
        assert r.status_code == 200, f"PATCH api_key failed: {r.text}"
        d = r.json()
        if d["auth_type"] == "api_key":
            ok(f"bearer -> api_key  has_auth={d['has_auth']}  auth_type={d['auth_type']}")
        else:
            fail(f"Expected api_key, got '{d['auth_type']}' — auth type did NOT change!")

        # ── PATCH name only — auth MUST stay unchanged ─────────────
        r = await c.patch(f"{BASE}/api/monitors/{mid}", headers=h,
                          json={"name": "Renamed Monitor"})
        assert r.status_code == 200, f"PATCH name failed: {r.text}"
        d = r.json()
        if d["auth_type"] == "api_key" and d["name"] == "Renamed Monitor":
            ok(f"name-only PATCH  auth unchanged={d['auth_type']}  name='{d['name']}'")
        else:
            fail(f"auth changed unexpectedly after name-only PATCH: {d}")

        # ── PATCH: clear auth (send auth=null) ─────────────────────
        r = await c.patch(f"{BASE}/api/monitors/{mid}", headers=h,
                          json={"auth": None})
        assert r.status_code == 200, f"PATCH clear auth failed: {r.text}"
        d = r.json()
        if not d["has_auth"] and d["auth_type"] is None:
            ok(f"auth=null clears auth  has_auth={d['has_auth']}  auth_type={d['auth_type']}")
        else:
            fail(f"Auth not cleared after sending auth=null: {d}")

    print(f"\n{C}{'='*60}{E}")
    print(f"{C}  Done.{E}")
    print(f"{C}{'='*60}{E}\n")


asyncio.run(test())
