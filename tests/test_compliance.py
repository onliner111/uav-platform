from __future__ import annotations

from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlmodel import Session, SQLModel, create_engine, select

from app import main as app_main
from app.domain.models import CommandRequestRecord
from app.infra import audit, db, events


@pytest.fixture()
def compliance_client(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> Generator[TestClient, None, None]:
    db_path = tmp_path / "compliance_test.db"
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


def _create_mission(client: TestClient, token: str, name: str, *, emergency_fastlane: bool = False) -> str:
    response = client.post(
        "/api/mission/missions",
        json={
            "name": name,
            "type": "POINT_TASK",
            "payload": {"point": {"lat": 30.1, "lon": 114.2, "alt_m": 120}},
            "constraints": {"emergency_fastlane": emergency_fastlane} if emergency_fastlane else {},
        },
        headers=_auth_header(token),
    )
    assert response.status_code == 201
    return response.json()["id"]


def _approve_mission(client: TestClient, token: str, mission_id: str) -> None:
    response = client.post(
        f"/api/mission/missions/{mission_id}/approve",
        json={"decision": "APPROVE", "comment": "compliance test approve"},
        headers=_auth_header(token),
    )
    assert response.status_code == 200
    assert response.json()["state"] == "APPROVED"


def _create_drone(client: TestClient, token: str, name: str) -> str:
    response = client.post(
        "/api/registry/drones",
        json={"name": name, "vendor": "FAKE", "capabilities": {"rth": True}},
        headers=_auth_header(token),
    )
    assert response.status_code == 201
    return response.json()["id"]


def _create_no_fly_zone(client: TestClient, token: str, name: str) -> str:
    response = client.post(
        "/api/compliance/zones",
        json={
            "name": name,
            "zone_type": "NO_FLY",
            "geom_wkt": "POLYGON((114.19 30.09,114.21 30.09,114.21 30.11,114.19 30.11,114.19 30.09))",
            "detail": {"source": "test"},
        },
        headers=_auth_header(token),
    )
    assert response.status_code == 201
    return response.json()["id"]


def test_mission_plan_rejected_when_entering_no_fly_zone(compliance_client: TestClient) -> None:
    tenant_id = _create_tenant(compliance_client, "phase12-zone-mission")
    _bootstrap_admin(compliance_client, tenant_id, "admin", "admin-pass")
    token = _login(compliance_client, tenant_id, "admin", "admin-pass")
    _ = _create_no_fly_zone(compliance_client, token, "phase12-no-fly")

    create_resp = compliance_client.post(
        "/api/mission/missions",
        json={
            "name": "blocked-mission",
            "type": "POINT_TASK",
            "payload": {"point": {"lat": 30.1, "lon": 114.2, "alt_m": 100}},
            "constraints": {},
        },
        headers=_auth_header(token),
    )
    assert create_resp.status_code == 409
    assert create_resp.json()["detail"]["reason_code"] == "AIRSPACE_NO_FLY"


def test_preflight_checklist_is_required_before_mission_running(compliance_client: TestClient) -> None:
    tenant_id = _create_tenant(compliance_client, "phase12-preflight")
    _bootstrap_admin(compliance_client, tenant_id, "admin", "admin-pass")
    token = _login(compliance_client, tenant_id, "admin", "admin-pass")
    mission_id = _create_mission(compliance_client, token, "preflight-mission")
    _approve_mission(compliance_client, token, mission_id)

    run_resp = compliance_client.post(
        f"/api/mission/missions/{mission_id}/transition",
        json={"target_state": "RUNNING"},
        headers=_auth_header(token),
    )
    assert run_resp.status_code == 409
    assert run_resp.json()["detail"]["reason_code"] == "PREFLIGHT_CHECKLIST_REQUIRED"

    init_resp = compliance_client.post(
        f"/api/compliance/missions/{mission_id}/preflight/init",
        json={
            "required_items": [
                {"code": "CHK-A", "title": "airframe check"},
                {"code": "CHK-B", "title": "battery check"},
            ]
        },
        headers=_auth_header(token),
    )
    assert init_resp.status_code == 200
    assert init_resp.json()["status"] == "PENDING"

    check_a_resp = compliance_client.post(
        f"/api/compliance/missions/{mission_id}/preflight/check-item",
        json={"item_code": "CHK-A", "checked": True, "note": "done"},
        headers=_auth_header(token),
    )
    assert check_a_resp.status_code == 200
    assert check_a_resp.json()["status"] == "IN_PROGRESS"

    run_incomplete_resp = compliance_client.post(
        f"/api/mission/missions/{mission_id}/transition",
        json={"target_state": "RUNNING"},
        headers=_auth_header(token),
    )
    assert run_incomplete_resp.status_code == 409
    assert run_incomplete_resp.json()["detail"]["reason_code"] == "PREFLIGHT_CHECKLIST_INCOMPLETE"

    check_b_resp = compliance_client.post(
        f"/api/compliance/missions/{mission_id}/preflight/check-item",
        json={"item_code": "CHK-B", "checked": True},
        headers=_auth_header(token),
    )
    assert check_b_resp.status_code == 200
    assert check_b_resp.json()["status"] == "COMPLETED"

    run_ok_resp = compliance_client.post(
        f"/api/mission/missions/{mission_id}/transition",
        json={"target_state": "RUNNING"},
        headers=_auth_header(token),
    )
    assert run_ok_resp.status_code == 200
    assert run_ok_resp.json()["state"] == "RUNNING"


def test_fastlane_mission_can_run_without_preflight_checklist(compliance_client: TestClient) -> None:
    tenant_id = _create_tenant(compliance_client, "phase12-fastlane")
    _bootstrap_admin(compliance_client, tenant_id, "admin", "admin-pass")
    token = _login(compliance_client, tenant_id, "admin", "admin-pass")
    mission_id = _create_mission(compliance_client, token, "fastlane-mission", emergency_fastlane=True)
    _approve_mission(compliance_client, token, mission_id)

    run_resp = compliance_client.post(
        f"/api/mission/missions/{mission_id}/transition",
        json={"target_state": "RUNNING"},
        headers=_auth_header(token),
    )
    assert run_resp.status_code == 200
    assert run_resp.json()["state"] == "RUNNING"


def test_command_blocked_by_geofence_has_reason_and_idempotent_trace(compliance_client: TestClient) -> None:
    tenant_id = _create_tenant(compliance_client, "phase12-command-geofence")
    _bootstrap_admin(compliance_client, tenant_id, "admin", "admin-pass")
    token = _login(compliance_client, tenant_id, "admin", "admin-pass")
    drone_id = _create_drone(compliance_client, token, "phase12-drone")
    _ = _create_no_fly_zone(compliance_client, token, "phase12-command-no-fly")

    payload = {
        "drone_id": drone_id,
        "type": "GOTO",
        "params": {"lat": 30.1, "lon": 114.2, "alt_m": 80},
        "idempotency_key": "phase12-goto-blocked",
        "expect_ack": True,
    }
    first_resp = compliance_client.post("/api/command/commands", json=payload, headers=_auth_header(token))
    second_resp = compliance_client.post("/api/command/commands", json=payload, headers=_auth_header(token))

    assert first_resp.status_code == 409
    assert second_resp.status_code == 409
    assert first_resp.json()["detail"]["reason_code"] == "COMMAND_GEOFENCE_BLOCKED"
    assert second_resp.json()["detail"]["reason_code"] == "COMMAND_GEOFENCE_BLOCKED"

    command_id = first_resp.json()["detail"]["detail"]["command_id"]
    get_resp = compliance_client.get(
        f"/api/command/commands/{command_id}",
        headers=_auth_header(token),
    )
    assert get_resp.status_code == 200
    assert get_resp.json()["compliance_passed"] is False
    assert get_resp.json()["compliance_reason_code"] == "COMMAND_GEOFENCE_BLOCKED"
    assert get_resp.json()["status"] == "FAILED"

    with Session(db.engine) as session:
        rows = list(
            session.exec(
                select(CommandRequestRecord)
                .where(CommandRequestRecord.tenant_id == tenant_id)
                .where(CommandRequestRecord.idempotency_key == "phase12-goto-blocked")
            ).all()
        )
    assert len(rows) == 1


def test_start_mission_command_requires_approval_and_preflight(compliance_client: TestClient) -> None:
    tenant_id = _create_tenant(compliance_client, "phase12-command-start")
    _bootstrap_admin(compliance_client, tenant_id, "admin", "admin-pass")
    token = _login(compliance_client, tenant_id, "admin", "admin-pass")
    drone_id = _create_drone(compliance_client, token, "phase12-start-drone")
    mission_id = _create_mission(compliance_client, token, "phase12-start-mission")

    draft_resp = compliance_client.post(
        "/api/command/commands",
        json={
            "drone_id": drone_id,
            "type": "START_MISSION",
            "params": {"mission_id": mission_id},
            "idempotency_key": "phase12-start-draft",
            "expect_ack": True,
        },
        headers=_auth_header(token),
    )
    assert draft_resp.status_code == 409
    assert draft_resp.json()["detail"]["reason_code"] == "PREFLIGHT_CHECKLIST_INCOMPLETE"

    _approve_mission(compliance_client, token, mission_id)

    no_preflight_resp = compliance_client.post(
        "/api/command/commands",
        json={
            "drone_id": drone_id,
            "type": "START_MISSION",
            "params": {"mission_id": mission_id},
            "idempotency_key": "phase12-start-no-preflight",
            "expect_ack": True,
        },
        headers=_auth_header(token),
    )
    assert no_preflight_resp.status_code == 409
    assert no_preflight_resp.json()["detail"]["reason_code"] == "PREFLIGHT_CHECKLIST_REQUIRED"

    init_resp = compliance_client.post(
        f"/api/compliance/missions/{mission_id}/preflight/init",
        json={"required_items": [{"code": "CHK-START", "title": "before start"}]},
        headers=_auth_header(token),
    )
    assert init_resp.status_code == 200

    check_resp = compliance_client.post(
        f"/api/compliance/missions/{mission_id}/preflight/check-item",
        json={"item_code": "CHK-START", "checked": True},
        headers=_auth_header(token),
    )
    assert check_resp.status_code == 200
    assert check_resp.json()["status"] == "COMPLETED"

    ok_resp = compliance_client.post(
        "/api/command/commands",
        json={
            "drone_id": drone_id,
            "type": "START_MISSION",
            "params": {"mission_id": mission_id},
            "idempotency_key": "phase12-start-ok",
            "expect_ack": True,
        },
        headers=_auth_header(token),
    )
    assert ok_resp.status_code == 201
    assert ok_resp.json()["status"] == "ACKED"
    assert ok_resp.json()["compliance_passed"] is True
