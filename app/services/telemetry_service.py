from __future__ import annotations

from app.domain.models import TelemetryNormalized
from app.infra import redis_state
from app.infra.events import event_bus


class TelemetryError(Exception):
    pass


class NotFoundError(TelemetryError):
    pass


class TelemetryService:
    @staticmethod
    def _state_key(tenant_id: str, drone_id: str) -> str:
        return f"state:{tenant_id}:{drone_id}"

    def ingest(self, tenant_id: str, payload: TelemetryNormalized) -> TelemetryNormalized:
        normalized = payload.model_copy(update={"tenant_id": tenant_id})
        redis = redis_state.get_redis()
        key = self._state_key(tenant_id, normalized.drone_id)
        redis.set(key, normalized.model_dump_json())
        event_bus.publish_dict(
            "telemetry.normalized",
            tenant_id,
            normalized.model_dump(mode="json"),
        )
        return normalized

    def get_latest(self, tenant_id: str, drone_id: str) -> TelemetryNormalized:
        redis = redis_state.get_redis()
        key = self._state_key(tenant_id, drone_id)
        raw = redis.get(key)
        if raw is None:
            raise NotFoundError("telemetry not found")
        if isinstance(raw, bytes):
            raw = raw.decode()
        if not isinstance(raw, str):
            raise NotFoundError("telemetry payload invalid")
        return TelemetryNormalized.model_validate_json(raw)
