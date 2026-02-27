from __future__ import annotations

from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine, select

from app import main as app_main
from app.domain.models import AlertOncallShift, AlertRecord, EventRecord
from app.infra import audit, db, events, redis_state


class FakeRedis:
    def __init__(self) -> None:
        self._store: dict[str, str] = {}

    def set(self, key: str, value: str) -> bool:
        self._store[key] = value
        return True

    def get(self, key: str) -> str | None:
        return self._store.get(key)

    def ping(self) -> bool:
        return True


@pytest.fixture()
def alert_oncall_client(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> Generator[TestClient, None, None]:
    db_path = tmp_path / "alert_oncall_test.db"
    test_engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
    )
    SQLModel.metadata.create_all(test_engine)
    fake_redis = FakeRedis()

    monkeypatch.setattr(db, "engine", test_engine)
    monkeypatch.setattr(audit, "engine", test_engine)
    monkeypatch.setattr(events, "engine", test_engine)
    monkeypatch.setattr(redis_state, "get_redis", lambda: fake_redis)

    client = TestClient(app_main.app)
    yield client
    client.close()


def _auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _create_tenant(client: TestClient, name: str) -> str:
    response = client.post("/api/identity/tenants", json={"name": name})
    assert response.status_code == 201
    return response.json()["id"]


def _bootstrap_admin(client: TestClient, tenant_id: str, username: str, password: str) -> None:
    response = client.post(
        "/api/identity/bootstrap-admin",
        json={"tenant_id": tenant_id, "username": username, "password": password},
    )
    assert response.status_code == 201


def _login(client: TestClient, tenant_id: str, username: str, password: str) -> str:
    response = client.post(
        "/api/identity/dev-login",
        json={"tenant_id": tenant_id, "username": username, "password": password},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def _ingest_payload(drone_id: str, *, battery_percent: float) -> dict[str, object]:
    return {
        "tenant_id": "spoofed",
        "drone_id": drone_id,
        "position": {"lat": 30.123, "lon": 114.456, "alt_m": 120.5},
        "battery": {"percent": battery_percent},
        "link": {"latency_ms": 50},
        "mode": "AUTO",
        "health": {
            "low_battery": battery_percent <= 20.0,
            "link_lost": False,
            "geofence_breach": False,
        },
    }


def test_alert_oncall_timeout_escalation(alert_oncall_client: TestClient) -> None:
    tenant_id = _create_tenant(alert_oncall_client, "alert-oncall-timeout-tenant")
    _bootstrap_admin(alert_oncall_client, tenant_id, "admin", "admin-pass")
    token = _login(alert_oncall_client, tenant_id, "admin", "admin-pass")
    now = datetime.now(UTC)

    shift_resp = alert_oncall_client.post(
        "/api/alert/oncall/shifts",
        json={
            "shift_name": "day-shift",
            "target": "oncall-user-a",
            "starts_at": (now - timedelta(hours=1)).isoformat(),
            "ends_at": (now + timedelta(hours=1)).isoformat(),
            "timezone": "UTC",
            "is_active": True,
            "detail": {"team": "A"},
        },
        headers=_auth_header(token),
    )
    assert shift_resp.status_code == 201

    policy_resp = alert_oncall_client.post(
        "/api/alert/escalation-policies",
        json={
            "priority_level": "P3",
            "ack_timeout_seconds": 30,
            "repeat_threshold": 50,
            "max_escalation_level": 2,
            "escalation_channel": "IN_APP",
            "escalation_target": "oncall://active",
            "is_active": True,
            "detail": {"source": "test"},
        },
        headers=_auth_header(token),
    )
    assert policy_resp.status_code == 201

    rule_resp = alert_oncall_client.post(
        "/api/alert/routing-rules",
        json={
            "priority_level": "P3",
            "alert_type": "LOW_BATTERY",
            "channel": "IN_APP",
            "target": "oncall://active",
            "is_active": True,
            "detail": {},
        },
        headers=_auth_header(token),
    )
    assert rule_resp.status_code == 201

    ingest_resp = alert_oncall_client.post(
        "/api/telemetry/ingest",
        json=_ingest_payload("drone-oncall-1", battery_percent=10.0),
        headers=_auth_header(token),
    )
    assert ingest_resp.status_code == 200

    alerts_resp = alert_oncall_client.get("/api/alert/alerts", headers=_auth_header(token))
    assert alerts_resp.status_code == 200
    alerts = alerts_resp.json()
    assert len(alerts) == 1
    alert_id = alerts[0]["id"]

    routes_resp = alert_oncall_client.get(
        f"/api/alert/alerts/{alert_id}/routes",
        headers=_auth_header(token),
    )
    assert routes_resp.status_code == 200
    first_route = routes_resp.json()[0]
    assert first_route["target"] == "oncall-user-a"

    with Session(db.engine) as session:
        row = session.exec(select(AlertRecord).where(AlertRecord.id == alert_id)).first()
        assert row is not None
        row.routed_at = datetime.now(UTC) - timedelta(minutes=2)
        session.add(row)
        session.commit()

    run_resp = alert_oncall_client.post(
        "/api/alert/alerts:escalation-run",
        json={"dry_run": False, "limit": 50},
        headers=_auth_header(token),
    )
    assert run_resp.status_code == 200
    run_body = run_resp.json()
    assert run_body["scanned_count"] >= 1
    assert run_body["escalated_count"] == 1
    assert run_body["items"][0]["alert_id"] == alert_id
    assert run_body["items"][0]["reason"] == "ACK_TIMEOUT"

    actions_resp = alert_oncall_client.get(
        f"/api/alert/alerts/{alert_id}/actions",
        headers=_auth_header(token),
    )
    assert actions_resp.status_code == 200
    action_types = {item["action_type"] for item in actions_resp.json()}
    assert "ESCALATE" in action_types

    with Session(db.engine) as session:
        rows = list(session.exec(select(EventRecord).where(EventRecord.tenant_id == tenant_id)).all())
    related = [row for row in rows if row.payload.get("alert_id") == alert_id]
    event_types = {row.event_type for row in related}
    assert "alert.escalated" in event_types


def test_alert_oncall_shift_handover_escalation(alert_oncall_client: TestClient) -> None:
    tenant_id = _create_tenant(alert_oncall_client, "alert-oncall-handover-tenant")
    _bootstrap_admin(alert_oncall_client, tenant_id, "admin", "admin-pass")
    token = _login(alert_oncall_client, tenant_id, "admin", "admin-pass")
    now = datetime.now(UTC)

    shift_a_resp = alert_oncall_client.post(
        "/api/alert/oncall/shifts",
        json={
            "shift_name": "shift-a",
            "target": "oncall-user-a",
            "starts_at": (now - timedelta(hours=1)).isoformat(),
            "ends_at": (now + timedelta(hours=1)).isoformat(),
            "timezone": "UTC",
            "is_active": True,
            "detail": {},
        },
        headers=_auth_header(token),
    )
    assert shift_a_resp.status_code == 201
    shift_a_id = shift_a_resp.json()["id"]

    shift_b_resp = alert_oncall_client.post(
        "/api/alert/oncall/shifts",
        json={
            "shift_name": "shift-b",
            "target": "oncall-user-b",
            "starts_at": (now + timedelta(hours=1)).isoformat(),
            "ends_at": (now + timedelta(hours=3)).isoformat(),
            "timezone": "UTC",
            "is_active": True,
            "detail": {},
        },
        headers=_auth_header(token),
    )
    assert shift_b_resp.status_code == 201
    shift_b_id = shift_b_resp.json()["id"]

    policy_resp = alert_oncall_client.post(
        "/api/alert/escalation-policies",
        json={
            "priority_level": "P3",
            "ack_timeout_seconds": 3600,
            "repeat_threshold": 99,
            "max_escalation_level": 2,
            "escalation_channel": "IN_APP",
            "escalation_target": "oncall://active",
            "is_active": True,
            "detail": {},
        },
        headers=_auth_header(token),
    )
    assert policy_resp.status_code == 201

    rule_resp = alert_oncall_client.post(
        "/api/alert/routing-rules",
        json={
            "priority_level": "P3",
            "alert_type": "LOW_BATTERY",
            "channel": "IN_APP",
            "target": "oncall://active",
            "is_active": True,
            "detail": {},
        },
        headers=_auth_header(token),
    )
    assert rule_resp.status_code == 201

    ingest_resp = alert_oncall_client.post(
        "/api/telemetry/ingest",
        json=_ingest_payload("drone-oncall-2", battery_percent=10.0),
        headers=_auth_header(token),
    )
    assert ingest_resp.status_code == 200

    alerts_resp = alert_oncall_client.get("/api/alert/alerts", headers=_auth_header(token))
    assert alerts_resp.status_code == 200
    alert_id = alerts_resp.json()[0]["id"]

    with Session(db.engine) as session:
        shift_a = session.exec(select(AlertOncallShift).where(AlertOncallShift.id == shift_a_id)).first()
        shift_b = session.exec(select(AlertOncallShift).where(AlertOncallShift.id == shift_b_id)).first()
        assert shift_a is not None
        assert shift_b is not None
        shift_a.ends_at = datetime.now(UTC) - timedelta(minutes=1)
        shift_b.starts_at = datetime.now(UTC) - timedelta(minutes=1)
        session.add(shift_a)
        session.add(shift_b)
        session.commit()

    run_resp = alert_oncall_client.post(
        "/api/alert/alerts:escalation-run",
        json={"dry_run": False, "limit": 50},
        headers=_auth_header(token),
    )
    assert run_resp.status_code == 200
    run_body = run_resp.json()
    assert run_body["escalated_count"] == 1
    assert run_body["items"][0]["alert_id"] == alert_id
    assert run_body["items"][0]["reason"] == "SHIFT_HANDOVER"
    assert run_body["items"][0]["to_target"] == "oncall-user-b"


def test_alert_webhook_route_and_receipt(alert_oncall_client: TestClient) -> None:
    tenant_id = _create_tenant(alert_oncall_client, "alert-webhook-tenant")
    _bootstrap_admin(alert_oncall_client, tenant_id, "admin", "admin-pass")
    token = _login(alert_oncall_client, tenant_id, "admin", "admin-pass")

    policy_resp = alert_oncall_client.post(
        "/api/alert/escalation-policies",
        json={
            "priority_level": "P3",
            "ack_timeout_seconds": 3600,
            "repeat_threshold": 99,
            "max_escalation_level": 1,
            "escalation_channel": "IN_APP",
            "escalation_target": "duty-default",
            "is_active": True,
            "detail": {},
        },
        headers=_auth_header(token),
    )
    assert policy_resp.status_code == 201

    rule_resp = alert_oncall_client.post(
        "/api/alert/routing-rules",
        json={
            "priority_level": "P3",
            "alert_type": "LOW_BATTERY",
            "channel": "WEBHOOK",
            "target": "https://example.invalid/hook",
            "is_active": True,
            "detail": {},
        },
        headers=_auth_header(token),
    )
    assert rule_resp.status_code == 201

    ingest_resp = alert_oncall_client.post(
        "/api/telemetry/ingest",
        json=_ingest_payload("drone-webhook-1", battery_percent=9.0),
        headers=_auth_header(token),
    )
    assert ingest_resp.status_code == 200

    alerts_resp = alert_oncall_client.get("/api/alert/alerts", headers=_auth_header(token))
    assert alerts_resp.status_code == 200
    alert_id = alerts_resp.json()[0]["id"]

    routes_resp = alert_oncall_client.get(
        f"/api/alert/alerts/{alert_id}/routes",
        headers=_auth_header(token),
    )
    assert routes_resp.status_code == 200
    routes = routes_resp.json()
    assert len(routes) == 1
    route = routes[0]
    assert route["channel"] == "WEBHOOK"
    assert route["delivery_status"] == "SENT"
    assert route["detail"]["delivery_mode"] == "webhook_simulated"

    receipt_resp = alert_oncall_client.post(
        f"/api/alert/routes/{route['id']}:receipt",
        json={
            "delivery_status": "FAILED",
            "receipt_id": "ack-001",
            "detail": {"code": "DELIVERY_TIMEOUT"},
        },
        headers=_auth_header(token),
    )
    assert receipt_resp.status_code == 200
    receipt_body = receipt_resp.json()
    assert receipt_body["delivery_status"] == "FAILED"
    assert receipt_body["detail"]["receipt"]["receipt_id"] == "ack-001"
