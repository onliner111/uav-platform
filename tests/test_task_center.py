from __future__ import annotations

from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlmodel import Session, SQLModel, create_engine, select

from app import main as app_main
from app.domain.models import AuditLog, EventRecord
from app.infra import audit, db, events


@pytest.fixture()
def task_center_client(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> Generator[TestClient, None, None]:
    db_path = tmp_path / "task_center_test.db"
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
) -> tuple[str, str]:
    role_resp = client.post(
        "/api/identity/roles",
        json={"name": f"{username}-role", "description": "task center test role"},
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
    token = _login(client, tenant_id, username, password)
    return user_id, token


def _create_org_unit(client: TestClient, token: str, name: str, code: str) -> str:
    response = client.post(
        "/api/identity/org-units",
        json={"name": name, "code": code, "is_active": True},
        headers=_auth_header(token),
    )
    assert response.status_code == 201
    return response.json()["id"]


def _bind_user_org_unit(client: TestClient, token: str, user_id: str, org_unit_id: str) -> None:
    response = client.post(
        f"/api/identity/users/{user_id}/org-units/{org_unit_id}",
        json={"is_primary": True},
        headers=_auth_header(token),
    )
    assert response.status_code == 200


def _create_asset_with_region(client: TestClient, token: str, code: str, region_code: str) -> str:
    create_resp = client.post(
        "/api/assets",
        json={"asset_type": "UAV", "asset_code": code, "name": f"asset-{code}"},
        headers=_auth_header(token),
    )
    assert create_resp.status_code == 201
    asset_id = create_resp.json()["id"]
    avail_resp = client.post(
        f"/api/assets/{asset_id}/availability",
        json={"availability_status": "AVAILABLE", "region_code": region_code},
        headers=_auth_header(token),
    )
    assert avail_resp.status_code == 200
    return asset_id


def test_task_center_p0_workflow(task_center_client: TestClient) -> None:
    tenant_id = _create_tenant(task_center_client, "task-center-main")
    _bootstrap_admin(task_center_client, tenant_id, "admin", "admin-pass")
    admin_token = _login(task_center_client, tenant_id, "admin", "admin-pass")

    assignee_id, _assignee_token = _create_user_with_permissions(
        task_center_client,
        admin_token,
        tenant_id,
        "assignee",
        "assignee-pass",
        ["mission.read", "mission.write"],
    )

    create_type_resp = task_center_client.post(
        "/api/task-center/types",
        json={"code": "INSPECT", "name": "inspection", "description": "inspection flow"},
        headers=_auth_header(admin_token),
    )
    assert create_type_resp.status_code == 201
    task_type_id = create_type_resp.json()["id"]

    create_template_resp = task_center_client.post(
        "/api/task-center/templates",
        json={
            "task_type_id": task_type_id,
            "template_key": "tpl-inspect-p0",
            "name": "Inspect Template",
            "requires_approval": True,
            "default_priority": 4,
            "default_risk_level": 2,
            "default_checklist": [{"code": "C1", "title": "check camera"}],
            "default_payload": {"region": "A"},
        },
        headers=_auth_header(admin_token),
    )
    assert create_template_resp.status_code == 201
    template_id = create_template_resp.json()["id"]

    create_task_resp = task_center_client.post(
        "/api/task-center/tasks",
        json={
            "task_type_id": task_type_id,
            "template_id": template_id,
            "name": "task-main",
            "project_code": "P11",
            "area_code": "A1",
        },
        headers=_auth_header(admin_token),
    )
    assert create_task_resp.status_code == 201
    task_id = create_task_resp.json()["id"]
    assert create_task_resp.json()["state"] == "DRAFT"

    direct_dispatch = task_center_client.post(
        f"/api/task-center/tasks/{task_id}/dispatch",
        json={"assigned_to": assignee_id},
        headers=_auth_header(admin_token),
    )
    assert direct_dispatch.status_code == 409

    submit_resp = task_center_client.post(
        f"/api/task-center/tasks/{task_id}/submit-approval",
        json={"note": "please review"},
        headers=_auth_header(admin_token),
    )
    assert submit_resp.status_code == 200
    assert submit_resp.json()["state"] == "APPROVAL_PENDING"

    approve_resp = task_center_client.post(
        f"/api/task-center/tasks/{task_id}/approve",
        json={"decision": "APPROVE", "note": "approved"},
        headers=_auth_header(admin_token),
    )
    assert approve_resp.status_code == 200
    assert approve_resp.json()["state"] == "APPROVED"

    dispatch_resp = task_center_client.post(
        f"/api/task-center/tasks/{task_id}/dispatch",
        json={"assigned_to": assignee_id, "note": "manual dispatch"},
        headers=_auth_header(admin_token),
    )
    assert dispatch_resp.status_code == 200
    assert dispatch_resp.json()["state"] == "DISPATCHED"
    assert dispatch_resp.json()["dispatch_mode"] == "MANUAL"

    in_progress_resp = task_center_client.post(
        f"/api/task-center/tasks/{task_id}/transition",
        json={"target_state": "IN_PROGRESS"},
        headers=_auth_header(admin_token),
    )
    assert in_progress_resp.status_code == 200
    assert in_progress_resp.json()["state"] == "IN_PROGRESS"

    accepted_resp = task_center_client.post(
        f"/api/task-center/tasks/{task_id}/transition",
        json={"target_state": "ACCEPTED"},
        headers=_auth_header(admin_token),
    )
    assert accepted_resp.status_code == 200
    assert accepted_resp.json()["state"] == "ACCEPTED"

    archived_resp = task_center_client.post(
        f"/api/task-center/tasks/{task_id}/transition",
        json={"target_state": "ARCHIVED"},
        headers=_auth_header(admin_token),
    )
    assert archived_resp.status_code == 200
    assert archived_resp.json()["state"] == "ARCHIVED"

    history_resp = task_center_client.get(
        f"/api/task-center/tasks/{task_id}/history",
        headers=_auth_header(admin_token),
    )
    assert history_resp.status_code == 200
    actions = [item["action"] for item in history_resp.json()]
    assert actions[0] == "created"
    assert "submitted_for_approval" in actions
    assert "approved" in actions
    assert "dispatched" in actions
    assert actions.count("state_changed") == 3

    with Session(db.engine) as session:
        events_rows = list(session.exec(select(EventRecord).where(EventRecord.tenant_id == tenant_id)).all())
        audit_rows = list(session.exec(select(AuditLog).where(AuditLog.tenant_id == tenant_id)).all())

    task_events = [row for row in events_rows if row.payload.get("task_id") == task_id]
    event_types = {row.event_type for row in task_events}
    assert "task_center.task.created" in event_types
    assert "task_center.task.approved" in event_types
    assert "task_center.task.dispatched" in event_types
    assert "task_center.task.state_changed" in event_types

    audit_actions = {row.action for row in audit_rows}
    assert "task_center.task.create" in audit_actions
    assert "task_center.task.approve" in audit_actions
    assert "task_center.task.dispatch" in audit_actions


def test_task_center_tenant_isolation_and_cross_tenant_assignee(task_center_client: TestClient) -> None:
    tenant_a = _create_tenant(task_center_client, "task-center-a")
    tenant_b = _create_tenant(task_center_client, "task-center-b")
    _bootstrap_admin(task_center_client, tenant_a, "admin-a", "pass-a")
    _bootstrap_admin(task_center_client, tenant_b, "admin-b", "pass-b")

    token_a = _login(task_center_client, tenant_a, "admin-a", "pass-a")
    token_b = _login(task_center_client, tenant_b, "admin-b", "pass-b")

    type_resp = task_center_client.post(
        "/api/task-center/types",
        json={"code": "OPS", "name": "ops"},
        headers=_auth_header(token_a),
    )
    assert type_resp.status_code == 201
    task_type_id = type_resp.json()["id"]

    task_resp = task_center_client.post(
        "/api/task-center/tasks",
        json={"task_type_id": task_type_id, "name": "tenant-a-task"},
        headers=_auth_header(token_a),
    )
    assert task_resp.status_code == 201
    task_id = task_resp.json()["id"]

    user_b_id, _token_user_b = _create_user_with_permissions(
        task_center_client,
        token_b,
        tenant_b,
        "b-operator",
        "b-pass",
        ["mission.read", "mission.write"],
    )

    cross_dispatch = task_center_client.post(
        f"/api/task-center/tasks/{task_id}/dispatch",
        json={"assigned_to": user_b_id},
        headers=_auth_header(token_a),
    )
    assert cross_dispatch.status_code == 404

    cross_get = task_center_client.get(
        f"/api/task-center/tasks/{task_id}",
        headers=_auth_header(token_b),
    )
    assert cross_get.status_code == 404

    cross_history = task_center_client.get(
        f"/api/task-center/tasks/{task_id}/history",
        headers=_auth_header(token_b),
    )
    assert cross_history.status_code == 404

    list_b = task_center_client.get("/api/task-center/tasks", headers=_auth_header(token_b))
    assert list_b.status_code == 200
    assert list_b.json() == []


def test_task_center_permission_guards(task_center_client: TestClient) -> None:
    tenant_id = _create_tenant(task_center_client, "task-center-perm")
    _bootstrap_admin(task_center_client, tenant_id, "admin", "admin-pass")
    admin_token = _login(task_center_client, tenant_id, "admin", "admin-pass")

    _reader_id, reader_token = _create_user_with_permissions(
        task_center_client,
        admin_token,
        tenant_id,
        "reader",
        "reader-pass",
        ["mission.read"],
    )

    create_type_resp = task_center_client.post(
        "/api/task-center/types",
        json={"code": "SEC", "name": "security"},
        headers=_auth_header(admin_token),
    )
    assert create_type_resp.status_code == 201

    create_denied = task_center_client.post(
        "/api/task-center/types",
        json={"code": "NOPE", "name": "nope"},
        headers=_auth_header(reader_token),
    )
    assert create_denied.status_code == 403

    list_ok = task_center_client.get("/api/task-center/types", headers=_auth_header(reader_token))
    assert list_ok.status_code == 200
    assert any(item["code"] == "SEC" for item in list_ok.json())


def test_task_center_auto_dispatch_and_enhancement_workflow(task_center_client: TestClient) -> None:
    tenant_id = _create_tenant(task_center_client, "task-center-auto")
    _bootstrap_admin(task_center_client, tenant_id, "admin", "admin-pass")
    admin_token = _login(task_center_client, tenant_id, "admin", "admin-pass")

    org_unit_id = _create_org_unit(task_center_client, admin_token, "ops-center", "OPS-CENTER")
    user_a_id, _token_a = _create_user_with_permissions(
        task_center_client,
        admin_token,
        tenant_id,
        "candidate_a",
        "pass-a",
        ["mission.read", "mission.write", "identity.read"],
    )
    user_b_id, _token_b = _create_user_with_permissions(
        task_center_client,
        admin_token,
        tenant_id,
        "candidate_b",
        "pass-b",
        ["mission.read", "mission.write", "identity.read"],
    )
    _bind_user_org_unit(task_center_client, admin_token, user_a_id, org_unit_id)

    _asset_id = _create_asset_with_region(task_center_client, admin_token, "AUTO-UAV-01", "AREA-X")

    type_resp = task_center_client.post(
        "/api/task-center/types",
        json={"code": "EMG", "name": "emergency"},
        headers=_auth_header(admin_token),
    )
    assert type_resp.status_code == 201
    task_type_id = type_resp.json()["id"]

    create_task_resp = task_center_client.post(
        "/api/task-center/tasks",
        json={
            "task_type_id": task_type_id,
            "name": "auto-dispatch-task",
            "org_unit_id": org_unit_id,
            "area_code": "AREA-X",
            "risk_level": 2,
            "checklist": [{"code": "C1", "title": "init"}],
        },
        headers=_auth_header(admin_token),
    )
    assert create_task_resp.status_code == 201
    task_id = create_task_resp.json()["id"]

    auto_dispatch_resp = task_center_client.post(
        f"/api/task-center/tasks/{task_id}/auto-dispatch",
        json={"candidate_user_ids": [user_b_id, user_a_id], "note": "auto"},
        headers=_auth_header(admin_token),
    )
    assert auto_dispatch_resp.status_code == 200
    auto_payload = auto_dispatch_resp.json()
    assert auto_payload["task"]["state"] == "DISPATCHED"
    assert auto_payload["task"]["dispatch_mode"] == "AUTO"
    assert auto_payload["selected_user_id"] == user_a_id
    assert len(auto_payload["scores"]) == 2
    assert auto_payload["resource_snapshot"]["available_assets"] >= 1
    assert auto_payload["scores"][0]["total_score"] >= auto_payload["scores"][1]["total_score"]

    risk_update_resp = task_center_client.patch(
        f"/api/task-center/tasks/{task_id}/risk-checklist",
        json={
            "risk_level": 5,
            "checklist": [
                {"code": "C1", "title": "updated", "status": "DONE"},
                {"code": "C2", "title": "extra", "status": "PENDING"},
            ],
            "note": "risk update",
        },
        headers=_auth_header(admin_token),
    )
    assert risk_update_resp.status_code == 200
    assert risk_update_resp.json()["risk_level"] == 5
    assert len(risk_update_resp.json()["checklist"]) == 2

    attachment_resp = task_center_client.post(
        f"/api/task-center/tasks/{task_id}/attachments",
        json={"name": "site-photo", "url": "https://example.com/a.jpg", "media_type": "image/jpeg"},
        headers=_auth_header(admin_token),
    )
    assert attachment_resp.status_code == 200
    assert len(attachment_resp.json()["attachments"]) == 1

    comment_resp = task_center_client.post(
        f"/api/task-center/tasks/{task_id}/comments",
        json={"content": "operator arrived"},
        headers=_auth_header(admin_token),
    )
    assert comment_resp.status_code == 200
    assert comment_resp.json()["content"] == "operator arrived"

    list_comments_resp = task_center_client.get(
        f"/api/task-center/tasks/{task_id}/comments",
        headers=_auth_header(admin_token),
    )
    assert list_comments_resp.status_code == 200
    assert len(list_comments_resp.json()) == 1

    with Session(db.engine) as session:
        event_rows = list(session.exec(select(EventRecord).where(EventRecord.tenant_id == tenant_id)).all())
        audit_rows = list(session.exec(select(AuditLog).where(AuditLog.tenant_id == tenant_id)).all())

    event_types = {row.event_type for row in event_rows if row.payload.get("task_id") == task_id}
    assert "task_center.task.auto_dispatched" in event_types
    assert "task_center.task.risk_checklist_updated" in event_types
    assert "task_center.task.attachment_added" in event_types
    assert "task_center.task.comment_added" in event_types

    audit_actions = {row.action for row in audit_rows}
    assert "task_center.task.auto_dispatch" in audit_actions
    assert "task_center.task.risk_checklist.update" in audit_actions
    assert "task_center.task.attachment.add" in audit_actions
    assert "task_center.task.comment.add" in audit_actions


def test_task_center_v2_template_conflict_and_batch(task_center_client: TestClient) -> None:
    tenant_id = _create_tenant(task_center_client, "task-center-v2")
    _bootstrap_admin(task_center_client, tenant_id, "admin", "admin-pass")
    admin_token = _login(task_center_client, tenant_id, "admin", "admin-pass")

    org_unit_id = _create_org_unit(task_center_client, admin_token, "v2-ops", "V2-OPS")
    user_a_id, _ = _create_user_with_permissions(
        task_center_client,
        admin_token,
        tenant_id,
        "v2-user-a",
        "v2-pass-a",
        ["mission.read", "mission.write", "identity.read"],
    )
    user_b_id, _ = _create_user_with_permissions(
        task_center_client,
        admin_token,
        tenant_id,
        "v2-user-b",
        "v2-pass-b",
        ["mission.read", "mission.write", "identity.read"],
    )
    _bind_user_org_unit(task_center_client, admin_token, user_a_id, org_unit_id)
    _create_asset_with_region(task_center_client, admin_token, "V2-UAV-01", "AREA-V2")

    task_type_resp = task_center_client.post(
        "/api/task-center/types",
        json={"code": "V2-INSPECT", "name": "v2-inspect"},
        headers=_auth_header(admin_token),
    )
    assert task_type_resp.status_code == 201
    task_type_id = task_type_resp.json()["id"]

    template_resp = task_center_client.post(
        "/api/task-center/templates",
        json={
            "task_type_id": task_type_id,
            "template_key": "v2-template-base",
            "name": "v2-template",
            "requires_approval": False,
            "default_priority": 6,
            "default_risk_level": 3,
            "route_template": {"mode": "grid", "waypoints": 12},
            "payload_template": {"camera": "4k", "gimbal": "stabilized"},
            "default_payload": {"biz_tag": "phase20"},
        },
        headers=_auth_header(admin_token),
    )
    assert template_resp.status_code == 201
    template_payload = template_resp.json()
    template_id = template_payload["id"]
    assert template_payload["template_version"] == "v2"
    assert template_payload["route_template"]["mode"] == "grid"
    assert template_payload["payload_template"]["camera"] == "4k"

    clone_resp = task_center_client.post(
        f"/api/task-center/templates/{template_id}:clone",
        json={"template_key": "v2-template-clone", "name": "v2-template-clone"},
        headers=_auth_header(admin_token),
    )
    assert clone_resp.status_code == 201
    assert clone_resp.json()["template_key"] == "v2-template-clone"
    assert clone_resp.json()["route_template"]["mode"] == "grid"

    start_at = datetime.now(UTC).replace(microsecond=0) + timedelta(hours=1)
    end_at = start_at + timedelta(hours=2)

    batch_resp = task_center_client.post(
        "/api/task-center/tasks:batch-create",
        json={
            "tasks": [
                {
                    "task_type_id": task_type_id,
                    "template_id": template_id,
                    "name": "v2-task-a",
                    "org_unit_id": org_unit_id,
                    "area_code": "AREA-V2",
                    "planned_start_at": start_at.isoformat(),
                    "planned_end_at": end_at.isoformat(),
                },
                {
                    "task_type_id": task_type_id,
                    "template_id": template_id,
                    "name": "v2-task-b",
                    "org_unit_id": org_unit_id,
                    "area_code": "AREA-V2",
                    "planned_start_at": (start_at + timedelta(minutes=30)).isoformat(),
                    "planned_end_at": (end_at + timedelta(minutes=30)).isoformat(),
                    "route_template": {"mode": "point", "waypoints": 4},
                },
            ]
        },
        headers=_auth_header(admin_token),
    )
    assert batch_resp.status_code == 201
    batch_payload = batch_resp.json()
    assert batch_payload["total"] == 2
    task_a = batch_payload["tasks"][0]["id"]
    task_b = batch_payload["tasks"][1]["id"]
    assert batch_payload["tasks"][1]["context_data"]["route_template"]["mode"] == "point"

    dispatch_a = task_center_client.post(
        f"/api/task-center/tasks/{task_a}/dispatch",
        json={"assigned_to": user_a_id},
        headers=_auth_header(admin_token),
    )
    assert dispatch_a.status_code == 200

    dispatch_b_conflict = task_center_client.post(
        f"/api/task-center/tasks/{task_b}/dispatch",
        json={"assigned_to": user_a_id},
        headers=_auth_header(admin_token),
    )
    assert dispatch_b_conflict.status_code == 409
    assert "overlapping assignment" in dispatch_b_conflict.json()["detail"]

    auto_dispatch_b = task_center_client.post(
        f"/api/task-center/tasks/{task_b}/auto-dispatch",
        json={"candidate_user_ids": [user_a_id, user_b_id]},
        headers=_auth_header(admin_token),
    )
    assert auto_dispatch_b.status_code == 200
    auto_payload = auto_dispatch_b.json()
    assert auto_payload["selected_user_id"] == user_b_id
    assert auto_payload["resource_snapshot"]["score_strategy"]["version"] == "v2.0"
    assert any("overlap_conflicts=" in reason for reason in auto_payload["scores"][0]["reasons"])

    with Session(db.engine) as session:
        audit_rows = list(session.exec(select(AuditLog).where(AuditLog.tenant_id == tenant_id)).all())
    audit_actions = {row.action for row in audit_rows}
    assert "task_center.template.clone" in audit_actions
    assert "task_center.task.batch_create" in audit_actions
