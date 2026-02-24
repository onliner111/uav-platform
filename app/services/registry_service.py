from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.domain.models import Drone, DroneCreate, DroneUpdate, Tenant
from app.infra.db import get_engine
from app.infra.events import event_bus


class RegistryError(Exception):
    pass


class NotFoundError(RegistryError):
    pass


class ConflictError(RegistryError):
    pass


class RegistryService:
    def _session(self) -> Session:
        return Session(get_engine(), expire_on_commit=False)

    def _get_scoped_drone(self, session: Session, tenant_id: str, drone_id: str) -> Drone:
        drone = session.exec(
            select(Drone).where(Drone.tenant_id == tenant_id).where(Drone.id == drone_id)
        ).first()
        if drone is None:
            raise NotFoundError("drone not found")
        return drone

    def create_drone(self, tenant_id: str, payload: DroneCreate) -> Drone:
        with self._session() as session:
            if session.get(Tenant, tenant_id) is None:
                raise NotFoundError("tenant not found")
            drone = Drone(
                tenant_id=tenant_id,
                name=payload.name,
                vendor=payload.vendor,
                capabilities=payload.capabilities,
            )
            session.add(drone)
            try:
                session.commit()
            except IntegrityError as exc:
                session.rollback()
                raise ConflictError("drone name already exists in tenant") from exc
            session.refresh(drone)

        event_bus.publish_dict(
            "drone.registered",
            tenant_id,
            {
                "drone_id": drone.id,
                "name": drone.name,
                "vendor": drone.vendor,
                "capabilities": drone.capabilities,
            },
        )
        return drone

    def list_drones(self, tenant_id: str) -> list[Drone]:
        with self._session() as session:
            statement = select(Drone).where(Drone.tenant_id == tenant_id)
            return list(session.exec(statement).all())

    def get_drone(self, tenant_id: str, drone_id: str) -> Drone:
        with self._session() as session:
            drone = self._get_scoped_drone(session, tenant_id, drone_id)
            return drone

    def update_drone(self, tenant_id: str, drone_id: str, payload: DroneUpdate) -> Drone:
        with self._session() as session:
            drone = self._get_scoped_drone(session, tenant_id, drone_id)
            if payload.name is not None:
                drone.name = payload.name
            if payload.vendor is not None:
                drone.vendor = payload.vendor
            if payload.capabilities is not None:
                drone.capabilities = payload.capabilities
            drone.updated_at = datetime.now(UTC)
            session.add(drone)
            try:
                session.commit()
            except IntegrityError as exc:
                session.rollback()
                raise ConflictError("drone name already exists in tenant") from exc
            session.refresh(drone)

        event_bus.publish_dict(
            "drone.updated",
            tenant_id,
            {
                "drone_id": drone.id,
                "name": drone.name,
                "vendor": drone.vendor,
                "capabilities": drone.capabilities,
            },
        )
        return drone

    def delete_drone(self, tenant_id: str, drone_id: str) -> None:
        with self._session() as session:
            drone = self._get_scoped_drone(session, tenant_id, drone_id)
            session.delete(drone)
            session.commit()

