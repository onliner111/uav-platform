from __future__ import annotations

from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlmodel import SQLModel, create_engine

from app import main as app_main
from app.infra import audit, db, events


@pytest.fixture()
def observability_client(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> Generator[TestClient, None, None]:
    db_path = tmp_path / "observability_test.db"
    test_engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
    )

    @event.listens_for(test_engine, "connect")
    def _enable_foreign_keys(dbapi_connection: object, _connection_record: object) -> None:
        cursor = dbapi_connection.cursor()  # type: ignore[attr-defined]
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    SQLModel.metadata.create_all(test_engine)
    monkeypatch.setattr(db, "engine", test_engine)
    monkeypatch.setattr(audit, "engine", test_engine)
    monkeypatch.setattr(events, "engine", test_engine)

    client = TestClient(app_main.app)
    yield client
    client.close()
    app_main.app.dependency_overrides.clear()


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


def test_observability_phase25_full_chain(observability_client: TestClient) -> None:
    tenant_id = _create_tenant(observability_client, "phase25-observability")
    _bootstrap_admin(observability_client, tenant_id, "admin-obv", "admin-pass")
    token = _login(observability_client, tenant_id, "admin-obv", "admin-pass")

    now = datetime.now(UTC)
    shift_resp = observability_client.post(
        "/api/alert/oncall/shifts",
        json={
            "shift_name": "phase25-day",
            "target": "oncall-phase25",
            "starts_at": (now - timedelta(hours=1)).isoformat(),
            "ends_at": (now + timedelta(hours=2)).isoformat(),
            "timezone": "UTC",
            "is_active": True,
            "detail": {},
        },
        headers=_auth_header(token),
    )
    assert shift_resp.status_code == 201

    ingest_resp = observability_client.post(
        "/api/observability/signals:ingest",
        json={
            "items": [
                {
                    "signal_type": "METRIC",
                    "level": "INFO",
                    "service_name": "mission-dispatch",
                    "signal_name": "request",
                    "status_code": 200,
                    "duration_ms": 120,
                    "numeric_value": 1.0,
                    "unit": "count",
                    "occurred_at": now.isoformat(),
                },
                {
                    "signal_type": "METRIC",
                    "level": "ERROR",
                    "service_name": "mission-dispatch",
                    "signal_name": "request",
                    "status_code": 500,
                    "duration_ms": 900,
                    "numeric_value": 1.0,
                    "unit": "count",
                    "occurred_at": now.isoformat(),
                },
                {
                    "signal_type": "TRACE",
                    "level": "INFO",
                    "service_name": "mission-dispatch",
                    "signal_name": "request",
                    "trace_id": "trace-001",
                    "span_id": "span-001",
                    "duration_ms": 220,
                    "occurred_at": now.isoformat(),
                },
            ]
        },
        headers=_auth_header(token),
    )
    assert ingest_resp.status_code == 201
    assert ingest_resp.json()["accepted_count"] == 3

    list_resp = observability_client.get(
        "/api/observability/signals?service_name=mission-dispatch",
        headers=_auth_header(token),
    )
    assert list_resp.status_code == 200
    assert len(list_resp.json()) == 3

    overview_resp = observability_client.get(
        "/api/observability/overview?window_minutes=120",
        headers=_auth_header(token),
    )
    assert overview_resp.status_code == 200
    overview = overview_resp.json()
    assert overview["total_signals"] >= 3
    assert overview["error_signals"] >= 1

    policy_resp = observability_client.post(
        "/api/observability/slo/policies",
        json={
            "policy_key": "dispatch-availability",
            "service_name": "mission-dispatch",
            "signal_name": "request",
            "target_ratio": 0.95,
            "window_minutes": 60,
            "minimum_samples": 1,
            "alert_severity": "P2",
        },
        headers=_auth_header(token),
    )
    assert policy_resp.status_code == 201

    eval_resp = observability_client.post(
        "/api/observability/slo:evaluate",
        json={"dry_run": False},
        headers=_auth_header(token),
    )
    assert eval_resp.status_code == 200
    eval_body = eval_resp.json()
    assert eval_body["evaluated_count"] >= 1
    assert eval_body["breached_count"] >= 1
    assert eval_body["alerts_created"] >= 1

    alerts_resp = observability_client.get(
        "/api/observability/alerts?source=SLO",
        headers=_auth_header(token),
    )
    assert alerts_resp.status_code == 200
    alerts = alerts_resp.json()
    assert len(alerts) >= 1
    assert alerts[0]["target"] == "oncall-phase25"

    backup_resp = observability_client.post(
        "/api/observability/backups:runs",
        json={"run_type": "FULL", "is_drill": True},
        headers=_auth_header(token),
    )
    assert backup_resp.status_code == 201
    backup_id = backup_resp.json()["id"]

    restore_resp = observability_client.post(
        f"/api/observability/backups/runs/{backup_id}:restore-drill",
        json={"objective_rto_seconds": 300, "simulated_restore_seconds": 180},
        headers=_auth_header(token),
    )
    assert restore_resp.status_code == 201
    assert restore_resp.json()["status"] == "PASSED"

    sec_resp = observability_client.post(
        "/api/observability/security-inspections:runs",
        json={"baseline_version": "phase25-v1"},
        headers=_auth_header(token),
    )
    assert sec_resp.status_code == 201
    sec_body = sec_resp.json()
    assert sec_body["total_checks"] >= 1
    assert len(sec_body["items"]) == sec_body["total_checks"]

    policy_upsert_resp = observability_client.put(
        "/api/observability/capacity/policies/cpu.utilization",
        json={
            "target_utilization_pct": 75,
            "scale_out_threshold_pct": 85,
            "scale_in_threshold_pct": 50,
            "min_replicas": 1,
            "max_replicas": 5,
            "current_replicas": 2,
            "is_active": True,
        },
        headers=_auth_header(token),
    )
    assert policy_upsert_resp.status_code == 200

    cpu_metrics_resp = observability_client.post(
        "/api/observability/signals:ingest",
        json={
            "items": [
                {
                    "signal_type": "METRIC",
                    "level": "INFO",
                    "service_name": "platform-runtime",
                    "signal_name": "cpu.utilization",
                    "numeric_value": 92.0,
                    "unit": "percent",
                    "occurred_at": now.isoformat(),
                },
                {
                    "signal_type": "METRIC",
                    "level": "INFO",
                    "service_name": "platform-runtime",
                    "signal_name": "cpu.utilization",
                    "numeric_value": 90.0,
                    "unit": "percent",
                    "occurred_at": now.isoformat(),
                },
            ]
        },
        headers=_auth_header(token),
    )
    assert cpu_metrics_resp.status_code == 201

    forecast_resp = observability_client.post(
        "/api/observability/capacity:forecast",
        json={"meter_key": "cpu.utilization", "window_minutes": 60, "sample_minutes": 180},
        headers=_auth_header(token),
    )
    assert forecast_resp.status_code == 201
    forecast = forecast_resp.json()
    assert forecast["decision"] == "SCALE_OUT"
    assert forecast["recommended_replicas"] == 3

    forecast_list_resp = observability_client.get(
        "/api/observability/capacity/forecasts?meter_key=cpu.utilization",
        headers=_auth_header(token),
    )
    assert forecast_list_resp.status_code == 200
    assert any(item["id"] == forecast["id"] for item in forecast_list_resp.json())


def test_observability_tenant_boundary(observability_client: TestClient) -> None:
    tenant_a = _create_tenant(observability_client, "phase25-obv-a")
    _bootstrap_admin(observability_client, tenant_a, "admin-a", "admin-pass")
    token_a = _login(observability_client, tenant_a, "admin-a", "admin-pass")

    tenant_b = _create_tenant(observability_client, "phase25-obv-b")
    _bootstrap_admin(observability_client, tenant_b, "admin-b", "admin-pass")
    token_b = _login(observability_client, tenant_b, "admin-b", "admin-pass")

    ingest_a = observability_client.post(
        "/api/observability/signals:ingest",
        json={
            "items": [
                {
                    "signal_type": "LOG",
                    "level": "INFO",
                    "service_name": "tenant-a-service",
                    "signal_name": "heartbeat",
                    "message": "ok",
                }
            ]
        },
        headers=_auth_header(token_a),
    )
    assert ingest_a.status_code == 201

    backup_a = observability_client.post(
        "/api/observability/backups:runs",
        json={"run_type": "FULL"},
        headers=_auth_header(token_a),
    )
    assert backup_a.status_code == 201
    backup_a_id = backup_a.json()["id"]

    list_b = observability_client.get(
        "/api/observability/signals?service_name=tenant-a-service",
        headers=_auth_header(token_b),
    )
    assert list_b.status_code == 200
    assert list_b.json() == []

    restore_b = observability_client.post(
        f"/api/observability/backups/runs/{backup_a_id}:restore-drill",
        json={"objective_rto_seconds": 120, "simulated_restore_seconds": 60},
        headers=_auth_header(token_b),
    )
    assert restore_b.status_code == 404

    alerts_b = observability_client.get(
        "/api/observability/alerts",
        headers=_auth_header(token_b),
    )
    assert alerts_b.status_code == 200
    assert alerts_b.json() == []
