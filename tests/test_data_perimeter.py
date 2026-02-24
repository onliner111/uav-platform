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
def perimeter_client(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> Generator[TestClient, None, None]:
    db_path = tmp_path / "perimeter_test.db"
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
        json={"name": f"{username}-role", "description": "perimeter test role"},
        headers=_auth_header(admin_token),
    )
    assert role_resp.status_code == 201
    role_id = role_resp.json()["id"]

    for permission_name in permission_names:
        permission_id = _get_permission_id(client, admin_token, permission_name)
        bind_perm_resp = client.post(
            f"/api/identity/roles/{role_id}/permissions/{permission_id}",
            headers=_auth_header(admin_token),
        )
        assert bind_perm_resp.status_code == 204

    user_resp = client.post(
        "/api/identity/users",
        json={"username": username, "password": password, "is_active": True},
        headers=_auth_header(admin_token),
    )
    assert user_resp.status_code == 201
    user_id = user_resp.json()["id"]

    bind_role_resp = client.post(
        f"/api/identity/users/{user_id}/roles/{role_id}",
        headers=_auth_header(admin_token),
    )
    assert bind_role_resp.status_code == 204
    return user_id


def test_data_perimeter_filters_core_domains(perimeter_client: TestClient) -> None:
    tenant_id = _create_tenant(perimeter_client, "perimeter-tenant")
    _bootstrap_admin(perimeter_client, tenant_id, "admin", "admin-pass")
    admin_token = _login(perimeter_client, tenant_id, "admin", "admin-pass")

    org_a_resp = perimeter_client.post(
        "/api/identity/org-units",
        json={"name": "Org-A", "code": "ORG-A"},
        headers=_auth_header(admin_token),
    )
    assert org_a_resp.status_code == 201
    org_a = org_a_resp.json()["id"]

    org_b_resp = perimeter_client.post(
        "/api/identity/org-units",
        json={"name": "Org-B", "code": "ORG-B"},
        headers=_auth_header(admin_token),
    )
    assert org_b_resp.status_code == 201
    org_b = org_b_resp.json()["id"]

    mission_a_resp = perimeter_client.post(
        "/api/mission/missions",
        json={
            "name": "mission-a",
            "org_unit_id": org_a,
            "project_code": "PROJ-A",
            "area_code": "AREA-A",
            "type": "POINT_TASK",
            "payload": {},
            "constraints": {},
        },
        headers=_auth_header(admin_token),
    )
    assert mission_a_resp.status_code == 201
    mission_a = mission_a_resp.json()["id"]

    mission_b_resp = perimeter_client.post(
        "/api/mission/missions",
        json={
            "name": "mission-b",
            "org_unit_id": org_b,
            "project_code": "PROJ-B",
            "area_code": "AREA-B",
            "type": "POINT_TASK",
            "payload": {},
            "constraints": {},
        },
        headers=_auth_header(admin_token),
    )
    assert mission_b_resp.status_code == 201
    mission_b = mission_b_resp.json()["id"]

    template_resp = perimeter_client.post(
        "/api/inspection/templates",
        json={
            "name": "tpl-perimeter",
            "category": "perimeter",
            "description": "perimeter template",
            "is_active": True,
        },
        headers=_auth_header(admin_token),
    )
    assert template_resp.status_code == 201
    template_id = template_resp.json()["id"]

    task_a_resp = perimeter_client.post(
        "/api/inspection/tasks",
        json={
            "name": "task-a",
            "template_id": template_id,
            "mission_id": mission_a,
            "org_unit_id": org_a,
            "project_code": "PROJ-A",
            "area_code": "AREA-A",
            "area_geom": "",
            "priority": 3,
        },
        headers=_auth_header(admin_token),
    )
    assert task_a_resp.status_code == 201
    task_a = task_a_resp.json()["id"]

    task_b_resp = perimeter_client.post(
        "/api/inspection/tasks",
        json={
            "name": "task-b",
            "template_id": template_id,
            "mission_id": mission_b,
            "org_unit_id": org_b,
            "project_code": "PROJ-B",
            "area_code": "AREA-B",
            "area_geom": "",
            "priority": 3,
        },
        headers=_auth_header(admin_token),
    )
    assert task_b_resp.status_code == 201
    task_b = task_b_resp.json()["id"]

    obs_a_resp = perimeter_client.post(
        f"/api/inspection/tasks/{task_a}/observations",
        json={
            "position_lat": 30.1,
            "position_lon": 114.1,
            "alt_m": 100.0,
            "item_code": "OBS-A",
            "severity": 2,
            "note": "obs-a",
        },
        headers=_auth_header(admin_token),
    )
    assert obs_a_resp.status_code == 201
    obs_a = obs_a_resp.json()["id"]

    obs_b_resp = perimeter_client.post(
        f"/api/inspection/tasks/{task_b}/observations",
        json={
            "position_lat": 30.2,
            "position_lon": 114.2,
            "alt_m": 120.0,
            "item_code": "OBS-B",
            "severity": 2,
            "note": "obs-b",
        },
        headers=_auth_header(admin_token),
    )
    assert obs_b_resp.status_code == 201
    obs_b = obs_b_resp.json()["id"]

    defect_a_resp = perimeter_client.post(
        f"/api/defects/from-observation/{obs_a}",
        headers=_auth_header(admin_token),
    )
    assert defect_a_resp.status_code == 201
    defect_a = defect_a_resp.json()["id"]

    defect_b_resp = perimeter_client.post(
        f"/api/defects/from-observation/{obs_b}",
        headers=_auth_header(admin_token),
    )
    assert defect_b_resp.status_code == 201
    defect_b = defect_b_resp.json()["id"]

    incident_a_resp = perimeter_client.post(
        "/api/incidents",
        json={
            "title": "incident-a",
            "level": "HIGH",
            "org_unit_id": org_a,
            "project_code": "PROJ-A",
            "area_code": "AREA-A",
            "location_geom": "POINT(0 0)",
        },
        headers=_auth_header(admin_token),
    )
    assert incident_a_resp.status_code == 201
    incident_a = incident_a_resp.json()["id"]

    incident_b_resp = perimeter_client.post(
        "/api/incidents",
        json={
            "title": "incident-b",
            "level": "HIGH",
            "org_unit_id": org_b,
            "project_code": "PROJ-B",
            "area_code": "AREA-B",
            "location_geom": "POINT(1 1)",
        },
        headers=_auth_header(admin_token),
    )
    assert incident_b_resp.status_code == 201

    scoped_user_id = _create_user_with_permissions(
        perimeter_client,
        admin_token,
        tenant_id,
        "scoped_reader",
        "reader-pass",
        ["mission.read", "inspection:read", "defect.read", "incident.read", "reporting.read"],
    )
    update_policy_resp = perimeter_client.put(
        f"/api/identity/users/{scoped_user_id}/data-policy",
        json={
            "scope_mode": "SCOPED",
            "org_unit_ids": [org_a],
            "project_codes": [],
            "area_codes": [],
            "task_ids": [],
        },
        headers=_auth_header(admin_token),
    )
    assert update_policy_resp.status_code == 200

    scoped_token = _login(perimeter_client, tenant_id, "scoped_reader", "reader-pass")

    missions_resp = perimeter_client.get("/api/mission/missions", headers=_auth_header(scoped_token))
    assert missions_resp.status_code == 200
    assert [item["id"] for item in missions_resp.json()] == [mission_a]

    task_list_resp = perimeter_client.get("/api/inspection/tasks", headers=_auth_header(scoped_token))
    assert task_list_resp.status_code == 200
    assert [item["id"] for item in task_list_resp.json()] == [task_a]

    defects_resp = perimeter_client.get("/api/defects", headers=_auth_header(scoped_token))
    assert defects_resp.status_code == 200
    assert [item["id"] for item in defects_resp.json()] == [defect_a]

    incidents_resp = perimeter_client.get("/api/incidents", headers=_auth_header(scoped_token))
    assert incidents_resp.status_code == 200
    assert [item["id"] for item in incidents_resp.json()] == [incident_a]

    overview_resp = perimeter_client.get("/api/reporting/overview", headers=_auth_header(scoped_token))
    assert overview_resp.status_code == 200
    overview = overview_resp.json()
    assert overview["missions_total"] == 1
    assert overview["inspections_total"] == 1
    assert overview["defects_total"] == 1

    cross_mission_resp = perimeter_client.get(
        f"/api/mission/missions/{mission_b}",
        headers=_auth_header(scoped_token),
    )
    assert cross_mission_resp.status_code == 404

    cross_task_resp = perimeter_client.get(
        f"/api/inspection/tasks/{task_b}",
        headers=_auth_header(scoped_token),
    )
    assert cross_task_resp.status_code == 404

    cross_defect_resp = perimeter_client.get(
        f"/api/defects/{defect_b}",
        headers=_auth_header(scoped_token),
    )
    assert cross_defect_resp.status_code == 404
