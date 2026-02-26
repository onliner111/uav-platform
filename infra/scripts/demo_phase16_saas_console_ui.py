from __future__ import annotations

import asyncio
import os
from uuid import uuid4

import httpx
from demo_common import assert_status, wait_ok


async def _run() -> None:
    base_url = os.getenv("APP_BASE_URL", "http://app:8000").rstrip("/")
    timeout = httpx.Timeout(20.0)

    async with httpx.AsyncClient(base_url=base_url, timeout=timeout, follow_redirects=False) as client:
        await wait_ok(client, "/healthz")
        await wait_ok(client, "/readyz")

        run_id = uuid4().hex[:8]
        tenant_name = f"phase16-tenant-{run_id}"
        username = f"phase16-admin-{run_id}"
        password = f"phase16-pass-{run_id}"

        tenant_resp = await client.post("/api/identity/tenants", json={"name": tenant_name})
        assert_status(tenant_resp, 201)
        tenant_id = tenant_resp.json()["id"]

        bootstrap_resp = await client.post(
            "/api/identity/bootstrap-admin",
            json={"tenant_id": tenant_id, "username": username, "password": password},
        )
        assert_status(bootstrap_resp, 201)

        login_page_resp = await client.get("/ui/login?next=/ui/console")
        assert_status(login_page_resp, 200)
        csrf_token = client.cookies.get("uav_ui_csrf")
        if not csrf_token:
            raise RuntimeError("ui csrf cookie not set")

        login_submit_resp = await client.post(
            "/ui/login",
            data={
                "tenant_id": tenant_id,
                "username": username,
                "password": password,
                "csrf_token": csrf_token,
                "next": "/ui/console",
            },
        )
        assert_status(login_submit_resp, 303)
        if login_submit_resp.headers.get("location") != "/ui/console":
            raise RuntimeError(f"unexpected login redirect: {login_submit_resp.headers.get('location')}")
        if not client.cookies.get("uav_ui_session"):
            raise RuntimeError("ui session cookie not set")

        console_resp = await client.get("/ui/console")
        assert_status(console_resp, 200)
        body = console_resp.text
        required_markers = [
            "SaaS Console",
            "Navigation",
            "Switch Tenant",
            "Task Center",
            "Platform",
        ]
        for marker in required_markers:
            if marker not in body:
                raise RuntimeError(f"console page missing marker: {marker}")

        module_paths = [
            "/ui/inspection",
            "/ui/defects",
            "/ui/emergency",
            "/ui/command-center",
            "/ui/task-center",
            "/ui/assets",
            "/ui/compliance",
            "/ui/alerts",
            "/ui/reports",
            "/ui/platform",
        ]
        for path in module_paths:
            resp = await client.get(path)
            assert_status(resp, 200)

        logout_csrf = client.cookies.get("uav_ui_csrf")
        if not logout_csrf:
            raise RuntimeError("logout csrf cookie missing")
        logout_resp = await client.post("/ui/logout", data={"csrf_token": logout_csrf})
        assert_status(logout_resp, 303)
        if logout_resp.headers.get("location") != "/ui/login":
            raise RuntimeError(f"unexpected logout redirect: {logout_resp.headers.get('location')}")

    print("demo_phase16_saas_console_ui: ok")


def main() -> None:
    asyncio.run(_run())


if __name__ == "__main__":
    main()
