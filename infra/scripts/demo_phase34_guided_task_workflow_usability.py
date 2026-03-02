from __future__ import annotations

import asyncio
import os

import httpx
from demo_common import assert_status, bootstrap_admin, wait_ok


async def _assert_ui_contains(client: httpx.AsyncClient, token: str, path: str, expected: str) -> None:
    response = await client.get(f"{path}?token={token}")
    assert_status(response, 200)
    if expected not in response.text:
        raise RuntimeError(f"phase34 demo expected {expected!r} in {path}")


async def _run() -> None:
    base_url = os.getenv("APP_BASE_URL", "http://app:8000").rstrip("/")
    timeout = httpx.Timeout(20.0)
    async with httpx.AsyncClient(base_url=base_url, timeout=timeout) as client:
        await wait_ok(client, "/healthz")
        await wait_ok(client, "/readyz")

        _tenant_id, token = await bootstrap_admin(client, "phase34")

        ui_checks = [
            ("/ui/inspection", "巡检任务创建向导"),
            ("/ui/inspection", "推荐提示"),
            ("/ui/emergency", "1. 地图选点"),
            ("/ui/emergency", "风险提示"),
            ("/ui/compliance", "审批流可视化"),
            ("/ui/compliance", "流程提示"),
        ]
        for path, expected in ui_checks:
            await _assert_ui_contains(client, token, path, expected)

    print("demo_phase34_guided_task_workflow_usability: ok")


def main() -> None:
    asyncio.run(_run())


if __name__ == "__main__":
    main()
