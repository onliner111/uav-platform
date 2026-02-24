from __future__ import annotations

from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, SQLModel, create_engine, select

from app import main as app_main
from app.domain.models import OrgUnit, User, UserOrgMembership
from app.infra import audit, db, events


@pytest.fixture()
def identity_org_client(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> Generator[TestClient, None, None]:
    db_path = tmp_path / "identity_org_test.db"
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


def _get_user_id(tenant_id: str, username: str) -> str:
    with Session(db.engine) as session:
        user = session.exec(
            select(User).where(User.tenant_id == tenant_id).where(User.username == username)
        ).first()
    assert user is not None
    return user.id


def test_org_units_parent_composite_fk_enforced(identity_org_client: TestClient) -> None:
    tenant_a = _create_tenant(identity_org_client, "org-parent-a")
    tenant_b = _create_tenant(identity_org_client, "org-parent-b")

    with Session(db.engine, expire_on_commit=False) as session:
        root_a = OrgUnit(
            tenant_id=tenant_a,
            name="Root A",
            code="A-ROOT",
            parent_id=None,
            level=0,
            path="/A-ROOT",
        )
        root_b = OrgUnit(
            tenant_id=tenant_b,
            name="Root B",
            code="B-ROOT",
            parent_id=None,
            level=0,
            path="/B-ROOT",
        )
        session.add(root_a)
        session.add(root_b)
        session.commit()
        session.refresh(root_a)
        session.refresh(root_b)

        session.add(
            OrgUnit(
                tenant_id=tenant_a,
                name="Cross Tenant Child",
                code="A-CHILD-X",
                parent_id=root_b.id,
                level=1,
                path="/A-ROOT/A-CHILD-X",
            )
        )
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()

        session.add(
            OrgUnit(
                tenant_id=tenant_a,
                name="Tenant A Child",
                code="A-CHILD-1",
                parent_id=root_a.id,
                level=1,
                path="/A-ROOT/A-CHILD-1",
            )
        )
        session.commit()


def test_user_org_memberships_composite_fk_enforced(identity_org_client: TestClient) -> None:
    tenant_a = _create_tenant(identity_org_client, "org-membership-a")
    tenant_b = _create_tenant(identity_org_client, "org-membership-b")
    _bootstrap_admin(identity_org_client, tenant_a, "admin_a", "pass-a")
    _bootstrap_admin(identity_org_client, tenant_b, "admin_b", "pass-b")

    admin_a_id = _get_user_id(tenant_a, "admin_a")
    admin_b_id = _get_user_id(tenant_b, "admin_b")

    with Session(db.engine, expire_on_commit=False) as session:
        org_a = OrgUnit(
            tenant_id=tenant_a,
            name="Tenant A Root",
            code="A-MEM-ROOT",
            parent_id=None,
            level=0,
            path="/A-MEM-ROOT",
        )
        org_b = OrgUnit(
            tenant_id=tenant_b,
            name="Tenant B Root",
            code="B-MEM-ROOT",
            parent_id=None,
            level=0,
            path="/B-MEM-ROOT",
        )
        session.add(org_a)
        session.add(org_b)
        session.commit()
        session.refresh(org_a)
        session.refresh(org_b)

        session.add(
            UserOrgMembership(
                tenant_id=tenant_a,
                user_id=admin_a_id,
                org_unit_id=org_b.id,
                is_primary=True,
            )
        )
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()

        session.add(
            UserOrgMembership(
                tenant_id=tenant_a,
                user_id=admin_b_id,
                org_unit_id=org_a.id,
                is_primary=False,
            )
        )
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()

        session.add(
            UserOrgMembership(
                tenant_id=tenant_a,
                user_id=admin_a_id,
                org_unit_id=org_a.id,
                is_primary=True,
            )
        )
        session.commit()

