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

        _tenant_id, token = await bootstrap_admin(client, "phase37")

        alerts_page = await client.get(f"/ui/alerts?token={token}")
        assert_status(alerts_page, 200)
        for marker in (
            "消息中心与待办中心",
            "统一待办视图",
            "通知渠道与发送策略",
            "回执、催办与升级跟踪",
            "角色优先级与协同建议",
        ):
            if marker not in alerts_page.text:
                raise RuntimeError(f"phase37 alerts page missing marker: {marker}")

    print("demo_phase37_notification_collaboration_hub: ok")


def main() -> None:
    asyncio.run(_run())


if __name__ == "__main__":
    main()
