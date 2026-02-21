from __future__ import annotations

import asyncio
import os
import time

import httpx
from demo_common import (
    assert_status,
    auth_headers,
    bootstrap_admin,
    create_template,
    wait_ok,
)


async def _run() -> None:
    base_url = os.getenv("APP_BASE_URL", "http://app:8000").rstrip("/")
    timeout = httpx.Timeout(20.0)
    async with httpx.AsyncClient(base_url=base_url, timeout=timeout) as client:
        await wait_ok(client, "/healthz")
        await wait_ok(client, "/readyz")

        _tenant_id, token = await bootstrap_admin(client, "phase3")
        template_id = await create_template(client, token, name="phase3-template")

        started = time.monotonic()
        incident_resp = await client.post(
            "/api/incidents",
            json={
                "title": "Emergency spill",
                "level": "HIGH",
                "location_geom": "POINT(114.305500 30.592800)",
            },
            headers=auth_headers(token),
        )
        assert_status(incident_resp, 201)
        incident_id = incident_resp.json()["id"]

        task_resp = await client.post(
            f"/api/incidents/{incident_id}/create-task",
            json={"template_id": template_id},
            headers=auth_headers(token),
        )
        assert_status(task_resp, 200)
        payload = task_resp.json()
        if not payload.get("mission_id"):
            raise RuntimeError("mission_id missing in emergency task creation")
        if time.monotonic() - started > 180:
            raise RuntimeError("phase3 flow exceeded 3-minute target")

        ui_resp = await client.get("/ui/emergency", params={"token": token})
        assert_status(ui_resp, 200)

    print("demo_emergency_phase3: ok")


def main() -> None:
    asyncio.run(_run())


if __name__ == "__main__":
    main()
