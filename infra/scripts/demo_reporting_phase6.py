from __future__ import annotations

import asyncio
import os
from uuid import uuid4

import httpx
from demo_common import (
    add_observation,
    assert_status,
    auth_headers,
    bootstrap_admin,
    create_inspection_task,
    create_template,
    wait_ok,
)


async def _run() -> None:
    base_url = os.getenv("APP_BASE_URL", "http://app:8000").rstrip("/")
    timeout = httpx.Timeout(20.0)
    async with httpx.AsyncClient(base_url=base_url, timeout=timeout) as client:
        await wait_ok(client, "/healthz")
        await wait_ok(client, "/readyz")

        _tenant_id, token = await bootstrap_admin(client, "phase6")
        template_id = await create_template(client, token, name="phase6-template")
        task_id = await create_inspection_task(client, token, template_id, name="phase6-task")

        drone_resp = await client.post(
            "/api/registry/drones",
            json={
                "name": f"phase6-drone-{uuid4().hex[:6]}",
                "vendor": "FAKE",
                "capabilities": {"camera": True},
            },
            headers=auth_headers(token),
        )
        assert_status(drone_resp, 201)

        observation_id = await add_observation(
            client,
            token,
            task_id,
            item_code="GARBAGE",
            lat=30.5970,
            lon=114.3090,
            severity=3,
            note="reporting source",
        )
        defect_resp = await client.post(
            f"/api/defects/from-observation/{observation_id}",
            headers=auth_headers(token),
        )
        assert_status(defect_resp, 201)
        defect_id = defect_resp.json()["id"]
        await client.post(
            f"/api/defects/{defect_id}/assign",
            json={"assigned_to": "phase6-user"},
            headers=auth_headers(token),
        )
        for next_status in ["IN_PROGRESS", "FIXED", "VERIFIED", "CLOSED"]:
            status_resp = await client.post(
                f"/api/defects/{defect_id}/status",
                json={"status": next_status},
                headers=auth_headers(token),
            )
            assert_status(status_resp, 200)

        overview_resp = await client.get("/api/reporting/overview", headers=auth_headers(token))
        assert_status(overview_resp, 200)
        closure_resp = await client.get("/api/reporting/closure-rate", headers=auth_headers(token))
        assert_status(closure_resp, 200)
        util_resp = await client.get("/api/reporting/device-utilization", headers=auth_headers(token))
        assert_status(util_resp, 200)
        export_resp = await client.post(
            "/api/reporting/export",
            json={"title": "Quarterly Reporting Demo"},
            headers=auth_headers(token),
        )
        assert_status(export_resp, 200)
        file_path = export_resp.json().get("file_path")
        if not file_path:
            raise RuntimeError("report export did not return file_path")

    print("demo_reporting_phase6: ok")


def main() -> None:
    asyncio.run(_run())


if __name__ == "__main__":
    main()
