from __future__ import annotations

from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine, select

from app import main as app_main
from app.domain.models import AlertRecord, EventRecord
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
def alert_wp3_client(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> Generator[TestClient, None, None]:
    db_path = tmp_path / "alert_wp3_test.db"
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


def test_alert_silence_rule_suppresses_trigger(alert_wp3_client: TestClient) -> None:
    tenant_id = _create_tenant(alert_wp3_client, "alert-wp3-silence-tenant")
    _bootstrap_admin(alert_wp3_client, tenant_id, "admin", "admin-pass")
    token = _login(alert_wp3_client, tenant_id, "admin", "admin-pass")
    now = datetime.now(UTC)

    silence_resp = alert_wp3_client.post(
        "/api/alert/silence-rules",
        json={
            "name": "night-silence",
            "alert_type": "LOW_BATTERY",
            "drone_id": "drone-silence-1",
            "starts_at": (now - timedelta(minutes=30)).isoformat(),
            "ends_at": (now + timedelta(minutes=30)).isoformat(),
            "is_active": True,
            "detail": {"source": "test"},
        },
        headers=_auth_header(token),
    )
    assert silence_resp.status_code == 201

    ingest_resp = alert_wp3_client.post(
        "/api/telemetry/ingest",
        json=_ingest_payload("drone-silence-1", battery_percent=8.0),
        headers=_auth_header(token),
    )
    assert ingest_resp.status_code == 200

    alerts_resp = alert_wp3_client.get("/api/alert/alerts", headers=_auth_header(token))
    assert alerts_resp.status_code == 200
    assert alerts_resp.json() == []

    with Session(db.engine) as session:
        events_rows = list(session.exec(select(EventRecord).where(EventRecord.tenant_id == tenant_id)).all())
    event_types = {row.event_type for row in events_rows}
    assert "alert.suppressed" in event_types


def test_alert_aggregation_rule_accumulates_repeat_count(alert_wp3_client: TestClient) -> None:
    tenant_id = _create_tenant(alert_wp3_client, "alert-wp3-aggregation-tenant")
    _bootstrap_admin(alert_wp3_client, tenant_id, "admin", "admin-pass")
    token = _login(alert_wp3_client, tenant_id, "admin", "admin-pass")

    aggregation_resp = alert_wp3_client.post(
        "/api/alert/aggregation-rules",
        json={
            "name": "low-battery-agg",
            "alert_type": "LOW_BATTERY",
            "window_seconds": 600,
            "is_active": True,
            "detail": {"source": "test"},
        },
        headers=_auth_header(token),
    )
    assert aggregation_resp.status_code == 201

    first_ingest = alert_wp3_client.post(
        "/api/telemetry/ingest",
        json=_ingest_payload("drone-aggregation-1", battery_percent=11.0),
        headers=_auth_header(token),
    )
    assert first_ingest.status_code == 200
    second_ingest = alert_wp3_client.post(
        "/api/telemetry/ingest",
        json=_ingest_payload("drone-aggregation-1", battery_percent=10.0),
        headers=_auth_header(token),
    )
    assert second_ingest.status_code == 200

    alerts_resp = alert_wp3_client.get("/api/alert/alerts", headers=_auth_header(token))
    assert alerts_resp.status_code == 200
    alerts = alerts_resp.json()
    assert len(alerts) == 1
    detail = alerts[0]["detail"]
    assert detail["repeat_count"] >= 2
    assert detail["aggregation"]["rule_name"] == "low-battery-agg"
    assert detail["aggregation"]["aggregated_count"] >= 1


def test_alert_noise_suppression_optimization(alert_wp3_client: TestClient) -> None:
    tenant_id = _create_tenant(alert_wp3_client, "alert-wp3-noise-tenant")
    _bootstrap_admin(alert_wp3_client, tenant_id, "admin", "admin-pass")
    token = _login(alert_wp3_client, tenant_id, "admin", "admin-pass")

    aggregation_resp = alert_wp3_client.post(
        "/api/alert/aggregation-rules",
        json={
            "name": "noise-agg",
            "alert_type": "LOW_BATTERY",
            "window_seconds": 600,
            "is_active": True,
            "detail": {"noise_threshold": 2},
        },
        headers=_auth_header(token),
    )
    assert aggregation_resp.status_code == 201

    first_ingest = alert_wp3_client.post(
        "/api/telemetry/ingest",
        json=_ingest_payload("drone-noise-1", battery_percent=12.0),
        headers=_auth_header(token),
    )
    assert first_ingest.status_code == 200
    second_ingest = alert_wp3_client.post(
        "/api/telemetry/ingest",
        json=_ingest_payload("drone-noise-1", battery_percent=11.5),
        headers=_auth_header(token),
    )
    assert second_ingest.status_code == 200
    third_ingest = alert_wp3_client.post(
        "/api/telemetry/ingest",
        json=_ingest_payload("drone-noise-1", battery_percent=11.0),
        headers=_auth_header(token),
    )
    assert third_ingest.status_code == 200

    alerts_resp = alert_wp3_client.get("/api/alert/alerts", headers=_auth_header(token))
    assert alerts_resp.status_code == 200
    alerts = alerts_resp.json()
    assert len(alerts) == 1
    detail = alerts[0]["detail"]
    assert detail["noise_control"]["suppressed"] is True
    assert detail["noise_control"]["threshold"] == 2

    with Session(db.engine) as session:
        events_rows = list(session.exec(select(EventRecord).where(EventRecord.tenant_id == tenant_id)).all())
    event_types = {row.event_type for row in events_rows}
    assert "alert.noise_suppressed" in event_types


def test_alert_sla_overview_includes_timeout_escalation(alert_wp3_client: TestClient) -> None:
    tenant_id = _create_tenant(alert_wp3_client, "alert-wp3-sla-tenant")
    _bootstrap_admin(alert_wp3_client, tenant_id, "admin", "admin-pass")
    token = _login(alert_wp3_client, tenant_id, "admin", "admin-pass")
    now = datetime.now(UTC)

    policy_resp = alert_wp3_client.post(
        "/api/alert/escalation-policies",
        json={
            "priority_level": "P3",
            "ack_timeout_seconds": 30,
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

    ingest_resp = alert_wp3_client.post(
        "/api/telemetry/ingest",
        json=_ingest_payload("drone-sla-1", battery_percent=9.0),
        headers=_auth_header(token),
    )
    assert ingest_resp.status_code == 200

    alerts_resp = alert_wp3_client.get("/api/alert/alerts", headers=_auth_header(token))
    assert alerts_resp.status_code == 200
    alert_id = alerts_resp.json()[0]["id"]

    with Session(db.engine) as session:
        row = session.exec(select(AlertRecord).where(AlertRecord.id == alert_id)).first()
        assert row is not None
        row.first_seen_at = now - timedelta(minutes=3)
        row.routed_at = now - timedelta(minutes=3)
        session.add(row)
        session.commit()

    escalation_run = alert_wp3_client.post(
        "/api/alert/alerts:escalation-run",
        json={"dry_run": False, "limit": 100},
        headers=_auth_header(token),
    )
    assert escalation_run.status_code == 200
    assert escalation_run.json()["escalated_count"] >= 1

    ack_resp = alert_wp3_client.post(
        f"/api/alert/alerts/{alert_id}/ack",
        json={"comment": "acked"},
        headers=_auth_header(token),
    )
    assert ack_resp.status_code == 200
    close_resp = alert_wp3_client.post(
        f"/api/alert/alerts/{alert_id}/close",
        json={"comment": "closed"},
        headers=_auth_header(token),
    )
    assert close_resp.status_code == 200

    sla_resp = alert_wp3_client.get(
        "/api/alert/sla/overview",
        params={
            "from_ts": (now - timedelta(hours=1)).isoformat(),
            "to_ts": (now + timedelta(hours=1)).isoformat(),
        },
        headers=_auth_header(token),
    )
    assert sla_resp.status_code == 200
    body = sla_resp.json()
    assert body["total_alerts"] >= 1
    assert body["acked_alerts"] >= 1
    assert body["closed_alerts"] >= 1
    assert body["timeout_escalated_alerts"] >= 1
    assert body["mtta_seconds_avg"] > 0
    assert body["mttr_seconds_avg"] > 0
