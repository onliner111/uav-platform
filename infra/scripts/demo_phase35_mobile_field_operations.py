from __future__ import annotations

import asyncio
import os

import httpx
from demo_common import assert_status, bootstrap_admin, wait_ok


async def _run() -> None:
    base_url = os.getenv("APP_BASE_URL", "http://app:8000").rstrip("/")
    timeout = httpx.Timeout(20.0)
    async with httpx.AsyncClient(base_url=base_url, timeout=timeout) as client:
        await wait_ok(client, "/healthz")
        await wait_ok(client, "/readyz")

        _tenant_id, token = await bootstrap_admin(client, "phase35")
        headers = {"Authorization": f"Bearer {token}"}

        create_template_resp = await client.post(
            "/api/inspection/templates",
            json={
                "name": "phase35-template",
                "category": "field-mobile",
                "description": "phase35 mobile template",
                "is_active": True,
            },
            headers=headers,
        )
        assert_status(create_template_resp, 201)
        template_id = create_template_resp.json()["id"]

        create_task_resp = await client.post(
            "/api/inspection/tasks",
            json={
                "name": "phase35-task",
                "template_id": template_id,
                "mission_id": None,
                "area_geom": "",
                "priority": 5,
            },
            headers=headers,
        )
        assert_status(create_task_resp, 201)
        task_id = create_task_resp.json()["id"]

        task_page = await client.get(f"/ui/inspection/tasks/{task_id}?token={token}")
        assert_status(task_page, 200)
        for marker in ("现场执行工作台", "网络状态", "重试上一笔", "现场备注与媒体预留"):
            if marker not in task_page.text:
                raise RuntimeError(f"phase35 task page missing marker: {marker}")

        defects_page = await client.get(f"/ui/defects?token={token}")
        assert_status(defects_page, 200)
        for marker in ("移动端缺陷工作区", "重试上一笔分派", "重试上一笔状态更新", "现场补充说明"):
            if marker not in defects_page.text:
                raise RuntimeError(f"phase35 defects page missing marker: {marker}")

    print("demo_phase35_mobile_field_operations: ok")


def main() -> None:
    asyncio.run(_run())


if __name__ == "__main__":
    main()
