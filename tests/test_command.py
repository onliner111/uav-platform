from __future__ import annotations

from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, SQLModel, create_engine, select

from app import main as app_main
from app.api.routers import command as command_router
from app.domain.models import CommandRequestRecord, CommandStatus, CommandType, EventRecord
from app.infra import audit, db, events
from app.services.command_service import CommandService


@pytest.fixture()
def command_client(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> Generator[TestClient, None, None]:
    db_path = tmp_path / "command_test.db"
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


def _create_drone(client: TestClient, token: str, name: str) -> str:
    response = client.post(
        "/api/registry/drones",
        json={"name": name, "vendor": "FAKE", "capabilities": {"rth": True}},
        headers=_auth_header(token),
    )
    assert response.status_code == 201
    return response.json()["id"]


def test_command_idempotency_returns_existing_record(command_client: TestClient) -> None:
    tenant_id = _create_tenant(command_client, "command-idempotent-tenant")
    _bootstrap_admin(command_client, tenant_id, "admin", "admin-pass")
    token = _login(command_client, tenant_id, "admin", "admin-pass")
    drone_id = _create_drone(command_client, token, "drone-command-1")

    payload = {
        "drone_id": drone_id,
        "type": "RTH",
        "params": {"reason": "test"},
        "idempotency_key": "idem-1",
        "expect_ack": True,
    }
    first = command_client.post(
        "/api/command/commands",
        json=payload,
        headers=_auth_header(token),
    )
    second = command_client.post(
        "/api/command/commands",
        json=payload,
        headers=_auth_header(token),
    )

    assert first.status_code == 201
    assert second.status_code == 200
    assert first.json()["id"] == second.json()["id"]
    assert first.json()["status"] == "ACKED"
    assert second.json()["attempts"] == 1

    command_id = first.json()["id"]
    with Session(db.engine) as session:
        rows = list(session.exec(select(EventRecord).where(EventRecord.tenant_id == tenant_id)).all())

    filtered_rows = [row for row in rows if row.payload.get("command_id") == command_id]
    event_types = [row.event_type for row in filtered_rows]
    assert event_types.count("command.requested") == 1
    assert event_types.count("command.acked") == 1


def test_command_ack_and_query(command_client: TestClient) -> None:
    tenant_id = _create_tenant(command_client, "command-ack-tenant")
    _bootstrap_admin(command_client, tenant_id, "admin", "admin-pass")
    token = _login(command_client, tenant_id, "admin", "admin-pass")
    drone_id = _create_drone(command_client, token, "drone-command-2")

    create_resp = command_client.post(
        "/api/command/commands",
        json={
            "drone_id": drone_id,
            "type": "LAND",
            "params": {},
            "idempotency_key": "ack-1",
            "expect_ack": True,
        },
        headers=_auth_header(token),
    )
    assert create_resp.status_code == 201
    body = create_resp.json()
    assert body["status"] == "ACKED"
    assert body["ack_ok"] is True
    assert "FAKE ack" in body["ack_message"]

    get_resp = command_client.get(
        f"/api/command/commands/{body['id']}",
        headers=_auth_header(token),
    )
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == body["id"]
    assert get_resp.json()["status"] == "ACKED"


def test_command_timeout_marked_timeout(command_client: TestClient) -> None:
    app_main.app.dependency_overrides[command_router.get_command_service] = (
        lambda: CommandService(ack_timeout_seconds=0.05)
    )

    tenant_id = _create_tenant(command_client, "command-timeout-tenant")
    _bootstrap_admin(command_client, tenant_id, "admin", "admin-pass")
    token = _login(command_client, tenant_id, "admin", "admin-pass")
    drone_id = _create_drone(command_client, token, "drone-command-3")

    timeout_resp = command_client.post(
        "/api/command/commands",
        json={
            "drone_id": drone_id,
            "type": "HOLD",
            "params": {"_fake_timeout": True},
            "idempotency_key": "timeout-1",
            "expect_ack": True,
        },
        headers=_auth_header(token),
    )
    assert timeout_resp.status_code == 201
    body = timeout_resp.json()
    assert body["status"] == "TIMEOUT"
    assert body["ack_ok"] is False
    assert body["attempts"] == 1


def test_command_cross_tenant_drone_access_returns_404(command_client: TestClient) -> None:
    tenant_a = _create_tenant(command_client, "command-cross-tenant-a")
    tenant_b = _create_tenant(command_client, "command-cross-tenant-b")
    _bootstrap_admin(command_client, tenant_a, "admin_a", "pass-a")
    _bootstrap_admin(command_client, tenant_b, "admin_b", "pass-b")
    token_a = _login(command_client, tenant_a, "admin_a", "pass-a")
    token_b = _login(command_client, tenant_b, "admin_b", "pass-b")
    drone_a = _create_drone(command_client, token_a, "drone-cross-a")

    response = command_client.post(
        "/api/command/commands",
        json={
            "drone_id": drone_a,
            "type": "RTH",
            "params": {},
            "idempotency_key": "cross-tenant-drone",
            "expect_ack": True,
        },
        headers=_auth_header(token_b),
    )
    assert response.status_code == 404


def test_command_requests_composite_fk_enforced_in_db(command_client: TestClient) -> None:
    tenant_a = _create_tenant(command_client, "command-fk-a")
    tenant_b = _create_tenant(command_client, "command-fk-b")
    _bootstrap_admin(command_client, tenant_a, "admin_a", "pass-a")
    _bootstrap_admin(command_client, tenant_b, "admin_b", "pass-b")

    token_a = _login(command_client, tenant_a, "admin_a", "pass-a")
    token_b = _login(command_client, tenant_b, "admin_b", "pass-b")
    drone_a = _create_drone(command_client, token_a, "drone-fk-a")
    drone_b = _create_drone(command_client, token_b, "drone-fk-b")

    with Session(db.engine, expire_on_commit=False) as session:
        session.add(
            CommandRequestRecord(
                tenant_id=tenant_a,
                drone_id=drone_b,
                command_type=CommandType.RTH,
                params={},
                idempotency_key="cross-tenant-fk",
                expect_ack=True,
                status=CommandStatus.PENDING,
                attempts=0,
                issued_by="tester",
            )
        )
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()

        session.add(
            CommandRequestRecord(
                tenant_id=tenant_a,
                drone_id=drone_a,
                command_type=CommandType.LAND,
                params={},
                idempotency_key="same-tenant-fk",
                expect_ack=True,
                status=CommandStatus.PENDING,
                attempts=0,
                issued_by="tester",
            )
        )
        session.commit()
