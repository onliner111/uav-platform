from __future__ import annotations

from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, SQLModel, create_engine

from app import main as app_main
from app.domain.models import InspectionTask, InspectionTaskStatus
from app.infra import audit, db, events


@pytest.fixture()
def inspection_client(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> Generator[TestClient, None, None]:
    db_path = tmp_path / "inspection_test.db"
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


def _create_template(client: TestClient, token: str, name: str) -> str:
    response = client.post(
        "/api/inspection/templates",
        json={
            "name": name,
            "category": "safety",
            "description": "template for fk check",
            "is_active": True,
        },
        headers=_auth_header(token),
    )
    assert response.status_code == 201
    return response.json()["id"]


def test_inspection_task_template_composite_fk_enforced_in_db(inspection_client: TestClient) -> None:
    tenant_a = _create_tenant(inspection_client, "inspection-fk-a")
    tenant_b = _create_tenant(inspection_client, "inspection-fk-b")
    _bootstrap_admin(inspection_client, tenant_a, "admin_a", "pass-a")
    _bootstrap_admin(inspection_client, tenant_b, "admin_b", "pass-b")

    token_a = _login(inspection_client, tenant_a, "admin_a", "pass-a")
    token_b = _login(inspection_client, tenant_b, "admin_b", "pass-b")

    template_a_id = _create_template(inspection_client, token_a, "template-a")
    template_b_id = _create_template(inspection_client, token_b, "template-b")

    with Session(db.engine, expire_on_commit=False) as session:
        session.add(
            InspectionTask(
                tenant_id=tenant_a,
                name="cross-tenant-template-task",
                template_id=template_b_id,
                mission_id=None,
                area_geom="",
                priority=5,
                status=InspectionTaskStatus.DRAFT,
            )
        )
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()

        session.add(
            InspectionTask(
                tenant_id=tenant_a,
                name="same-tenant-template-task",
                template_id=template_a_id,
                mission_id=None,
                area_geom="",
                priority=5,
                status=InspectionTaskStatus.DRAFT,
            )
        )
        session.commit()
