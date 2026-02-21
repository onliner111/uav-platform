from __future__ import annotations

import asyncio
import json
import os
from urllib.parse import urlsplit, urlunsplit

import httpx
import websockets
from demo_common import (
    add_observation,
    assert_status,
    auth_headers,
    bootstrap_admin,
    create_inspection_task,
    create_template,
    wait_ok,
)


def _to_ws_base_url(http_base_url: str) -> str:
    parsed = urlsplit(http_base_url)
    scheme = "wss" if parsed.scheme == "https" else "ws"
    return urlunsplit((scheme, parsed.netloc, "", "", ""))


async def _run() -> None:
    base_url = os.getenv("APP_BASE_URL", "http://app:8000").rstrip("/")
    ws_base_url = _to_ws_base_url(base_url)

    timeout = httpx.Timeout(20.0)
    async with httpx.AsyncClient(base_url=base_url, timeout=timeout) as client:
        await wait_ok(client, "/healthz")
        await wait_ok(client, "/readyz")

        _tenant_id, token = await bootstrap_admin(client, "phase4")
        template_id = await create_template(client, token, name="phase4-template")
        task_id = await create_inspection_task(client, token, template_id, name="phase4-task")
        await add_observation(
            client,
            token,
            task_id,
            item_code="STALLING",
            lat=30.5960,
            lon=114.3070,
            severity=2,
            note="live marker",
        )

        stats_resp = await client.get("/api/dashboard/stats", headers=auth_headers(token))
        assert_status(stats_resp, 200)
        if stats_resp.json()["today_inspections"] < 1:
            raise RuntimeError("dashboard stats did not include today's inspection")

        ws_url = f"{ws_base_url}/ws/dashboard?token={token}"
        async with websockets.connect(ws_url, open_timeout=10.0, close_timeout=5.0) as websocket:
            raw = await asyncio.wait_for(websocket.recv(), timeout=10.0)
            text = raw.decode() if isinstance(raw, bytes) else raw
            payload = json.loads(text)
            if "stats" not in payload:
                raise RuntimeError("dashboard websocket payload missing stats")
            if "markers" not in payload:
                raise RuntimeError("dashboard websocket payload missing markers")

        ui_resp = await client.get("/ui/command-center", params={"token": token})
        assert_status(ui_resp, 200)

    print("demo_command_center_phase4: ok")


def main() -> None:
    asyncio.run(_run())


if __name__ == "__main__":
    main()
