from __future__ import annotations

from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, SQLModel, create_engine, select

from app import main as app_main
from app.domain.models import AuditLog, UserRole
from app.infra import audit, db, events


@pytest.fixture()
def identity_client(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> Generator[TestClient, None, None]:
    db_path = tmp_path / "identity_test.db"
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


def _latest_audit(
    tenant_id: str,
    action: str,
    *,
    status_code: int | None = None,
) -> AuditLog:
    with Session(db.get_engine(), expire_on_commit=False) as session:
        statement = (
            select(AuditLog)
            .where(AuditLog.tenant_id == tenant_id)
            .where(AuditLog.action == action)
        )
        if status_code is not None:
            statement = statement.where(AuditLog.status_code == status_code)
        rows = list(session.exec(statement).all())
    assert rows
    return sorted(rows, key=lambda item: item.ts)[-1]


def test_identity_tenant_isolation(identity_client: TestClient) -> None:
    tenant_a = _create_tenant(identity_client, "tenant-a")
    tenant_b = _create_tenant(identity_client, "tenant-b")
    _bootstrap_admin(identity_client, tenant_a, "admin_a", "pass-a")
    _bootstrap_admin(identity_client, tenant_b, "admin_b", "pass-b")

    token_a = _login(identity_client, tenant_a, "admin_a", "pass-a")
    token_b = _login(identity_client, tenant_b, "admin_b", "pass-b")

    create_user_resp = identity_client.post(
        "/api/identity/users",
        json={"username": "alice", "password": "alice-pass", "is_active": True},
        headers=_auth_header(token_a),
    )
    assert create_user_resp.status_code == 201
    alice_id = create_user_resp.json()["id"]

    cross_tenant_resp = identity_client.get(
        f"/api/identity/users/{alice_id}",
        headers=_auth_header(token_b),
    )
    assert cross_tenant_resp.status_code == 404


def test_identity_permission_denied(identity_client: TestClient) -> None:
    tenant_id = _create_tenant(identity_client, "tenant-perm")
    _bootstrap_admin(identity_client, tenant_id, "admin", "admin-pass")
    admin_token = _login(identity_client, tenant_id, "admin", "admin-pass")

    role_resp = identity_client.post(
        "/api/identity/roles",
        json={"name": "viewer", "description": "no permissions"},
        headers=_auth_header(admin_token),
    )
    assert role_resp.status_code == 201
    role_id = role_resp.json()["id"]

    bob_resp = identity_client.post(
        "/api/identity/users",
        json={"username": "bob", "password": "bob-pass", "is_active": True},
        headers=_auth_header(admin_token),
    )
    assert bob_resp.status_code == 201
    bob_id = bob_resp.json()["id"]

    bind_resp = identity_client.post(
        f"/api/identity/users/{bob_id}/roles/{role_id}",
        headers=_auth_header(admin_token),
    )
    assert bind_resp.status_code == 204

    bob_token = _login(identity_client, tenant_id, "bob", "bob-pass")
    forbidden_resp = identity_client.get("/api/identity/users", headers=_auth_header(bob_token))
    assert forbidden_resp.status_code == 403


def test_identity_cross_tenant_bind_unbind_returns_404(identity_client: TestClient) -> None:
    tenant_a = _create_tenant(identity_client, "tenant-404-a")
    tenant_b = _create_tenant(identity_client, "tenant-404-b")
    _bootstrap_admin(identity_client, tenant_a, "admin_a", "pass-a")
    _bootstrap_admin(identity_client, tenant_b, "admin_b", "pass-b")

    token_a = _login(identity_client, tenant_a, "admin_a", "pass-a")
    token_b = _login(identity_client, tenant_b, "admin_b", "pass-b")

    user_a_resp = identity_client.post(
        "/api/identity/users",
        json={"username": "alice_a", "password": "alice-pass", "is_active": True},
        headers=_auth_header(token_a),
    )
    assert user_a_resp.status_code == 201
    user_a_id = user_a_resp.json()["id"]

    role_a_resp = identity_client.post(
        "/api/identity/roles",
        json={"name": "viewer_a", "description": "tenant-a role"},
        headers=_auth_header(token_a),
    )
    assert role_a_resp.status_code == 201
    role_a_id = role_a_resp.json()["id"]

    role_b_resp = identity_client.post(
        "/api/identity/roles",
        json={"name": "viewer_b", "description": "tenant-b role"},
        headers=_auth_header(token_b),
    )
    assert role_b_resp.status_code == 201
    role_b_id = role_b_resp.json()["id"]

    cross_bind_resp = identity_client.post(
        f"/api/identity/users/{user_a_id}/roles/{role_b_id}",
        headers=_auth_header(token_a),
    )
    assert cross_bind_resp.status_code == 404

    bind_resp = identity_client.post(
        f"/api/identity/users/{user_a_id}/roles/{role_a_id}",
        headers=_auth_header(token_a),
    )
    assert bind_resp.status_code == 204

    cross_unbind_resp = identity_client.delete(
        f"/api/identity/users/{user_a_id}/roles/{role_a_id}",
        headers=_auth_header(token_b),
    )
    assert cross_unbind_resp.status_code == 404


def test_identity_user_roles_composite_fk_enforced(identity_client: TestClient) -> None:
    tenant_a = _create_tenant(identity_client, "tenant-fk-a")
    tenant_b = _create_tenant(identity_client, "tenant-fk-b")
    _bootstrap_admin(identity_client, tenant_a, "admin_fk_a", "pass-a")
    _bootstrap_admin(identity_client, tenant_b, "admin_fk_b", "pass-b")

    token_a = _login(identity_client, tenant_a, "admin_fk_a", "pass-a")
    token_b = _login(identity_client, tenant_b, "admin_fk_b", "pass-b")

    user_a_resp = identity_client.post(
        "/api/identity/users",
        json={"username": "charlie_a", "password": "charlie-pass", "is_active": True},
        headers=_auth_header(token_a),
    )
    assert user_a_resp.status_code == 201
    user_a_id = user_a_resp.json()["id"]

    role_a_resp = identity_client.post(
        "/api/identity/roles",
        json={"name": "ops_a", "description": "tenant-a role"},
        headers=_auth_header(token_a),
    )
    assert role_a_resp.status_code == 201
    role_a_id = role_a_resp.json()["id"]

    role_b_resp = identity_client.post(
        "/api/identity/roles",
        json={"name": "ops_b", "description": "tenant-b role"},
        headers=_auth_header(token_b),
    )
    assert role_b_resp.status_code == 201
    role_b_id = role_b_resp.json()["id"]

    with Session(db.get_engine(), expire_on_commit=False) as session:
        session.add(UserRole(tenant_id=tenant_a, user_id=user_a_id, role_id=role_b_id))
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()

        session.add(UserRole(tenant_id=tenant_a, user_id=user_a_id, role_id=role_a_id))
        session.commit()


def test_identity_role_templates_list_and_create(identity_client: TestClient) -> None:
    tenant_id = _create_tenant(identity_client, "tenant-template")
    _bootstrap_admin(identity_client, tenant_id, "admin_tpl", "pass-tpl")
    token = _login(identity_client, tenant_id, "admin_tpl", "pass-tpl")

    templates_resp = identity_client.get(
        "/api/identity/role-templates",
        headers=_auth_header(token),
    )
    assert templates_resp.status_code == 200
    template_keys = {item["key"] for item in templates_resp.json()}
    assert "dispatcher" in template_keys

    create_role_resp = identity_client.post(
        "/api/identity/roles:from-template",
        json={"template_key": "dispatcher", "name": "dispatch_ops"},
        headers=_auth_header(token),
    )
    assert create_role_resp.status_code == 201
    role_id = create_role_resp.json()["id"]

    create_user_resp = identity_client.post(
        "/api/identity/users",
        json={"username": "dispatcher_u", "password": "dispatcher-pass", "is_active": True},
        headers=_auth_header(token),
    )
    assert create_user_resp.status_code == 201
    user_id = create_user_resp.json()["id"]

    bind_resp = identity_client.post(
        f"/api/identity/users/{user_id}/roles/{role_id}",
        headers=_auth_header(token),
    )
    assert bind_resp.status_code == 204

    user_login = identity_client.post(
        "/api/identity/dev-login",
        json={"tenant_id": tenant_id, "username": "dispatcher_u", "password": "dispatcher-pass"},
    )
    assert user_login.status_code == 200
    permissions = set(user_login.json()["permissions"])
    assert "mission.write" in permissions
    assert "command.write" in permissions


def test_identity_role_template_not_found(identity_client: TestClient) -> None:
    tenant_id = _create_tenant(identity_client, "tenant-template-404")
    _bootstrap_admin(identity_client, tenant_id, "admin_tpl_404", "pass-tpl-404")
    token = _login(identity_client, tenant_id, "admin_tpl_404", "pass-tpl-404")

    create_role_resp = identity_client.post(
        "/api/identity/roles:from-template",
        json={"template_key": "unknown_template"},
        headers=_auth_header(token),
    )
    assert create_role_resp.status_code == 404


def test_identity_org_units_crud_and_membership_guards(identity_client: TestClient) -> None:
    tenant_id = _create_tenant(identity_client, "tenant-org")
    _bootstrap_admin(identity_client, tenant_id, "admin_org", "pass-org")
    token = _login(identity_client, tenant_id, "admin_org", "pass-org")

    create_user_resp = identity_client.post(
        "/api/identity/users",
        json={"username": "org_user", "password": "org-pass", "is_active": True},
        headers=_auth_header(token),
    )
    assert create_user_resp.status_code == 201
    user_id = create_user_resp.json()["id"]

    create_root_resp = identity_client.post(
        "/api/identity/org-units",
        json={"name": "HQ", "code": "HQ"},
        headers=_auth_header(token),
    )
    assert create_root_resp.status_code == 201
    root_id = create_root_resp.json()["id"]

    create_child_resp = identity_client.post(
        "/api/identity/org-units",
        json={"name": "Ops", "code": "OPS", "parent_id": root_id},
        headers=_auth_header(token),
    )
    assert create_child_resp.status_code == 201
    child_id = create_child_resp.json()["id"]

    create_field_resp = identity_client.post(
        "/api/identity/org-units",
        json={"name": "Field", "code": "FIELD", "parent_id": root_id},
        headers=_auth_header(token),
    )
    assert create_field_resp.status_code == 201
    field_id = create_field_resp.json()["id"]

    list_org_resp = identity_client.get("/api/identity/org-units", headers=_auth_header(token))
    assert list_org_resp.status_code == 200
    org_ids = [item["id"] for item in list_org_resp.json()]
    assert root_id in org_ids
    assert child_id in org_ids
    assert field_id in org_ids

    get_child_resp = identity_client.get(f"/api/identity/org-units/{child_id}", headers=_auth_header(token))
    assert get_child_resp.status_code == 200
    assert get_child_resp.json()["parent_id"] == root_id

    update_child_resp = identity_client.patch(
        f"/api/identity/org-units/{child_id}",
        json={"name": "Ops-Renamed", "is_active": False},
        headers=_auth_header(token),
    )
    assert update_child_resp.status_code == 200
    assert update_child_resp.json()["name"] == "Ops-Renamed"
    assert update_child_resp.json()["is_active"] is False

    bind_child_resp = identity_client.post(
        f"/api/identity/users/{user_id}/org-units/{child_id}",
        json={"is_primary": True},
        headers=_auth_header(token),
    )
    assert bind_child_resp.status_code == 200
    assert bind_child_resp.json()["is_primary"] is True

    bind_field_resp = identity_client.post(
        f"/api/identity/users/{user_id}/org-units/{field_id}",
        json={"is_primary": True},
        headers=_auth_header(token),
    )
    assert bind_field_resp.status_code == 200
    assert bind_field_resp.json()["is_primary"] is True

    list_user_org_resp = identity_client.get(
        f"/api/identity/users/{user_id}/org-units",
        headers=_auth_header(token),
    )
    assert list_user_org_resp.status_code == 200
    user_orgs = {item["org_unit_id"]: item for item in list_user_org_resp.json()}
    assert user_orgs[child_id]["is_primary"] is False
    assert user_orgs[field_id]["is_primary"] is True

    delete_root_resp = identity_client.delete(f"/api/identity/org-units/{root_id}", headers=_auth_header(token))
    assert delete_root_resp.status_code == 409

    delete_child_resp = identity_client.delete(f"/api/identity/org-units/{child_id}", headers=_auth_header(token))
    assert delete_child_resp.status_code == 409

    unbind_child_resp = identity_client.delete(
        f"/api/identity/users/{user_id}/org-units/{child_id}",
        headers=_auth_header(token),
    )
    assert unbind_child_resp.status_code == 204

    unbind_field_resp = identity_client.delete(
        f"/api/identity/users/{user_id}/org-units/{field_id}",
        headers=_auth_header(token),
    )
    assert unbind_field_resp.status_code == 204

    delete_child_resp = identity_client.delete(f"/api/identity/org-units/{child_id}", headers=_auth_header(token))
    assert delete_child_resp.status_code == 204

    delete_field_resp = identity_client.delete(f"/api/identity/org-units/{field_id}", headers=_auth_header(token))
    assert delete_field_resp.status_code == 204

    delete_root_resp = identity_client.delete(f"/api/identity/org-units/{root_id}", headers=_auth_header(token))
    assert delete_root_resp.status_code == 204


def test_identity_org_units_cross_tenant_returns_404(identity_client: TestClient) -> None:
    tenant_a = _create_tenant(identity_client, "tenant-org-a")
    tenant_b = _create_tenant(identity_client, "tenant-org-b")
    _bootstrap_admin(identity_client, tenant_a, "admin_org_a", "pass-a")
    _bootstrap_admin(identity_client, tenant_b, "admin_org_b", "pass-b")
    token_a = _login(identity_client, tenant_a, "admin_org_a", "pass-a")
    token_b = _login(identity_client, tenant_b, "admin_org_b", "pass-b")

    create_user_resp = identity_client.post(
        "/api/identity/users",
        json={"username": "a_user", "password": "a-pass", "is_active": True},
        headers=_auth_header(token_a),
    )
    assert create_user_resp.status_code == 201
    user_a_id = create_user_resp.json()["id"]

    create_org_b_resp = identity_client.post(
        "/api/identity/org-units",
        json={"name": "B-HQ", "code": "BHQ"},
        headers=_auth_header(token_b),
    )
    assert create_org_b_resp.status_code == 201
    org_b_id = create_org_b_resp.json()["id"]

    cross_get_org_resp = identity_client.get(
        f"/api/identity/org-units/{org_b_id}",
        headers=_auth_header(token_a),
    )
    assert cross_get_org_resp.status_code == 404

    cross_bind_resp = identity_client.post(
        f"/api/identity/users/{user_a_id}/org-units/{org_b_id}",
        headers=_auth_header(token_a),
    )
    assert cross_bind_resp.status_code == 404

    cross_list_user_org_resp = identity_client.get(
        f"/api/identity/users/{user_a_id}/org-units",
        headers=_auth_header(token_b),
    )
    assert cross_list_user_org_resp.status_code == 404


def test_identity_user_data_policy_upsert_and_get(identity_client: TestClient) -> None:
    tenant_id = _create_tenant(identity_client, "tenant-policy")
    _bootstrap_admin(identity_client, tenant_id, "admin_policy", "pass-policy")
    token = _login(identity_client, tenant_id, "admin_policy", "pass-policy")

    create_user_resp = identity_client.post(
        "/api/identity/users",
        json={"username": "policy_user", "password": "policy-pass", "is_active": True},
        headers=_auth_header(token),
    )
    assert create_user_resp.status_code == 201
    user_id = create_user_resp.json()["id"]

    upsert_resp = identity_client.put(
        f"/api/identity/users/{user_id}/data-policy",
        json={
            "scope_mode": "SCOPED",
            "org_unit_ids": ["OU-1", "OU-2"],
            "project_codes": ["PROJ-A"],
            "area_codes": ["AREA-NORTH"],
            "task_ids": ["TASK-1"],
        },
        headers=_auth_header(token),
    )
    assert upsert_resp.status_code == 200
    body = upsert_resp.json()
    assert body["scope_mode"] == "SCOPED"
    assert body["org_unit_ids"] == ["OU-1", "OU-2"]
    assert body["project_codes"] == ["PROJ-A"]

    get_resp = identity_client.get(
        f"/api/identity/users/{user_id}/data-policy",
        headers=_auth_header(token),
    )
    assert get_resp.status_code == 200
    assert get_resp.json()["task_ids"] == ["TASK-1"]


def test_identity_user_data_policy_cross_tenant_404(identity_client: TestClient) -> None:
    tenant_a = _create_tenant(identity_client, "tenant-policy-a")
    tenant_b = _create_tenant(identity_client, "tenant-policy-b")
    _bootstrap_admin(identity_client, tenant_a, "admin_policy_a", "pass-a")
    _bootstrap_admin(identity_client, tenant_b, "admin_policy_b", "pass-b")
    token_a = _login(identity_client, tenant_a, "admin_policy_a", "pass-a")
    token_b = _login(identity_client, tenant_b, "admin_policy_b", "pass-b")

    create_user_resp = identity_client.post(
        "/api/identity/users",
        json={"username": "policy_user_a", "password": "policy-pass", "is_active": True},
        headers=_auth_header(token_a),
    )
    assert create_user_resp.status_code == 201
    user_a_id = create_user_resp.json()["id"]

    cross_get_resp = identity_client.get(
        f"/api/identity/users/{user_a_id}/data-policy",
        headers=_auth_header(token_b),
    )
    assert cross_get_resp.status_code == 404

    cross_upsert_resp = identity_client.put(
        f"/api/identity/users/{user_a_id}/data-policy",
        json={"scope_mode": "SCOPED", "org_unit_ids": ["X"]},
        headers=_auth_header(token_b),
    )
    assert cross_upsert_resp.status_code == 404


def test_identity_user_data_policy_audit_hardening(identity_client: TestClient) -> None:
    tenant_a = _create_tenant(identity_client, "tenant-policy-audit-a")
    tenant_b = _create_tenant(identity_client, "tenant-policy-audit-b")
    _bootstrap_admin(identity_client, tenant_a, "admin_policy_audit_a", "pass-a")
    _bootstrap_admin(identity_client, tenant_b, "admin_policy_audit_b", "pass-b")
    token_a = _login(identity_client, tenant_a, "admin_policy_audit_a", "pass-a")
    token_b = _login(identity_client, tenant_b, "admin_policy_audit_b", "pass-b")

    create_user_resp = identity_client.post(
        "/api/identity/users",
        json={"username": "policy_audit_user", "password": "policy-pass", "is_active": True},
        headers=_auth_header(token_a),
    )
    assert create_user_resp.status_code == 201
    user_a_id = create_user_resp.json()["id"]

    upsert_resp = identity_client.put(
        f"/api/identity/users/{user_a_id}/data-policy",
        json={
            "scope_mode": "SCOPED",
            "org_unit_ids": ["OU-1"],
            "project_codes": ["PROJ-A"],
            "area_codes": ["AREA-1"],
            "task_ids": ["TASK-1"],
        },
        headers=_auth_header(token_a),
    )
    assert upsert_resp.status_code == 200

    success_log = _latest_audit(tenant_a, "identity.data_policy.upsert", status_code=200)
    success_detail = success_log.detail
    assert success_detail["who"]["tenant_id"] == tenant_a
    assert success_detail["what"]["target"]["user_id"] == user_a_id
    assert success_detail["what"]["policy_before"]["scope_mode"] == "ALL"
    assert success_detail["what"]["policy_after"]["scope_mode"] == "SCOPED"
    assert "scope_mode" in success_detail["what"]["changed_fields"]
    assert success_detail["result"]["outcome"] == "success"

    cross_upsert_resp = identity_client.put(
        f"/api/identity/users/{user_a_id}/data-policy",
        json={"scope_mode": "SCOPED", "org_unit_ids": ["OU-X"]},
        headers=_auth_header(token_b),
    )
    assert cross_upsert_resp.status_code == 404

    denied_log = _latest_audit(tenant_b, "identity.data_policy.upsert", status_code=404)
    denied_detail = denied_log.detail
    assert denied_detail["what"]["target"]["user_id"] == user_a_id
    assert denied_detail["result"]["outcome"] == "denied"
    assert denied_detail["result"]["reason"] == "cross_tenant_boundary"


def test_identity_user_roles_batch_bind_audit(identity_client: TestClient) -> None:
    tenant_a = _create_tenant(identity_client, "tenant-batch-a")
    tenant_b = _create_tenant(identity_client, "tenant-batch-b")
    _bootstrap_admin(identity_client, tenant_a, "admin_batch_a", "pass-a")
    _bootstrap_admin(identity_client, tenant_b, "admin_batch_b", "pass-b")
    token_a = _login(identity_client, tenant_a, "admin_batch_a", "pass-a")
    token_b = _login(identity_client, tenant_b, "admin_batch_b", "pass-b")

    create_user_resp = identity_client.post(
        "/api/identity/users",
        json={"username": "batch_user", "password": "batch-pass", "is_active": True},
        headers=_auth_header(token_a),
    )
    assert create_user_resp.status_code == 201
    user_a_id = create_user_resp.json()["id"]

    role_a1_resp = identity_client.post(
        "/api/identity/roles",
        json={"name": "role_a_1", "description": "role a1"},
        headers=_auth_header(token_a),
    )
    assert role_a1_resp.status_code == 201
    role_a1 = role_a1_resp.json()["id"]

    role_a2_resp = identity_client.post(
        "/api/identity/roles",
        json={"name": "role_a_2", "description": "role a2"},
        headers=_auth_header(token_a),
    )
    assert role_a2_resp.status_code == 201
    role_a2 = role_a2_resp.json()["id"]

    role_b_resp = identity_client.post(
        "/api/identity/roles",
        json={"name": "role_b_1", "description": "role b"},
        headers=_auth_header(token_b),
    )
    assert role_b_resp.status_code == 201
    role_b = role_b_resp.json()["id"]

    batch_resp = identity_client.post(
        f"/api/identity/users/{user_a_id}/roles:batch-bind",
        json={"role_ids": [role_a1, role_b, "missing-role", role_a2, role_a1]},
        headers=_auth_header(token_a),
    )
    assert batch_resp.status_code == 200
    body = batch_resp.json()
    assert body["requested_count"] == 5
    assert body["bound_count"] == 2
    assert body["already_bound_count"] == 1
    assert body["denied_count"] == 1
    assert body["missing_count"] == 1

    success_log = _latest_audit(tenant_a, "identity.user_role.batch_bind", status_code=200)
    success_detail = success_log.detail
    assert success_detail["what"]["target"]["user_id"] == user_a_id
    assert success_detail["what"]["batch_result"]["bound_count"] == 2
    assert role_b in success_detail["what"]["denied_role_ids"]
    assert success_detail["result"]["outcome"] == "partial_denied"
    assert success_detail["result"]["reason"] == "cross_tenant_boundary"

    cross_batch_resp = identity_client.post(
        f"/api/identity/users/{user_a_id}/roles:batch-bind",
        json={"role_ids": [role_a1]},
        headers=_auth_header(token_b),
    )
    assert cross_batch_resp.status_code == 404

    denied_log = _latest_audit(tenant_b, "identity.user_role.batch_bind", status_code=404)
    denied_detail = denied_log.detail
    assert denied_detail["what"]["target"]["user_id"] == user_a_id
    assert denied_detail["result"]["outcome"] == "denied"
    assert denied_detail["result"]["reason"] == "cross_tenant_boundary"
