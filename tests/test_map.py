from __future__ import annotations

from collections.abc import Generator
from datetime import UTC, datetime, timedelta
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
def map_client(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> Generator[TestClient, None, None]:
    db_path = tmp_path / "map_test.db"
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


def _create_drone(client: TestClient, token: str, *, name: str) -> str:
    response = client.post(
        "/api/registry/drones",
        json={"name": name, "vendor": "FAKE", "capabilities": {}},
        headers=_auth_header(token),
    )
    assert response.status_code == 201
    return response.json()["id"]


def _create_asset(client: TestClient, token: str, *, asset_code: str) -> str:
    response = client.post(
        "/api/assets",
        json={"asset_type": "UAV", "asset_code": asset_code, "name": f"Asset-{asset_code}"},
        headers=_auth_header(token),
    )
    assert response.status_code == 201
    return response.json()["id"]


def _bind_asset(client: TestClient, token: str, *, asset_id: str, drone_id: str) -> None:
    response = client.post(
        f"/api/assets/{asset_id}/bind",
        json={"bound_to_drone_id": drone_id},
        headers=_auth_header(token),
    )
    assert response.status_code == 200


def _create_mission(client: TestClient, token: str, *, name: str) -> str:
    response = client.post(
        "/api/mission/missions",
        json={"name": name, "type": "POINT_TASK", "payload": {}, "constraints": {}},
        headers=_auth_header(token),
    )
    assert response.status_code == 201
    return response.json()["id"]


def _create_incident(client: TestClient, token: str, *, title: str, point_wkt: str) -> str:
    response = client.post(
        "/api/incidents",
        json={"title": title, "level": "P1", "location_geom": point_wkt},
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
    ts: datetime,
    battery_percent: float = 80.0,
) -> None:
    response = client.post(
        "/api/telemetry/ingest",
        json={
            "tenant_id": "spoofed-tenant",
            "drone_id": drone_id,
            "ts": ts.isoformat(),
            "position": {"lat": lat, "lon": lon, "alt_m": 120.0},
            "battery": {"percent": battery_percent},
            "mode": "AUTO",
            "health": {"low_battery": battery_percent <= 20.0},
        },
        headers=_auth_header(token),
    )
    assert response.status_code == 200


def test_map_overview_and_layers_are_tenant_scoped(map_client: TestClient) -> None:
    tenant_a = _create_tenant(map_client, "map-tenant-a")
    tenant_b = _create_tenant(map_client, "map-tenant-b")
    _bootstrap_admin(map_client, tenant_a, "admin_a", "pass-a")
    _bootstrap_admin(map_client, tenant_b, "admin_b", "pass-b")
    token_a = _login(map_client, tenant_a, "admin_a", "pass-a")
    token_b = _login(map_client, tenant_b, "admin_b", "pass-b")

    drone_a = _create_drone(map_client, token_a, name="drone-a")
    drone_b = _create_drone(map_client, token_b, name="drone-b")
    asset_a = _create_asset(map_client, token_a, asset_code="ASSET-A")
    _bind_asset(map_client, token_a, asset_id=asset_a, drone_id=drone_a)

    mission_a = _create_mission(map_client, token_a, name="mission-a")
    mission_b = _create_mission(map_client, token_b, name="mission-b")
    incident_a = _create_incident(map_client, token_a, title="incident-a", point_wkt="POINT(114.0 30.0)")
    incident_b = _create_incident(map_client, token_b, title="incident-b", point_wkt="POINT(115.0 31.0)")

    now = datetime.now(UTC)
    _ingest_telemetry(map_client, token_a, drone_id=drone_a, lat=30.0, lon=114.0, ts=now, battery_percent=10.0)
    _ingest_telemetry(map_client, token_b, drone_id=drone_b, lat=31.0, lon=115.0, ts=now, battery_percent=80.0)

    overview = map_client.get("/api/map/overview", headers=_auth_header(token_a))
    assert overview.status_code == 200
    overview_body = overview.json()
    assert overview_body["resources_total"] == 2
    assert overview_body["tasks_total"] == 2
    assert overview_body["alerts_total"] == 1
    assert overview_body["events_total"] >= 1

    resources_layer = map_client.get("/api/map/layers/resources", headers=_auth_header(token_a))
    assert resources_layer.status_code == 200
    resource_items = resources_layer.json()["items"]
    resource_ids = {item["id"] for item in resource_items}
    assert drone_a in resource_ids
    assert asset_a in resource_ids
    assert drone_b not in resource_ids

    tasks_layer = map_client.get("/api/map/layers/tasks", headers=_auth_header(token_a))
    assert tasks_layer.status_code == 200
    task_ids = {item["id"] for item in tasks_layer.json()["items"]}
    assert mission_a in task_ids
    assert incident_a in task_ids
    assert mission_b not in task_ids
    assert incident_b not in task_ids

    alerts_layer = map_client.get("/api/map/layers/alerts", headers=_auth_header(token_a))
    assert alerts_layer.status_code == 200
    alert_items = alerts_layer.json()["items"]
    assert len(alert_items) == 1
    assert alert_items[0]["detail"]["drone_id"] == drone_a


def test_map_track_replay_supports_sampling_and_tenant_boundary(map_client: TestClient) -> None:
    tenant_a = _create_tenant(map_client, "map-replay-tenant-a")
    tenant_b = _create_tenant(map_client, "map-replay-tenant-b")
    _bootstrap_admin(map_client, tenant_a, "admin_a", "pass-a")
    _bootstrap_admin(map_client, tenant_b, "admin_b", "pass-b")
    token_a = _login(map_client, tenant_a, "admin_a", "pass-a")
    token_b = _login(map_client, tenant_b, "admin_b", "pass-b")

    drone_a = _create_drone(map_client, token_a, name="drone-replay-a")
    base = datetime.now(UTC)
    _ingest_telemetry(
        map_client,
        token_a,
        drone_id=drone_a,
        lat=30.0,
        lon=114.0,
        ts=base,
    )
    _ingest_telemetry(
        map_client,
        token_a,
        drone_id=drone_a,
        lat=30.1,
        lon=114.1,
        ts=base + timedelta(seconds=1),
    )
    _ingest_telemetry(
        map_client,
        token_a,
        drone_id=drone_a,
        lat=30.2,
        lon=114.2,
        ts=base + timedelta(seconds=2),
    )

    replay = map_client.get(
        f"/api/map/tracks/replay?drone_id={drone_a}&sample_step=2",
        headers=_auth_header(token_a),
    )
    assert replay.status_code == 200
    replay_body = replay.json()
    assert replay_body["drone_id"] == drone_a
    assert len(replay_body["points"]) == 2
    assert replay_body["points"][0]["lat"] == pytest.approx(30.0)
    assert replay_body["points"][1]["lat"] == pytest.approx(30.2)

    cross_tenant = map_client.get(
        f"/api/map/tracks/replay?drone_id={drone_a}",
        headers=_auth_header(token_b),
    )
    assert cross_tenant.status_code == 404

    unknown_drone = map_client.get(
        "/api/map/tracks/replay?drone_id=missing-drone",
        headers=_auth_header(token_a),
    )
    assert unknown_drone.status_code == 404
