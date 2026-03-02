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

        _tenant_id, token = await bootstrap_admin(client, "phase38")

        platform_page = await client.get(f"/ui/platform?token={token}")
        assert_status(platform_page, 200)
        for marker in (
            "租户开通向导",
            "标准配置包与模板中心",
            "模式切换与交付交接",
            "数据字典与治理总览",
            "治理快捷入口",
        ):
            if marker not in platform_page.text:
                raise RuntimeError(f"phase38 platform page missing marker: {marker}")

    print("demo_phase38_delivery_onboarding_operations: ok")


def main() -> None:
    asyncio.run(_run())


if __name__ == "__main__":
    main()
