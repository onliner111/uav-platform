from __future__ import annotations

import asyncio
import os
from datetime import UTC, datetime, timedelta

import httpx
from demo_common import assert_status, auth_headers, bootstrap_admin, wait_ok


async def _run() -> None:
    base_url = os.getenv("APP_BASE_URL", "http://app:8000").rstrip("/")
    timeout = httpx.Timeout(20.0)
    async with httpx.AsyncClient(base_url=base_url, timeout=timeout) as client:
        await wait_ok(client, "/healthz")
        await wait_ok(client, "/readyz")

        _tenant_id, token = await bootstrap_admin(client, "phase22")

        now = datetime.now(UTC)
        shift_resp = await client.post(
            "/api/alert/oncall/shifts",
            json={
                "shift_name": "phase22-day-shift",
                "target": "oncall-user-a",
                "starts_at": (now - timedelta(hours=1)).isoformat(),
                "ends_at": (now + timedelta(hours=1)).isoformat(),
                "timezone": "UTC",
                "is_active": True,
                "detail": {"team": "A"},
            },
            headers=auth_headers(token),
        )
        assert_status(shift_resp, 201)

        policy_resp = await client.post(
            "/api/alert/escalation-policies",
            json={
                "priority_level": "P3",
                "ack_timeout_seconds": 30,
                "repeat_threshold": 99,
                "max_escalation_level": 1,
                "escalation_channel": "IN_APP",
                "escalation_target": "oncall://active",
                "is_active": True,
                "detail": {},
            },
            headers=auth_headers(token),
        )
        assert_status(policy_resp, 201)

        aggregation_resp = await client.post(
            "/api/alert/aggregation-rules",
            json={
                "name": "phase22-low-battery-agg",
                "alert_type": "LOW_BATTERY",
                "window_seconds": 600,
                "is_active": True,
                "detail": {"noise_threshold": 2},
            },
            headers=auth_headers(token),
        )
        assert_status(aggregation_resp, 201)

        silence_resp = await client.post(
            "/api/alert/silence-rules",
            json={
                "name": "phase22-silence-other-drone",
                "alert_type": "LOW_BATTERY",
                "drone_id": "phase22-drone-silenced",
                "starts_at": (now - timedelta(hours=1)).isoformat(),
                "ends_at": (now + timedelta(hours=1)).isoformat(),
                "is_active": True,
                "detail": {},
            },
            headers=auth_headers(token),
        )
        assert_status(silence_resp, 201)

        rule_resp = await client.post(
            "/api/alert/routing-rules",
            json={
                "priority_level": "P3",
                "alert_type": "LOW_BATTERY",
                "channel": "IN_APP",
                "target": "oncall://active",
                "is_active": True,
                "detail": {},
            },
            headers=auth_headers(token),
        )
        assert_status(rule_resp, 201)

        payload = {
            "tenant_id": "spoofed",
            "drone_id": "phase22-drone-main",
            "position": {"lat": 30.123, "lon": 114.456, "alt_m": 120.5},
            "battery": {"percent": 12.0},
            "link": {"latency_ms": 50},
            "mode": "AUTO",
            "health": {"low_battery": True, "link_lost": False, "geofence_breach": False},
        }
        ingest_first = await client.post(
            "/api/telemetry/ingest",
            json=payload,
            headers=auth_headers(token),
        )
        assert_status(ingest_first, 200)
        ingest_second = await client.post(
            "/api/telemetry/ingest",
            json=payload,
            headers=auth_headers(token),
        )
        assert_status(ingest_second, 200)

        alerts_resp = await client.get("/api/alert/alerts", headers=auth_headers(token))
        assert_status(alerts_resp, 200)
        alerts = alerts_resp.json()
        if not alerts:
            raise RuntimeError("phase22 demo expected at least one alert")
        alert_id = alerts[0]["id"]
        detail = alerts[0].get("detail", {})
        if "aggregation" not in detail:
            raise RuntimeError("phase22 demo expected aggregation detail")

        routes_resp = await client.get(f"/api/alert/alerts/{alert_id}/routes", headers=auth_headers(token))
        assert_status(routes_resp, 200)
        routes = routes_resp.json()
        if not routes:
            raise RuntimeError("phase22 demo expected route logs")
        route_id = routes[0]["id"]

        receipt_resp = await client.post(
            f"/api/alert/routes/{route_id}:receipt",
            json={"delivery_status": "SENT", "receipt_id": "phase22-demo", "detail": {"source": "demo"}},
            headers=auth_headers(token),
        )
        assert_status(receipt_resp, 200)

        await asyncio.sleep(1.2)
        escalation_resp = await client.post(
            "/api/alert/alerts:escalation-run",
            json={"dry_run": False, "limit": 200},
            headers=auth_headers(token),
        )
        assert_status(escalation_resp, 200)

        ack_resp = await client.post(
            f"/api/alert/alerts/{alert_id}/ack",
            json={"comment": "phase22-demo-ack"},
            headers=auth_headers(token),
        )
        assert_status(ack_resp, 200)
        close_resp = await client.post(
            f"/api/alert/alerts/{alert_id}/close",
            json={"comment": "phase22-demo-close"},
            headers=auth_headers(token),
        )
        assert_status(close_resp, 200)

        sla_resp = await client.get("/api/alert/sla/overview", headers=auth_headers(token))
        assert_status(sla_resp, 200)
        if sla_resp.json().get("total_alerts", 0) < 1:
            raise RuntimeError("phase22 demo expected sla total_alerts >= 1")

    print("demo_phase22_alert_oncall_notification_v2: ok")


def main() -> None:
    asyncio.run(_run())


if __name__ == "__main__":
    main()
