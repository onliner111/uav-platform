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

        _tenant_id, token = await bootstrap_admin(client, "phase39")

        platform_page = await client.get(f"/ui/platform?token={token}")
        assert_status(platform_page, 200)
        for marker in (
            "上线保障与版本运营台",
            "上线检查清单与巡检面板",
            "内置帮助中心与培训模式",
            "发布说明与升级引导",
            "功能开关与灰度启用",
        ):
            if marker not in platform_page.text:
                raise RuntimeError(f"phase39 platform page missing marker: {marker}")

    print("demo_phase39_release_adoption_lifecycle: ok")


def main() -> None:
    asyncio.run(_run())


if __name__ == "__main__":
    main()
