from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import os
from datetime import UTC, datetime, timedelta

import httpx
from demo_common import (
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

        _tenant_id, token = await bootstrap_admin(client, "phase15")

        template_id = await create_template(client, token, "phase15-template")
        task_id = await create_inspection_task(client, token, template_id, name="phase15-task")

        obs_resp = await client.post(
            f"/api/inspection/tasks/{task_id}/observations",
            json={
                "position_lat": 30.5801,
                "position_lon": 114.3001,
                "alt_m": 55.0,
                "item_code": "PH15-OBS",
                "severity": 2,
                "note": "phase15 observation",
                "confidence": 0.9,
            },
            headers=auth_headers(token),
        )
        assert_status(obs_resp, 201)

        now = datetime.now(UTC)
        ingest_1 = await client.post(
            "/api/telemetry/ingest",
            json={
                "tenant_id": "spoofed",
                "drone_id": "phase15-drone",
                "ts": (now - timedelta(minutes=5)).isoformat(),
                "position": {"lat": 30.58, "lon": 114.30, "alt_m": 120.0},
                "battery": {"percent": 86.0},
                "link": {"latency_ms": 120},
                "mode": "AUTO",
                "health": {},
            },
            headers=auth_headers(token),
        )
        assert_status(ingest_1, 200)
        ingest_2 = await client.post(
            "/api/telemetry/ingest",
            json={
                "tenant_id": "spoofed",
                "drone_id": "phase15-drone",
                "ts": now.isoformat(),
                "position": {"lat": 30.583, "lon": 114.306, "alt_m": 122.0},
                "battery": {"percent": 81.0},
                "link": {"latency_ms": 130},
                "mode": "AUTO",
                "health": {},
            },
            headers=auth_headers(token),
        )
        assert_status(ingest_2, 200)

        snapshot_resp = await client.post(
            "/api/kpi/snapshots/recompute",
            json={
                "from_ts": (now - timedelta(days=1)).isoformat(),
                "to_ts": (now + timedelta(days=1)).isoformat(),
                "window_type": "CUSTOM",
            },
            headers=auth_headers(token),
        )
        assert_status(snapshot_resp, 201)
        snapshot = snapshot_resp.json()
        if snapshot["metrics"]["outcomes_total"] < 1:
            raise RuntimeError("expected at least one outcome in KPI snapshot")

        heatmap_resp = await client.get("/api/kpi/heatmap?source=OUTCOME", headers=auth_headers(token))
        assert_status(heatmap_resp, 200)
        if not heatmap_resp.json():
            raise RuntimeError("expected heatmap bins")

        credential_resp = await client.post(
            "/api/open-platform/credentials",
            json={"key_id": "phase15-demo-key"},
            headers=auth_headers(token),
        )
        assert_status(credential_resp, 201)
        credential = credential_resp.json()

        webhook_resp = await client.post(
            "/api/open-platform/webhooks",
            json={
                "name": "phase15-demo-hook",
                "endpoint_url": "https://external.example/hook",
                "event_type": "workorder.upsert",
                "credential_id": credential["id"],
            },
            headers=auth_headers(token),
        )
        assert_status(webhook_resp, 201)
        endpoint_id = webhook_resp.json()["id"]

        dispatch_resp = await client.post(
            f"/api/open-platform/webhooks/{endpoint_id}/dispatch-test",
            json={"payload": {"ticket_id": "WO-001"}},
            headers=auth_headers(token),
        )
        assert_status(dispatch_resp, 200)
        if dispatch_resp.json()["status"] != "SENT":
            raise RuntimeError("expected webhook test dispatch status SENT")

        ingress_payload = {"event_type": "workorder.upsert", "payload": {"ticket_id": "WO-001"}}
        raw_body = json.dumps(ingress_payload, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
        signature = hmac.new(
            credential["signing_secret"].encode("utf-8"),
            raw_body,
            hashlib.sha256,
        ).hexdigest()
        ingest_open_resp = await client.post(
            "/api/open-platform/adapters/events/ingest",
            content=raw_body,
            headers={
                "Content-Type": "application/json",
                "X-Open-Key-Id": credential["key_id"],
                "X-Open-Api-Key": credential["api_key"],
                "X-Open-Signature": signature,
            },
        )
        assert_status(ingest_open_resp, 201)
        if ingest_open_resp.json()["status"] != "ACCEPTED":
            raise RuntimeError("expected adapter ingress accepted")

        report_resp = await client.post(
            "/api/kpi/governance/export",
            json={"title": "Phase15 Governance Report", "window_type": "MONTHLY"},
            headers=auth_headers(token),
        )
        assert_status(report_resp, 200)
        if not report_resp.json().get("file_path"):
            raise RuntimeError("governance export path missing")

    print("demo_phase15_kpi_open_platform: ok")


def main() -> None:
    asyncio.run(_run())


if __name__ == "__main__":
    main()
