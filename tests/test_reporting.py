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
def reporting_client(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> Generator[TestClient, None, None]:
    db_path = tmp_path / "reporting_test.db"
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


def _create_mission(client: TestClient, token: str, name: str) -> str:
    response = client.post(
        "/api/mission/missions",
        json={
            "name": name,
            "type": "POINT_TASK",
            "payload": {},
            "constraints": {},
        },
        headers=_auth_header(token),
    )
    assert response.status_code == 201
    return response.json()["id"]


def test_reporting_overview_is_tenant_scoped(reporting_client: TestClient) -> None:
    tenant_a = _create_tenant(reporting_client, "reporting-scope-a")
    tenant_b = _create_tenant(reporting_client, "reporting-scope-b")
    _bootstrap_admin(reporting_client, tenant_a, "admin_a", "pass-a")
    _bootstrap_admin(reporting_client, tenant_b, "admin_b", "pass-b")
    token_a = _login(reporting_client, tenant_a, "admin_a", "pass-a")
    token_b = _login(reporting_client, tenant_b, "admin_b", "pass-b")

    _create_mission(reporting_client, token_a, "mission-a-1")
    _create_mission(reporting_client, token_a, "mission-a-2")
    _create_mission(reporting_client, token_b, "mission-b-1")

    overview_a = reporting_client.get("/api/reporting/overview", headers=_auth_header(token_a))
    overview_b = reporting_client.get("/api/reporting/overview", headers=_auth_header(token_b))

    assert overview_a.status_code == 200
    assert overview_b.status_code == 200

    body_a = overview_a.json()
    body_b = overview_b.json()
    assert body_a["missions_total"] == 2
    assert body_b["missions_total"] == 1
    assert body_a["inspections_total"] == 0
    assert body_b["inspections_total"] == 0
    assert body_a["defects_total"] == 0
    assert body_b["defects_total"] == 0
