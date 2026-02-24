from __future__ import annotations

from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, SQLModel, create_engine

from app import main as app_main
from app.domain.models import DefectAction
from app.infra import audit, db, events


@pytest.fixture()
def defect_client(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> Generator[TestClient, None, None]:
    db_path = tmp_path / "defect_test.db"
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


def _create_observation(client: TestClient, token: str, template_name: str) -> str:
    create_template_resp = client.post(
        "/api/inspection/templates",
        json={
            "name": template_name,
            "category": "defect-test",
            "description": "for defect fk test",
            "is_active": True,
        },
        headers=_auth_header(token),
    )
    assert create_template_resp.status_code == 201
    template_id = create_template_resp.json()["id"]

    create_task_resp = client.post(
        "/api/inspection/tasks",
        json={
            "name": f"task-{template_name}",
            "template_id": template_id,
            "mission_id": None,
            "area_geom": "",
            "priority": 5,
        },
        headers=_auth_header(token),
    )
    assert create_task_resp.status_code == 201
    task_id = create_task_resp.json()["id"]

    create_observation_resp = client.post(
        f"/api/inspection/tasks/{task_id}/observations",
        json={
            "drone_id": None,
            "position_lat": 30.1,
            "position_lon": 114.2,
            "alt_m": 120.0,
            "item_code": "CHK-1",
            "severity": 2,
            "note": "detected",
            "media_url": None,
            "confidence": 0.9,
        },
        headers=_auth_header(token),
    )
    assert create_observation_resp.status_code == 201
    return create_observation_resp.json()["id"]


def _create_defect_from_observation(client: TestClient, token: str, observation_id: str) -> str:
    response = client.post(
        f"/api/defects/from-observation/{observation_id}",
        headers=_auth_header(token),
    )
    assert response.status_code == 201
    return response.json()["id"]


def test_defect_actions_composite_fk_enforced_in_db(defect_client: TestClient) -> None:
    tenant_a = _create_tenant(defect_client, "defect-fk-a")
    tenant_b = _create_tenant(defect_client, "defect-fk-b")
    _bootstrap_admin(defect_client, tenant_a, "admin_a", "pass-a")
    _bootstrap_admin(defect_client, tenant_b, "admin_b", "pass-b")

    token_a = _login(defect_client, tenant_a, "admin_a", "pass-a")
    token_b = _login(defect_client, tenant_b, "admin_b", "pass-b")

    observation_a_id = _create_observation(defect_client, token_a, "template-a")
    observation_b_id = _create_observation(defect_client, token_b, "template-b")
    defect_a_id = _create_defect_from_observation(defect_client, token_a, observation_a_id)
    defect_b_id = _create_defect_from_observation(defect_client, token_b, observation_b_id)

    with Session(db.engine, expire_on_commit=False) as session:
        session.add(
            DefectAction(
                tenant_id=tenant_a,
                defect_id=defect_b_id,
                action_type="X_TENANT",
                note="cross tenant should fail",
            )
        )
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()

        session.add(
            DefectAction(
                tenant_id=tenant_a,
                defect_id=defect_a_id,
                action_type="IN_TENANT",
                note="same tenant should pass",
            )
        )
        session.commit()
