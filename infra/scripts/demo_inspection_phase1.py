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

        _tenant_id, token = await bootstrap_admin(client, "phase1")
        template_id = await create_template(client, token, name="phase1-template")
        task_id = await create_inspection_task(client, token, template_id, name="phase1-task")

        await add_observation(
            client,
            token,
            task_id,
            item_code="SIDEWALK_OCCUPY",
            lat=30.5912,
            lon=114.3011,
            severity=2,
            note="sidewalk occupied",
        )
        await add_observation(
            client,
            token,
            task_id,
            item_code="GARBAGE",
            lat=30.5920,
            lon=114.3025,
            severity=3,
            note="garbage accumulation",
        )
        await add_observation(
            client,
            token,
            task_id,
            item_code="STALLING",
            lat=30.5930,
            lon=114.3036,
            severity=2,
            note="illegal stall",
        )

        export_resp = await client.post(
            f"/api/inspection/tasks/{task_id}/export",
            params={"format": "html"},
            headers=auth_headers(token),
        )
        assert_status(export_resp, 200)
        export_id = export_resp.json()["id"]

        download_resp = await client.get(
            f"/api/inspection/exports/{export_id}",
            headers=auth_headers(token),
        )
        assert_status(download_resp, 200)

        ui_resp = await client.get("/ui/inspection", params={"token": token})
        assert_status(ui_resp, 200)
        ui_detail_resp = await client.get(f"/ui/inspection/tasks/{task_id}", params={"token": token})
        assert_status(ui_detail_resp, 200)

    print("demo_inspection_phase1: ok")


def main() -> None:
    asyncio.run(_run())


if __name__ == "__main__":
    main()
