from __future__ import annotations

from collections.abc import Generator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, SQLModel, create_engine, select

from app import main as app_main
from app.domain.models import EventRecord, Mission, MissionPlanType, MissionRun, MissionState
from app.infra import audit, db, events


@pytest.fixture()
def mission_client(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> Generator[TestClient, None, None]:
    db_path = tmp_path / "mission_test.db"
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


def _get_permission_id(client: TestClient, token: str, name: str) -> str:
    response = client.get("/api/identity/permissions", headers=_auth_header(token))
    assert response.status_code == 200
    matches = [item for item in response.json() if item["name"] == name]
    assert matches, f"permission not found: {name}"
    return matches[0]["id"]


def _create_user_with_permissions(
    client: TestClient,
    admin_token: str,
    tenant_id: str,
    username: str,
    password: str,
    permission_names: list[str],
) -> str:
    role_resp = client.post(
        "/api/identity/roles",
        json={"name": f"{username}-role", "description": "mission test role"},
        headers=_auth_header(admin_token),
    )
    assert role_resp.status_code == 201
    role_id = role_resp.json()["id"]

    for permission_name in permission_names:
        permission_id = _get_permission_id(client, admin_token, permission_name)
        bind_perm = client.post(
            f"/api/identity/roles/{role_id}/permissions/{permission_id}",
            headers=_auth_header(admin_token),
        )
        assert bind_perm.status_code == 204

    user_resp = client.post(
        "/api/identity/users",
        json={"username": username, "password": password, "is_active": True},
        headers=_auth_header(admin_token),
    )
    assert user_resp.status_code == 201
    user_id = user_resp.json()["id"]

    bind_role = client.post(
        f"/api/identity/users/{user_id}/roles/{role_id}",
        headers=_auth_header(admin_token),
    )
    assert bind_role.status_code == 204
    return _login(client, tenant_id, username, password)


def _create_basic_mission(client: TestClient, token: str) -> str:
    response = client.post(
        "/api/mission/missions",
        json={
            "name": "inspection-1",
            "type": "ROUTE_WAYPOINTS",
            "payload": {"waypoints": [{"lat": 30.1, "lon": 114.2, "alt_m": 120}]},
            "constraints": {"max_alt": 150},
        },
        headers=_auth_header(token),
    )
    assert response.status_code == 201
    return response.json()["id"]


def test_mission_invalid_transition_returns_409(mission_client: TestClient) -> None:
    tenant_id = _create_tenant(mission_client, "mission-tenant")
    _bootstrap_admin(mission_client, tenant_id, "admin", "admin-pass")
    admin_token = _login(mission_client, tenant_id, "admin", "admin-pass")
    mission_id = _create_basic_mission(mission_client, admin_token)

    transition_resp = mission_client.post(
        f"/api/mission/missions/{mission_id}/transition",
        json={"target_state": "COMPLETED"},
        headers=_auth_header(admin_token),
    )
    assert transition_resp.status_code == 409


def test_mission_permission_denied(mission_client: TestClient) -> None:
    tenant_id = _create_tenant(mission_client, "mission-perm-tenant")
    _bootstrap_admin(mission_client, tenant_id, "admin", "admin-pass")
    admin_token = _login(mission_client, tenant_id, "admin", "admin-pass")

    reader_token = _create_user_with_permissions(
        mission_client,
        admin_token,
        tenant_id,
        "reader",
        "reader-pass",
        ["mission.read"],
    )

    create_resp = mission_client.post(
        "/api/mission/missions",
        json={
            "name": "should-fail",
            "type": "POINT_TASK",
            "payload": {"point": {"lat": 30.1, "lon": 114.2}},
            "constraints": {},
        },
        headers=_auth_header(reader_token),
    )
    assert create_resp.status_code == 403


def test_mission_fastlane_requires_authorization(mission_client: TestClient) -> None:
    tenant_id = _create_tenant(mission_client, "mission-fastlane-tenant")
    _bootstrap_admin(mission_client, tenant_id, "admin", "admin-pass")
    admin_token = _login(mission_client, tenant_id, "admin", "admin-pass")

    operator_token = _create_user_with_permissions(
        mission_client,
        admin_token,
        tenant_id,
        "operator",
        "operator-pass",
        ["mission.write"],
    )

    create_resp = mission_client.post(
        "/api/mission/missions",
        json={
            "name": "fastlane-mission",
            "type": "POINT_TASK",
            "payload": {"point": {"lat": 30.1, "lon": 114.2}},
            "constraints": {"emergency_fastlane": True},
        },
        headers=_auth_header(operator_token),
    )
    assert create_resp.status_code == 403


def test_mission_emits_events_on_create_and_approve(mission_client: TestClient) -> None:
    tenant_id = _create_tenant(mission_client, "mission-events-tenant")
    _bootstrap_admin(mission_client, tenant_id, "admin", "admin-pass")
    admin_token = _login(mission_client, tenant_id, "admin", "admin-pass")
    mission_id = _create_basic_mission(mission_client, admin_token)

    approve_resp = mission_client.post(
        f"/api/mission/missions/{mission_id}/approve",
        json={"decision": "APPROVE", "comment": "looks good"},
        headers=_auth_header(admin_token),
    )
    assert approve_resp.status_code == 200
    assert approve_resp.json()["state"] == "APPROVED"

    with Session(db.engine) as session:
        rows = list(session.exec(select(EventRecord).where(EventRecord.tenant_id == tenant_id)).all())

    filtered_rows = [row for row in rows if row.payload.get("mission_id") == mission_id]
    event_types = {row.event_type for row in filtered_rows}
    assert "mission.created" in event_types
    assert "mission.approved" in event_types


def test_mission_tenant_isolation_by_id_endpoints(mission_client: TestClient) -> None:
    tenant_a = _create_tenant(mission_client, "mission-tenant-a")
    tenant_b = _create_tenant(mission_client, "mission-tenant-b")
    _bootstrap_admin(mission_client, tenant_a, "admin_a", "pass-a")
    _bootstrap_admin(mission_client, tenant_b, "admin_b", "pass-b")

    token_a = _login(mission_client, tenant_a, "admin_a", "pass-a")
    token_b = _login(mission_client, tenant_b, "admin_b", "pass-b")

    mission_id = _create_basic_mission(mission_client, token_a)

    cross_get = mission_client.get(
        f"/api/mission/missions/{mission_id}",
        headers=_auth_header(token_b),
    )
    assert cross_get.status_code == 404

    cross_update = mission_client.patch(
        f"/api/mission/missions/{mission_id}",
        json={"name": "spoofed"},
        headers=_auth_header(token_b),
    )
    assert cross_update.status_code == 404

    cross_approve = mission_client.post(
        f"/api/mission/missions/{mission_id}/approve",
        json={"decision": "APPROVE"},
        headers=_auth_header(token_b),
    )
    assert cross_approve.status_code == 404

    cross_approvals = mission_client.get(
        f"/api/mission/missions/{mission_id}/approvals",
        headers=_auth_header(token_b),
    )
    assert cross_approvals.status_code == 404

    cross_transition = mission_client.post(
        f"/api/mission/missions/{mission_id}/transition",
        json={"target_state": "RUNNING"},
        headers=_auth_header(token_b),
    )
    assert cross_transition.status_code == 404

    cross_delete = mission_client.delete(
        f"/api/mission/missions/{mission_id}",
        headers=_auth_header(token_b),
    )
    assert cross_delete.status_code == 404


def test_mission_create_and_update_reject_cross_tenant_drone(mission_client: TestClient) -> None:
    tenant_a = _create_tenant(mission_client, "mission-drone-a")
    tenant_b = _create_tenant(mission_client, "mission-drone-b")
    _bootstrap_admin(mission_client, tenant_a, "admin_a", "pass-a")
    _bootstrap_admin(mission_client, tenant_b, "admin_b", "pass-b")

    token_a = _login(mission_client, tenant_a, "admin_a", "pass-a")
    token_b = _login(mission_client, tenant_b, "admin_b", "pass-b")

    create_drone_resp = mission_client.post(
        "/api/registry/drones",
        json={"name": "cross-tenant-drone", "vendor": "FAKE", "capabilities": {"camera": True}},
        headers=_auth_header(token_b),
    )
    assert create_drone_resp.status_code == 201
    cross_tenant_drone_id = create_drone_resp.json()["id"]

    create_mission_resp = mission_client.post(
        "/api/mission/missions",
        json={
            "name": "cross-tenant-drone-mission",
            "drone_id": cross_tenant_drone_id,
            "type": "POINT_TASK",
            "payload": {"point": {"lat": 30.1, "lon": 114.2}},
            "constraints": {},
        },
        headers=_auth_header(token_a),
    )
    assert create_mission_resp.status_code == 404

    mission_id = _create_basic_mission(mission_client, token_a)
    update_mission_resp = mission_client.patch(
        f"/api/mission/missions/{mission_id}",
        json={"drone_id": cross_tenant_drone_id},
        headers=_auth_header(token_a),
    )
    assert update_mission_resp.status_code == 404


def test_mission_composite_fk_enforced_in_db(mission_client: TestClient) -> None:
    tenant_a = _create_tenant(mission_client, "mission-fk-a")
    tenant_b = _create_tenant(mission_client, "mission-fk-b")
    _bootstrap_admin(mission_client, tenant_a, "admin_a", "pass-a")
    _bootstrap_admin(mission_client, tenant_b, "admin_b", "pass-b")

    token_a = _login(mission_client, tenant_a, "admin_a", "pass-a")
    token_b = _login(mission_client, tenant_b, "admin_b", "pass-b")

    drone_b_resp = mission_client.post(
        "/api/registry/drones",
        json={"name": "drone-b", "vendor": "FAKE", "capabilities": {}},
        headers=_auth_header(token_b),
    )
    assert drone_b_resp.status_code == 201
    drone_b_id = drone_b_resp.json()["id"]

    mission_b_id = _create_basic_mission(mission_client, token_b)
    mission_a_id = _create_basic_mission(mission_client, token_a)

    with Session(db.engine, expire_on_commit=False) as session:
        cross_mission = Mission(
            tenant_id=tenant_a,
            name="db-cross-drone",
            drone_id=drone_b_id,
            plan_type=MissionPlanType.POINT_TASK,
            payload={"point": {"lat": 30.2, "lon": 114.3}},
            constraints={},
            state=MissionState.DRAFT,
            created_by="db-test",
        )
        session.add(cross_mission)
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()

        cross_run = MissionRun(
            tenant_id=tenant_a,
            mission_id=mission_b_id,
            state=MissionState.RUNNING,
            started_at=datetime.now(UTC),
        )
        session.add(cross_run)
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()

        valid_run = MissionRun(
            tenant_id=tenant_a,
            mission_id=mission_a_id,
            state=MissionState.RUNNING,
            started_at=datetime.now(UTC),
        )
        session.add(valid_run)
        session.commit()

