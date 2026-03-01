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

        _tenant_id, token = await bootstrap_admin(client, "phase28")

        mission_resp = await client.post(
            "/api/mission/missions",
            json={
                "name": "phase28-mission",
                "type": "POINT_TASK",
                "payload": {"point": {"lat": 30.1, "lon": 114.2, "alt_m": 90}},
                "constraints": {},
            },
            headers=auth_headers(token),
        )
        assert_status(mission_resp, 201)
        mission_id = mission_resp.json()["id"]

        approval_resp = await client.post(
            "/api/approvals",
            json={"entity_type": "MISSION", "entity_id": mission_id, "status": "APPROVED"},
            headers=auth_headers(token),
        )
        assert_status(approval_resp, 200)

        approvals_resp = await client.get(
            f"/api/approvals?entity_type=MISSION&entity_id={mission_id}",
            headers=auth_headers(token),
        )
        assert_status(approvals_resp, 200)
        if not approvals_resp.json():
            raise RuntimeError("phase28 demo expected approval list not empty")

        audit_export_resp = await client.get("/api/approvals/audit-export", headers=auth_headers(token))
        assert_status(audit_export_resp, 200)
        if "file_path" not in audit_export_resp.json():
            raise RuntimeError("phase28 demo expected approval audit export file path")

        flow_template_resp = await client.post(
            "/api/compliance/approval-flows/templates",
            json={
                "name": "phase28-mission-flow",
                "entity_type": "MISSION",
                "steps": [{"name": "L1"}],
                "is_active": True,
            },
            headers=auth_headers(token),
        )
        assert_status(flow_template_resp, 201)
        flow_template_id = flow_template_resp.json()["id"]

        flow_instance_resp = await client.post(
            "/api/compliance/approval-flows/instances",
            json={
                "template_id": flow_template_id,
                "entity_type": "MISSION",
                "entity_id": mission_id,
            },
            headers=auth_headers(token),
        )
        assert_status(flow_instance_resp, 201)
        flow_instance_id = flow_instance_resp.json()["id"]

        flow_action_resp = await client.post(
            f"/api/compliance/approval-flows/instances/{flow_instance_id}/actions",
            json={"action": "APPROVE", "note": "phase28 approve"},
            headers=auth_headers(token),
        )
        assert_status(flow_action_resp, 200)
        if flow_action_resp.json()["status"] != "APPROVED":
            raise RuntimeError("phase28 demo expected approval flow instance approved")

        zone_resp = await client.post(
            "/api/compliance/zones",
            json={
                "name": "phase28-no-fly",
                "zone_type": "NO_FLY",
                "policy_layer": "TENANT",
                "policy_effect": "DENY",
                "geom_wkt": "POLYGON((114.19 30.09,114.21 30.09,114.21 30.11,114.19 30.11,114.19 30.09))",
            },
            headers=auth_headers(token),
        )
        assert_status(zone_resp, 201)

        zones_resp = await client.get("/api/compliance/zones?zone_type=NO_FLY", headers=auth_headers(token))
        assert_status(zones_resp, 200)
        if not zones_resp.json():
            raise RuntimeError("phase28 demo expected at least one airspace zone")

        preflight_template_resp = await client.post(
            "/api/compliance/preflight/templates",
            json={
                "name": "phase28-preflight-template",
                "description": "phase28 preflight",
                "items": [{"code": "CHK-P28", "title": "payload check"}],
                "template_version": "v1",
                "evidence_requirements": {"required": True},
                "require_approval_before_run": True,
                "is_active": True,
            },
            headers=auth_headers(token),
        )
        assert_status(preflight_template_resp, 201)
        preflight_template_id = preflight_template_resp.json()["id"]

        preflight_init_resp = await client.post(
            f"/api/compliance/missions/{mission_id}/preflight/init",
            json={"template_id": preflight_template_id},
            headers=auth_headers(token),
        )
        assert_status(preflight_init_resp, 200)

        preflight_check_resp = await client.post(
            f"/api/compliance/missions/{mission_id}/preflight/check-item",
            json={
                "item_code": "CHK-P28",
                "checked": True,
                "note": "phase28 checked",
                "evidence": {"photo_url": "https://example.invalid/phase28.jpg"},
            },
            headers=auth_headers(token),
        )
        assert_status(preflight_check_resp, 200)
        if preflight_check_resp.json()["status"] != "COMPLETED":
            raise RuntimeError("phase28 demo expected mission preflight completed")

        decisions_resp = await client.get(
            f"/api/compliance/decision-records?entity_type=MISSION&entity_id={mission_id}",
            headers=auth_headers(token),
        )
        assert_status(decisions_resp, 200)
        if not decisions_resp.json():
            raise RuntimeError("phase28 demo expected decision records for mission")

        decisions_export_resp = await client.get(
            f"/api/compliance/decision-records/export?entity_type=MISSION&entity_id={mission_id}",
            headers=auth_headers(token),
        )
        assert_status(decisions_export_resp, 200)
        if "file_path" not in decisions_export_resp.json():
            raise RuntimeError("phase28 demo expected decision export file path")

        now = datetime.now(UTC)
        oncall_resp = await client.post(
            "/api/alert/oncall/shifts",
            json={
                "shift_name": "phase28-day-shift",
                "target": "oncall://active",
                "starts_at": (now - timedelta(hours=1)).isoformat(),
                "ends_at": (now + timedelta(hours=1)).isoformat(),
                "timezone": "UTC",
                "is_active": True,
                "detail": {"team": "phase28"},
            },
            headers=auth_headers(token),
        )
        assert_status(oncall_resp, 201)

        escalation_policy_resp = await client.post(
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
        assert_status(escalation_policy_resp, 201)

        routing_rule_resp = await client.post(
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
        assert_status(routing_rule_resp, 201)

        silence_resp = await client.post(
            "/api/alert/silence-rules",
            json={
                "name": "phase28-silence-other-drone",
                "alert_type": "LOW_BATTERY",
                "drone_id": "phase28-drone-silenced",
                "starts_at": (now - timedelta(hours=1)).isoformat(),
                "ends_at": (now + timedelta(hours=1)).isoformat(),
                "is_active": True,
                "detail": {},
            },
            headers=auth_headers(token),
        )
        assert_status(silence_resp, 201)

        aggregation_resp = await client.post(
            "/api/alert/aggregation-rules",
            json={
                "name": "phase28-low-battery-agg",
                "alert_type": "LOW_BATTERY",
                "window_seconds": 600,
                "is_active": True,
                "detail": {},
            },
            headers=auth_headers(token),
        )
        assert_status(aggregation_resp, 201)

        drone_id = "phase28-drone-main"
        telemetry_payload = {
            "tenant_id": "spoofed",
            "drone_id": drone_id,
            "position": {"lat": 30.123, "lon": 114.456, "alt_m": 120.5},
            "battery": {"percent": 12.0},
            "link": {"latency_ms": 50},
            "mode": "AUTO",
            "health": {"low_battery": True, "link_lost": False, "geofence_breach": False},
        }
        ingest_first = await client.post("/api/telemetry/ingest", json=telemetry_payload, headers=auth_headers(token))
        assert_status(ingest_first, 200)
        ingest_second = await client.post("/api/telemetry/ingest", json=telemetry_payload, headers=auth_headers(token))
        assert_status(ingest_second, 200)

        alerts_resp = await client.get(
            f"/api/alert/alerts?drone_id={drone_id}&alert_status=OPEN",
            headers=auth_headers(token),
        )
        assert_status(alerts_resp, 200)
        alerts = alerts_resp.json()
        if not alerts:
            raise RuntimeError("phase28 demo expected open alert for target drone")
        alert_id = alerts[0]["id"]

        action_resp = await client.post(
            f"/api/alert/alerts/{alert_id}/actions",
            json={"action_type": "REVIEW", "note": "phase28 action", "detail": {"source": "demo"}},
            headers=auth_headers(token),
        )
        assert_status(action_resp, 200)

        actions_resp = await client.get(f"/api/alert/alerts/{alert_id}/actions", headers=auth_headers(token))
        assert_status(actions_resp, 200)
        if not actions_resp.json():
            raise RuntimeError("phase28 demo expected alert handling actions")

        routes_resp = await client.get(f"/api/alert/alerts/{alert_id}/routes", headers=auth_headers(token))
        assert_status(routes_resp, 200)
        routes = routes_resp.json()
        if not routes:
            raise RuntimeError("phase28 demo expected alert route logs")
        route_id = routes[0]["id"]

        receipt_resp = await client.post(
            f"/api/alert/routes/{route_id}:receipt",
            json={"delivery_status": "SENT", "receipt_id": "phase28-demo", "detail": {"source": "demo"}},
            headers=auth_headers(token),
        )
        assert_status(receipt_resp, 200)

        await asyncio.sleep(1.2)
        escalation_run_resp = await client.post(
            "/api/alert/alerts:escalation-run",
            json={"dry_run": False, "limit": 200},
            headers=auth_headers(token),
        )
        assert_status(escalation_run_resp, 200)

        review_resp = await client.get(f"/api/alert/alerts/{alert_id}/review", headers=auth_headers(token))
        assert_status(review_resp, 200)
        review = review_resp.json()
        if review.get("alert", {}).get("id") != alert_id:
            raise RuntimeError("phase28 demo expected review payload bound to alert")

        ack_resp = await client.post(
            f"/api/alert/alerts/{alert_id}/ack",
            json={"comment": "phase28 ack"},
            headers=auth_headers(token),
        )
        assert_status(ack_resp, 200)

        close_resp = await client.post(
            f"/api/alert/alerts/{alert_id}/close",
            json={"comment": "phase28 close"},
            headers=auth_headers(token),
        )
        assert_status(close_resp, 200)

        sla_resp = await client.get("/api/alert/sla/overview", headers=auth_headers(token))
        assert_status(sla_resp, 200)
        if sla_resp.json().get("total_alerts", 0) < 1:
            raise RuntimeError("phase28 demo expected alert sla total_alerts >= 1")

        ui_checks = [
            ("/ui/compliance", "Approval Flow Workbench"),
            ("/ui/compliance", "Decision Records"),
            ("/ui/alerts", "Alert Queue"),
            ("/ui/alerts", "Escalation Run"),
            (f"/ui/alerts?alert_status=CLOSED&drone_id={drone_id}", "Apply Filter"),
        ]
        for path, expected_text in ui_checks:
            response = await client.get(f"{path}{'&' if '?' in path else '?'}token={token}")
            assert_status(response, 200)
            if expected_text not in response.text:
                raise RuntimeError(f"phase28 demo expected '{expected_text}' in {path}")

    print("demo_phase28_compliance_alert_operations_workbench: ok")


def main() -> None:
    asyncio.run(_run())


if __name__ == "__main__":
    main()
