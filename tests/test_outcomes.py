from __future__ import annotations

from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlmodel import SQLModel, create_engine

from app import main as app_main
from app.infra import audit, db, events


@pytest.fixture()
def outcomes_client(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> Generator[TestClient, None, None]:
    db_path = tmp_path / "outcomes_test.db"
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


def _create_template(client: TestClient, token: str, name: str) -> str:
    response = client.post(
        "/api/inspection/templates",
        json={"name": name, "category": "phase13", "description": "phase13", "is_active": True},
        headers=_auth_header(token),
    )
    assert response.status_code == 201
    return response.json()["id"]


def _create_task(client: TestClient, token: str, template_id: str, name: str) -> str:
    response = client.post(
        "/api/inspection/tasks",
        json={
            "name": name,
            "template_id": template_id,
            "area_geom": "POLYGON((114.30 30.58,114.31 30.58,114.31 30.59,114.30 30.59,114.30 30.58))",
            "priority": 3,
            "status": "SCHEDULED",
        },
        headers=_auth_header(token),
    )
    assert response.status_code == 201
    return response.json()["id"]


def _create_mission(client: TestClient, token: str, name: str) -> str:
    response = client.post(
        "/api/mission/missions",
        json={
            "name": name,
            "type": "POINT_TASK",
            "payload": {"point": {"lat": 30.2, "lon": 114.3, "alt_m": 120}},
            "constraints": {},
        },
        headers=_auth_header(token),
    )
    assert response.status_code == 201
    return response.json()["id"]


def test_observation_auto_materializes_outcome_and_status_update(outcomes_client: TestClient) -> None:
    tenant_id = _create_tenant(outcomes_client, "phase13-outcome-auto")
    _bootstrap_admin(outcomes_client, tenant_id, "admin", "admin-pass")
    token = _login(outcomes_client, tenant_id, "admin", "admin-pass")

    template_id = _create_template(outcomes_client, token, "phase13-template")
    task_id = _create_task(outcomes_client, token, template_id, "phase13-task")

    obs_resp = outcomes_client.post(
        f"/api/inspection/tasks/{task_id}/observations",
        json={
            "position_lat": 30.5801,
            "position_lon": 114.3001,
            "alt_m": 50.0,
            "item_code": "P13-A",
            "severity": 2,
            "note": "phase13 observation",
            "confidence": 0.88,
        },
        headers=_auth_header(token),
    )
    assert obs_resp.status_code == 201
    obs_id = obs_resp.json()["id"]

    outcomes_resp = outcomes_client.get(
        f"/api/outcomes/records?task_id={task_id}",
        headers=_auth_header(token),
    )
    assert outcomes_resp.status_code == 200
    outcomes = outcomes_resp.json()
    assert len(outcomes) == 1
    assert outcomes[0]["source_type"] == "INSPECTION_OBSERVATION"
    assert outcomes[0]["source_id"] == obs_id
    assert outcomes[0]["status"] == "NEW"

    outcome_id = outcomes[0]["id"]
    status_resp = outcomes_client.patch(
        f"/api/outcomes/records/{outcome_id}/status",
        json={"status": "IN_REVIEW", "note": "triaged"},
        headers=_auth_header(token),
    )
    assert status_resp.status_code == 200
    assert status_resp.json()["status"] == "IN_REVIEW"

    remat_resp = outcomes_client.post(
        f"/api/outcomes/records/from-observation/{obs_id}",
        headers=_auth_header(token),
    )
    assert remat_resp.status_code == 200
    assert remat_resp.json()["id"] == outcome_id


def test_raw_data_catalog_create_and_filter(outcomes_client: TestClient) -> None:
    tenant_id = _create_tenant(outcomes_client, "phase13-raw-filter")
    _bootstrap_admin(outcomes_client, tenant_id, "admin", "admin-pass")
    token = _login(outcomes_client, tenant_id, "admin", "admin-pass")

    template_id = _create_template(outcomes_client, token, "phase13-template-raw")
    task_id = _create_task(outcomes_client, token, template_id, "phase13-task-raw")
    mission_id = _create_mission(outcomes_client, token, "phase13-mission-raw")

    create_raw_resp = outcomes_client.post(
        "/api/outcomes/raw",
        json={
            "task_id": task_id,
            "mission_id": mission_id,
            "data_type": "IMAGE",
            "source_uri": "s3://bucket/phase13/image-001.jpg",
            "checksum": "sha256:phase13",
            "meta": {"camera": "payload-a"},
        },
        headers=_auth_header(token),
    )
    assert create_raw_resp.status_code == 201
    raw_id = create_raw_resp.json()["id"]

    list_raw_resp = outcomes_client.get(
        f"/api/outcomes/raw?task_id={task_id}&data_type=IMAGE",
        headers=_auth_header(token),
    )
    assert list_raw_resp.status_code == 200
    rows = list_raw_resp.json()
    assert len(rows) == 1
    assert rows[0]["id"] == raw_id


def test_alert_priority_and_routing_rules(outcomes_client: TestClient) -> None:
    tenant_id = _create_tenant(outcomes_client, "phase13-alert-route")
    _bootstrap_admin(outcomes_client, tenant_id, "admin", "admin-pass")
    token = _login(outcomes_client, tenant_id, "admin", "admin-pass")

    rule_resp = outcomes_client.post(
        "/api/alert/routing-rules",
        json={
            "priority_level": "P1",
            "channel": "IN_APP",
            "target": "duty-ops-team",
            "is_active": True,
            "detail": {"rotation": "night-shift"},
        },
        headers=_auth_header(token),
    )
    assert rule_resp.status_code == 201
    email_rule_resp = outcomes_client.post(
        "/api/alert/routing-rules",
        json={
            "priority_level": "P1",
            "channel": "EMAIL",
            "target": "ops@example.com",
            "is_active": True,
        },
        headers=_auth_header(token),
    )
    assert email_rule_resp.status_code == 201

    ingest_critical = outcomes_client.post(
        "/api/telemetry/ingest",
        json={
            "tenant_id": "spoofed",
            "drone_id": "phase13-drone-1",
            "position": {"lat": 30.12, "lon": 114.45, "alt_m": 120.0},
            "battery": {"percent": 80.0},
            "link": {"latency_ms": 3000},
            "mode": "LINK_LOST",
            "health": {"link_lost": True},
        },
        headers=_auth_header(token),
    )
    assert ingest_critical.status_code == 200

    list_resp = outcomes_client.get("/api/alert/alerts", headers=_auth_header(token))
    assert list_resp.status_code == 200
    critical = [item for item in list_resp.json() if item["alert_type"] == "LINK_LOSS"]
    assert len(critical) == 1
    alert_id = critical[0]["id"]
    assert critical[0]["priority_level"] == "P1"
    assert critical[0]["route_status"] == "ROUTED"

    route_logs_resp = outcomes_client.get(f"/api/alert/alerts/{alert_id}/routes", headers=_auth_header(token))
    assert route_logs_resp.status_code == 200
    route_logs = route_logs_resp.json()
    assert len(route_logs) >= 1
    assert any(item["target"] == "duty-ops-team" for item in route_logs)
    assert any(item["channel"] == "EMAIL" and item["delivery_status"] == "SKIPPED" for item in route_logs)

    verify_action_resp = outcomes_client.post(
        f"/api/alert/alerts/{alert_id}/actions",
        json={"action_type": "VERIFY", "note": "verified by duty", "detail": {"result": "ok"}},
        headers=_auth_header(token),
    )
    assert verify_action_resp.status_code == 200

    actions_resp = outcomes_client.get(f"/api/alert/alerts/{alert_id}/actions", headers=_auth_header(token))
    assert actions_resp.status_code == 200
    action_types = {item["action_type"] for item in actions_resp.json()}
    assert "DISPATCH" in action_types
    assert "VERIFY" in action_types

    review_resp = outcomes_client.get(f"/api/alert/alerts/{alert_id}/review", headers=_auth_header(token))
    assert review_resp.status_code == 200
    review = review_resp.json()
    assert review["alert"]["id"] == alert_id
    assert len(review["routes"]) >= 1
    assert len(review["actions"]) >= 2

    ingest_warning = outcomes_client.post(
        "/api/telemetry/ingest",
        json={
            "tenant_id": "spoofed",
            "drone_id": "phase13-drone-2",
            "position": {"lat": 30.12, "lon": 114.45, "alt_m": 120.0},
            "battery": {"percent": 12.0},
            "link": {"latency_ms": 50},
            "mode": "AUTO",
            "health": {"low_battery": True},
        },
        headers=_auth_header(token),
    )
    assert ingest_warning.status_code == 200

    list_again = outcomes_client.get("/api/alert/alerts", headers=_auth_header(token))
    assert list_again.status_code == 200
    warning = [item for item in list_again.json() if item["alert_type"] == "LOW_BATTERY"]
    assert len(warning) == 1
    assert warning[0]["priority_level"] == "P3"
    warning_routes = outcomes_client.get(
        f"/api/alert/alerts/{warning[0]['id']}/routes",
        headers=_auth_header(token),
    )
    assert warning_routes.status_code == 200
    assert any(item["target"] == "duty-default" for item in warning_routes.json())
