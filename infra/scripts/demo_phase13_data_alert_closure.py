from __future__ import annotations

import asyncio
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

        _tenant_id, token = await bootstrap_admin(client, "phase13")

        rule_in_app = await client.post(
            "/api/alert/routing-rules",
            json={
                "priority_level": "P1",
                "channel": "IN_APP",
                "target": "duty-ops",
                "is_active": True,
            },
            headers=auth_headers(token),
        )
        assert_status(rule_in_app, 201)

        rule_email = await client.post(
            "/api/alert/routing-rules",
            json={
                "priority_level": "P1",
                "channel": "EMAIL",
                "target": "ops@example.com",
                "is_active": True,
            },
            headers=auth_headers(token),
        )
        assert_status(rule_email, 201)

        mission_resp = await client.post(
            "/api/mission/missions",
            json={
                "name": "phase13-mission",
                "type": "POINT_TASK",
                "payload": {"point": {"lat": 30.2, "lon": 114.3, "alt_m": 80}},
                "constraints": {},
            },
            headers=auth_headers(token),
        )
        assert_status(mission_resp, 201)
        mission_id = mission_resp.json()["id"]

        template_id = await create_template(client, token, "phase13-template")
        task_id = await create_inspection_task(
            client,
            token,
            template_id,
            name="phase13-task",
            mission_id=mission_id,
        )

        obs_resp = await client.post(
            f"/api/inspection/tasks/{task_id}/observations",
            json={
                "position_lat": 30.5801,
                "position_lon": 114.3001,
                "alt_m": 42.0,
                "item_code": "PH13-OBS",
                "severity": 2,
                "note": "phase13 observation",
                "confidence": 0.91,
            },
            headers=auth_headers(token),
        )
        assert_status(obs_resp, 201)

        outcomes_resp = await client.get(f"/api/outcomes/records?task_id={task_id}", headers=auth_headers(token))
        assert_status(outcomes_resp, 200)
        outcomes = outcomes_resp.json()
        if not outcomes:
            raise RuntimeError("expected auto-materialized outcomes")
        outcome_id = outcomes[0]["id"]

        review_resp = await client.patch(
            f"/api/outcomes/records/{outcome_id}/status",
            json={"status": "IN_REVIEW", "note": "triaged"},
            headers=auth_headers(token),
        )
        assert_status(review_resp, 200)

        verify_resp = await client.patch(
            f"/api/outcomes/records/{outcome_id}/status",
            json={"status": "VERIFIED", "note": "verified"},
            headers=auth_headers(token),
        )
        assert_status(verify_resp, 200)

        raw_resp = await client.post(
            "/api/outcomes/raw",
            json={
                "task_id": task_id,
                "mission_id": mission_id,
                "data_type": "IMAGE",
                "source_uri": "s3://phase13/evidence.jpg",
                "meta": {"camera": "payload-a"},
            },
            headers=auth_headers(token),
        )
        assert_status(raw_resp, 201)

        critical_ingest = await client.post(
            "/api/telemetry/ingest",
            json={
                "tenant_id": "spoofed",
                "drone_id": "phase13-drone-critical",
                "position": {"lat": 30.1, "lon": 114.2, "alt_m": 120.0},
                "battery": {"percent": 60.0},
                "link": {"latency_ms": 3000},
                "mode": "LINK_LOST",
                "health": {"link_lost": True},
            },
            headers=auth_headers(token),
        )
        assert_status(critical_ingest, 200)

        warning_ingest = await client.post(
            "/api/telemetry/ingest",
            json={
                "tenant_id": "spoofed",
                "drone_id": "phase13-drone-warning",
                "position": {"lat": 30.1, "lon": 114.2, "alt_m": 120.0},
                "battery": {"percent": 12.0},
                "link": {"latency_ms": 50},
                "mode": "AUTO",
                "health": {"low_battery": True},
            },
            headers=auth_headers(token),
        )
        assert_status(warning_ingest, 200)

        alerts_resp = await client.get("/api/alert/alerts", headers=auth_headers(token))
        assert_status(alerts_resp, 200)
        alerts = alerts_resp.json()
        critical = [item for item in alerts if item["alert_type"] == "LINK_LOSS"]
        if not critical:
            raise RuntimeError("expected LINK_LOSS alert")
        critical_alert_id = critical[0]["id"]

        routes_resp = await client.get(
            f"/api/alert/alerts/{critical_alert_id}/routes",
            headers=auth_headers(token),
        )
        assert_status(routes_resp, 200)
        routes = routes_resp.json()
        if not routes:
            raise RuntimeError("expected alert route logs")
        external_routes = [item for item in routes if item["channel"] in {"EMAIL", "SMS", "WEBHOOK"}]
        if external_routes and any(item["delivery_status"] != "SKIPPED" for item in external_routes):
            raise RuntimeError("external route should be SKIPPED placeholder")

        action_resp = await client.post(
            f"/api/alert/alerts/{critical_alert_id}/actions",
            json={"action_type": "VERIFY", "note": "verified in demo"},
            headers=auth_headers(token),
        )
        assert_status(action_resp, 200)

        ack_resp = await client.post(
            f"/api/alert/alerts/{critical_alert_id}/ack",
            json={"comment": "ack in demo"},
            headers=auth_headers(token),
        )
        assert_status(ack_resp, 200)

        close_resp = await client.post(
            f"/api/alert/alerts/{critical_alert_id}/close",
            json={"comment": "close in demo"},
            headers=auth_headers(token),
        )
        assert_status(close_resp, 200)

        review_resp = await client.get(
            f"/api/alert/alerts/{critical_alert_id}/review",
            headers=auth_headers(token),
        )
        assert_status(review_resp, 200)
        if len(review_resp.json().get("actions", [])) < 3:
            raise RuntimeError("expected alert handling action chain")

        export_resp = await client.post(
            "/api/reporting/export",
            json={
                "title": "Phase13 Data Outcome Report",
                "task_id": task_id,
                "topic": "other",
                "from_ts": (datetime.now(UTC) - timedelta(days=1)).isoformat(),
                "to_ts": (datetime.now(UTC) + timedelta(days=1)).isoformat(),
            },
            headers=auth_headers(token),
        )
        assert_status(export_resp, 200)
        if not export_resp.json().get("file_path"):
            raise RuntimeError("report export file path missing")

    print("demo_phase13_data_alert_closure: ok")


def main() -> None:
    asyncio.run(_run())


if __name__ == "__main__":
    main()
