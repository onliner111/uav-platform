from __future__ import annotations

import asyncio
import os

import httpx
from demo_common import assert_status, bootstrap_admin, wait_ok


async def _assert_ui_contains(client: httpx.AsyncClient, token: str, path: str, expected: str) -> None:
    response = await client.get(f"{path}?token={token}")
    assert_status(response, 200)
    if expected not in response.text:
        raise RuntimeError(f"phase32 demo expected {expected!r} in {path}")


async def _run() -> None:
    base_url = os.getenv("APP_BASE_URL", "http://app:8000").rstrip("/")
    timeout = httpx.Timeout(20.0)
    async with httpx.AsyncClient(base_url=base_url, timeout=timeout) as client:
        await wait_ok(client, "/healthz")
        await wait_ok(client, "/readyz")

        _tenant_id, token = await bootstrap_admin(client, "phase32")

        ui_checks = [
            ("/ui/console", "角色化工作台"),
            ("/ui/console", "管理员专项入口"),
            ("/ui/workbench/commander", "指挥工作台"),
            ("/ui/workbench/dispatcher", "调度工作台"),
            ("/ui/workbench/operator", "现场执行工作台"),
            ("/ui/workbench/compliance", "合规工作台"),
            ("/ui/workbench/executive", "领导视图"),
            ("/ui/task-center", "主处理动作"),
            ("/ui/assets", "资产处理工作区"),
            ("/ui/alerts", "当前告警处理"),
            ("/ui/alerts", "告警类型"),
            ("/ui/compliance", "审批待办"),
            ("/ui/reports", "成果数据工作区"),
            ("/ui/emergency", "应急事件处置"),
            ("/ui/observability", "管理员关联入口"),
        ]
        for path, expected in ui_checks:
            await _assert_ui_contains(client, token, path, expected)

    print("demo_phase32_role_workbench_productization: ok")


def main() -> None:
    asyncio.run(_run())


if __name__ == "__main__":
    main()
