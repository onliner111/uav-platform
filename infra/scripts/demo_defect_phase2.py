from __future__ import annotations

import asyncio
import os

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

        _tenant_id, token = await bootstrap_admin(client, "phase2")
        template_id = await create_template(client, token, name="phase2-template")
        task_id = await create_inspection_task(client, token, template_id, name="phase2-task")
        observation_id = await add_observation(
            client,
            token,
            task_id,
            item_code="GARBAGE",
            lat=30.5940,
            lon=114.3048,
            severity=3,
            note="overflowing bins",
        )

        defect_resp = await client.post(
            f"/api/defects/from-observation/{observation_id}",
            headers=auth_headers(token),
        )
        assert_status(defect_resp, 201)
        defect_id = defect_resp.json()["id"]

        assign_resp = await client.post(
            f"/api/defects/{defect_id}/assign",
            json={"assigned_to": "inspector-01", "note": "dispatch"},
            headers=auth_headers(token),
        )
        assert_status(assign_resp, 200)

        for next_status in ["IN_PROGRESS", "FIXED", "VERIFIED", "CLOSED"]:
            status_resp = await client.post(
                f"/api/defects/{defect_id}/status",
                json={"status": next_status, "note": f"move to {next_status}"},
                headers=auth_headers(token),
            )
            assert_status(status_resp, 200)

        stats_resp = await client.get("/api/defects/stats", headers=auth_headers(token))
        assert_status(stats_resp, 200)
        if stats_resp.json()["closed"] < 1:
            raise RuntimeError("phase2 stats did not count closed defects")

        ui_resp = await client.get("/ui/defects", params={"token": token})
        assert_status(ui_resp, 200)

    print("demo_defect_phase2: ok")


def main() -> None:
    asyncio.run(_run())


if __name__ == "__main__":
    main()
