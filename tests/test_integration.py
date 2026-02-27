from __future__ import annotations

import time
from collections.abc import Generator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlmodel import SQLModel, create_engine

from app import main as app_main
from app.infra import audit, db, events, redis_state
from app.services.integration_service import IntegrationService


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
def integration_client(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> Generator[TestClient, None, None]:
    db_path = tmp_path / "integration_test.db"
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
    monkeypatch.setattr(IntegrationService, "_device_sessions", {})
    monkeypatch.setattr(IntegrationService, "_video_streams", {})

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


def _create_drone(client: TestClient, token: str, *, name: str, vendor: str = "FAKE") -> str:
    response = client.post(
        "/api/registry/drones",
        json={"name": name, "vendor": vendor, "capabilities": {}},
        headers=_auth_header(token),
    )
    assert response.status_code == 201
    return response.json()["id"]


def _ingest_telemetry(
    client: TestClient,
    token: str,
    *,
    drone_id: str,
    lat: float,
    lon: float,
) -> None:
    response = client.post(
        "/api/telemetry/ingest",
        json={
            "tenant_id": "spoofed-tenant",
            "drone_id": drone_id,
            "ts": datetime.now(UTC).isoformat(),
            "position": {"lat": lat, "lon": lon, "alt_m": 120.0},
            "battery": {"percent": 75.0},
            "mode": "AUTO",
            "health": {"source": "test"},
        },
        headers=_auth_header(token),
    )
    assert response.status_code == 200


def _wait_until_session_done(client: TestClient, token: str, session_id: str) -> dict[str, object]:
    deadline = time.monotonic() + 2.0
    last: dict[str, object] = {}
    while time.monotonic() < deadline:
        response = client.get(
            f"/api/integration/device-sessions/{session_id}",
            headers=_auth_header(token),
        )
        assert response.status_code == 200
        last = response.json()
        if last["status"] in {"COMPLETED", "FAILED"}:
            return last
        time.sleep(0.05)
    raise AssertionError(f"session did not complete in time: {last}")


def test_device_session_lifecycle_conflict_and_tenant_boundary(integration_client: TestClient) -> None:
    tenant_a = _create_tenant(integration_client, "integration-tenant-a")
    tenant_b = _create_tenant(integration_client, "integration-tenant-b")
    _bootstrap_admin(integration_client, tenant_a, "admin-a", "pass-a")
    _bootstrap_admin(integration_client, tenant_b, "admin-b", "pass-b")
    token_a = _login(integration_client, tenant_a, "admin-a", "pass-a")
    token_b = _login(integration_client, tenant_b, "admin-b", "pass-b")

    drone_a = _create_drone(integration_client, token_a, name="drone-a", vendor="MAVLINK")

    start_running = integration_client.post(
        "/api/integration/device-sessions/start",
        json={
            "drone_id": drone_a,
            "adapter_vendor": "MAVLINK",
            "simulation_mode": True,
            "telemetry_interval_seconds": 0.01,
        },
        headers=_auth_header(token_a),
    )
    assert start_running.status_code == 201
    running_session_id = start_running.json()["session_id"]

    conflict = integration_client.post(
        "/api/integration/device-sessions/start",
        json={
            "drone_id": drone_a,
            "simulation_mode": True,
            "telemetry_interval_seconds": 0.01,
        },
        headers=_auth_header(token_a),
    )
    assert conflict.status_code == 409

    cross_tenant_get = integration_client.get(
        f"/api/integration/device-sessions/{running_session_id}",
        headers=_auth_header(token_b),
    )
    assert cross_tenant_get.status_code == 404

    stop_resp = integration_client.post(
        f"/api/integration/device-sessions/{running_session_id}:stop",
        headers=_auth_header(token_a),
    )
    assert stop_resp.status_code == 200
    assert stop_resp.json()["status"] == "STOPPED"

    bounded = integration_client.post(
        "/api/integration/device-sessions/start",
        json={
            "drone_id": drone_a,
            "adapter_vendor": "MAVLINK",
            "simulation_mode": True,
            "telemetry_interval_seconds": 0.0,
            "max_samples": 3,
        },
        headers=_auth_header(token_a),
    )
    assert bounded.status_code == 201
    bounded_session_id = bounded.json()["session_id"]

    done = _wait_until_session_done(integration_client, token_a, bounded_session_id)
    assert done["status"] == "COMPLETED"
    assert int(done["samples_ingested"]) >= 3

    latest = integration_client.get(
        f"/api/telemetry/drones/{drone_a}/latest",
        headers=_auth_header(token_a),
    )
    assert latest.status_code == 200
    assert latest.json()["drone_id"] == drone_a


def test_video_stream_crud_and_live_status(integration_client: TestClient) -> None:
    tenant_a = _create_tenant(integration_client, "integration-video-tenant-a")
    tenant_b = _create_tenant(integration_client, "integration-video-tenant-b")
    _bootstrap_admin(integration_client, tenant_a, "admin-a", "pass-a")
    _bootstrap_admin(integration_client, tenant_b, "admin-b", "pass-b")
    token_a = _login(integration_client, tenant_a, "admin-a", "pass-a")
    token_b = _login(integration_client, tenant_b, "admin-b", "pass-b")

    drone_a = _create_drone(integration_client, token_a, name="drone-video-a", vendor="FAKE")

    create_resp = integration_client.post(
        "/api/integration/video-streams",
        json={
            "stream_key": "cam-a1",
            "protocol": "RTSP",
            "endpoint": "rtsp://demo.local/live/cam-a1",
            "label": "A1 Main",
            "drone_id": drone_a,
            "enabled": True,
        },
        headers=_auth_header(token_a),
    )
    assert create_resp.status_code == 201
    stream_id = create_resp.json()["stream_id"]
    assert create_resp.json()["status"] == "STANDBY"

    duplicate = integration_client.post(
        "/api/integration/video-streams",
        json={
            "stream_key": "cam-a1",
            "protocol": "WEBRTC",
            "endpoint": "webrtc://demo.local/live/cam-a1",
            "enabled": True,
        },
        headers=_auth_header(token_a),
    )
    assert duplicate.status_code == 409

    cross_tenant_get = integration_client.get(
        f"/api/integration/video-streams/{stream_id}",
        headers=_auth_header(token_b),
    )
    assert cross_tenant_get.status_code == 404

    _ingest_telemetry(integration_client, token_a, drone_id=drone_a, lat=30.12345, lon=114.54321)

    live_resp = integration_client.get(
        f"/api/integration/video-streams/{stream_id}",
        headers=_auth_header(token_a),
    )
    assert live_resp.status_code == 200
    live_payload = live_resp.json()
    assert live_payload["status"] == "LIVE"
    assert live_payload["linked_telemetry"]["lat"] == pytest.approx(30.12345)
    assert live_payload["linked_telemetry"]["lon"] == pytest.approx(114.54321)

    disable_resp = integration_client.patch(
        f"/api/integration/video-streams/{stream_id}",
        json={"enabled": False},
        headers=_auth_header(token_a),
    )
    assert disable_resp.status_code == 200
    assert disable_resp.json()["status"] == "DISABLED"

    list_resp = integration_client.get(
        "/api/integration/video-streams",
        headers=_auth_header(token_a),
    )
    assert list_resp.status_code == 200
    assert len(list_resp.json()) == 1

    delete_resp = integration_client.delete(
        f"/api/integration/video-streams/{stream_id}",
        headers=_auth_header(token_a),
    )
    assert delete_resp.status_code == 204

    missing_resp = integration_client.get(
        f"/api/integration/video-streams/{stream_id}",
        headers=_auth_header(token_a),
    )
    assert missing_resp.status_code == 404
