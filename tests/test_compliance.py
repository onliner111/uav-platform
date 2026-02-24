from __future__ import annotations

from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, SQLModel, create_engine, select

from app import main as app_main
from app.domain.models import ApprovalRecord, User
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


def _get_user_id(tenant_id: str, username: str) -> str:
    with Session(db.engine) as session:
        user = session.exec(
            select(User).where(User.tenant_id == tenant_id).where(User.username == username)
        ).first()
    assert user is not None
    return user.id


def test_approval_list_is_tenant_scoped(compliance_client: TestClient) -> None:
    tenant_a = _create_tenant(compliance_client, "approval-scope-a")
    tenant_b = _create_tenant(compliance_client, "approval-scope-b")
    _bootstrap_admin(compliance_client, tenant_a, "admin_a", "pass-a")
    _bootstrap_admin(compliance_client, tenant_b, "admin_b", "pass-b")
    token_a = _login(compliance_client, tenant_a, "admin_a", "pass-a")
    token_b = _login(compliance_client, tenant_b, "admin_b", "pass-b")

    create_a = compliance_client.post(
        "/api/approvals",
        json={"entity_type": "mission", "entity_id": "m-a", "status": "APPROVED"},
        headers=_auth_header(token_a),
    )
    create_b = compliance_client.post(
        "/api/approvals",
        json={"entity_type": "mission", "entity_id": "m-b", "status": "APPROVED"},
        headers=_auth_header(token_b),
    )

    assert create_a.status_code == 200
    assert create_b.status_code == 200

    list_a = compliance_client.get("/api/approvals", headers=_auth_header(token_a))
    list_b = compliance_client.get("/api/approvals", headers=_auth_header(token_b))

    assert list_a.status_code == 200
    assert list_b.status_code == 200
    assert [item["entity_id"] for item in list_a.json()] == ["m-a"]
    assert [item["entity_id"] for item in list_b.json()] == ["m-b"]


def test_approval_records_composite_fk_enforced_in_db(compliance_client: TestClient) -> None:
    tenant_a = _create_tenant(compliance_client, "approval-fk-a")
    tenant_b = _create_tenant(compliance_client, "approval-fk-b")
    _bootstrap_admin(compliance_client, tenant_a, "admin_a", "pass-a")
    _bootstrap_admin(compliance_client, tenant_b, "admin_b", "pass-b")

    admin_a_id = _get_user_id(tenant_a, "admin_a")
    admin_b_id = _get_user_id(tenant_b, "admin_b")

    with Session(db.engine, expire_on_commit=False) as session:
        session.add(
            ApprovalRecord(
                tenant_id=tenant_a,
                entity_type="mission",
                entity_id="cross-tenant",
                status="APPROVED",
                approved_by=admin_b_id,
            )
        )
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()

        session.add(
            ApprovalRecord(
                tenant_id=tenant_a,
                entity_type="mission",
                entity_id="same-tenant",
                status="APPROVED",
                approved_by=admin_a_id,
            )
        )
        session.commit()
