from __future__ import annotations

from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlmodel import SQLModel, create_engine

from app import main as app_main
from app.infra import audit, db, events, redis_state


class FakeRedis:
    def __init__(self) -> None:
        self._store: dict[str, str] = {}

    def set(self, key: str, value: str) -> bool:
        self._store[key] = value
        return True

    def get(self, key: str) -> str | None:
        return self._store.get(key)

    def ping(self) -> bool:
        return True


@pytest.fixture()
def telemetry_client(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> Generator[TestClient, None, None]:
    db_path = tmp_path / "telemetry_test.db"
    test_engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
    )
    SQLModel.metadata.create_all(test_engine)
    fake_redis = FakeRedis()

    monkeypatch.setattr(db, "engine", test_engine)
    monkeypatch.setattr(audit, "engine", test_engine)
    monkeypatch.setattr(events, "engine", test_engine)
    monkeypatch.setattr(redis_state, "get_redis", lambda: fake_redis)

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


def _telemetry_payload(drone_id: str) -> dict[str, object]:
    return {
        "tenant_id": "spoofed-tenant",
        "drone_id": drone_id,
        "position": {"lat": 30.123, "lon": 114.456, "alt_m": 120.5},
        "battery": {"percent": 88.5},
        "mode": "AUTO",
        "health": {"gps": "ok"},
    }


def test_telemetry_ingest_and_query_latest(telemetry_client: TestClient) -> None:
    tenant_id = _create_tenant(telemetry_client, "telemetry-tenant")
    _bootstrap_admin(telemetry_client, tenant_id, "admin", "admin-pass")
    token = _login(telemetry_client, tenant_id, "admin", "admin-pass")

    ingest_resp = telemetry_client.post(
        "/api/telemetry/ingest",
        json=_telemetry_payload("drone-1"),
        headers=_auth_header(token),
    )
    assert ingest_resp.status_code == 200
    assert ingest_resp.json()["tenant_id"] == tenant_id

    latest_resp = telemetry_client.get(
        "/api/telemetry/drones/drone-1/latest",
        headers=_auth_header(token),
    )
    assert latest_resp.status_code == 200
    body = latest_resp.json()
    assert body["tenant_id"] == tenant_id
    assert body["drone_id"] == "drone-1"
    assert body["position"]["lat"] == pytest.approx(30.123)


def test_telemetry_ws_receives_updates(telemetry_client: TestClient) -> None:
    tenant_id = _create_tenant(telemetry_client, "telemetry-ws-tenant")
    _bootstrap_admin(telemetry_client, tenant_id, "admin", "admin-pass")
    token = _login(telemetry_client, tenant_id, "admin", "admin-pass")

    with telemetry_client.websocket_connect(f"/ws/drones?token={token}") as websocket:
        ingest_resp = telemetry_client.post(
            "/api/telemetry/ingest",
            json=_telemetry_payload("drone-ws"),
            headers=_auth_header(token),
        )
        assert ingest_resp.status_code == 200

        message = websocket.receive_json()
        assert message["tenant_id"] == tenant_id
        assert message["drone_id"] == "drone-ws"
        assert message["mode"] == "AUTO"

