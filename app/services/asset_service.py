from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.domain.models import (
    Asset,
    AssetAvailabilityStatus,
    AssetAvailabilityUpdateRequest,
    AssetBindRequest,
    AssetCreate,
    AssetHealthStatus,
    AssetHealthUpdateRequest,
    AssetLifecycleStatus,
    AssetRetireRequest,
    AssetType,
    Drone,
    Tenant,
)
from app.infra.db import get_engine
from app.infra.events import event_bus
from app.services.data_perimeter_service import DataPerimeterService


class AssetError(Exception):
    pass


class NotFoundError(AssetError):
    pass


class ConflictError(AssetError):
    pass


class AssetService:
    def __init__(self) -> None:
        self._data_perimeter = DataPerimeterService()

    def _session(self) -> Session:
        return Session(get_engine(), expire_on_commit=False)

    def _get_scoped_asset(self, session: Session, tenant_id: str, asset_id: str) -> Asset:
        asset = session.exec(select(Asset).where(Asset.tenant_id == tenant_id).where(Asset.id == asset_id)).first()
        if asset is None:
            raise NotFoundError("asset not found")
        return asset

    def _ensure_scoped_drone(self, session: Session, tenant_id: str, drone_id: str) -> None:
        drone = session.exec(select(Drone).where(Drone.tenant_id == tenant_id).where(Drone.id == drone_id)).first()
        if drone is None:
            raise NotFoundError("drone not found")

    def _ensure_asset_visible(
        self,
        session: Session,
        tenant_id: str,
        viewer_user_id: str | None,
        asset: Asset,
    ) -> None:
        if viewer_user_id is None:
            return
        scope = self._data_perimeter.resolve_scope(session, tenant_id, viewer_user_id)
        if not self._data_perimeter.asset_visible(asset, scope):
            raise NotFoundError("asset not found")

    def create_asset(self, tenant_id: str, payload: AssetCreate) -> Asset:
        with self._session() as session:
            if session.get(Tenant, tenant_id) is None:
                raise NotFoundError("tenant not found")
            asset = Asset(
                tenant_id=tenant_id,
                asset_type=payload.asset_type,
                asset_code=payload.asset_code,
                name=payload.name,
                serial_number=payload.serial_number,
                detail=payload.detail,
                lifecycle_status=AssetLifecycleStatus.REGISTERED,
            )
            session.add(asset)
            try:
                session.commit()
            except IntegrityError as exc:
                session.rollback()
                raise ConflictError("asset code already exists in tenant/type") from exc
            session.refresh(asset)

        event_bus.publish_dict(
            "asset.registered",
            tenant_id,
            {
                "asset_id": asset.id,
                "asset_type": asset.asset_type,
                "asset_code": asset.asset_code,
                "lifecycle_status": asset.lifecycle_status,
            },
        )
        return asset

    def list_assets(
        self,
        tenant_id: str,
        *,
        asset_type: AssetType | None = None,
        lifecycle_status: AssetLifecycleStatus | None = None,
        availability_status: AssetAvailabilityStatus | None = None,
        health_status: AssetHealthStatus | None = None,
        region_code: str | None = None,
        viewer_user_id: str | None = None,
    ) -> list[Asset]:
        with self._session() as session:
            statement = select(Asset).where(Asset.tenant_id == tenant_id)
            if asset_type is not None:
                statement = statement.where(Asset.asset_type == asset_type)
            if lifecycle_status is not None:
                statement = statement.where(Asset.lifecycle_status == lifecycle_status)
            if availability_status is not None:
                statement = statement.where(Asset.availability_status == availability_status)
            if health_status is not None:
                statement = statement.where(Asset.health_status == health_status)
            if region_code is not None:
                statement = statement.where(Asset.region_code == region_code)
            rows = list(session.exec(statement).all())
            if viewer_user_id is None:
                return rows
            scope = self._data_perimeter.resolve_scope(session, tenant_id, viewer_user_id)
            return [item for item in rows if self._data_perimeter.asset_visible(item, scope)]

    def list_resource_pool(
        self,
        tenant_id: str,
        *,
        asset_type: AssetType | None = None,
        availability_status: AssetAvailabilityStatus = AssetAvailabilityStatus.AVAILABLE,
        health_status: AssetHealthStatus | None = None,
        region_code: str | None = None,
        min_health_score: int | None = None,
        viewer_user_id: str | None = None,
    ) -> list[Asset]:
        with self._session() as session:
            statement = select(Asset).where(Asset.tenant_id == tenant_id)
            statement = statement.where(Asset.lifecycle_status != AssetLifecycleStatus.RETIRED)
            statement = statement.where(Asset.availability_status == availability_status)
            if asset_type is not None:
                statement = statement.where(Asset.asset_type == asset_type)
            if health_status is not None:
                statement = statement.where(Asset.health_status == health_status)
            if region_code is not None:
                statement = statement.where(Asset.region_code == region_code)
            rows = list(session.exec(statement).all())
            if viewer_user_id is not None:
                scope = self._data_perimeter.resolve_scope(session, tenant_id, viewer_user_id)
                rows = [item for item in rows if self._data_perimeter.asset_visible(item, scope)]
            if min_health_score is not None:
                rows = [
                    item
                    for item in rows
                    if item.health_score is not None and item.health_score >= min_health_score
                ]
            return rows

    def summarize_resource_pool(
        self,
        tenant_id: str,
        *,
        asset_type: AssetType | None = None,
        health_status: AssetHealthStatus | None = None,
        region_code: str | None = None,
        min_health_score: int | None = None,
        viewer_user_id: str | None = None,
    ) -> list[dict[str, Any]]:
        assets = self.list_resource_pool(
            tenant_id,
            asset_type=asset_type,
            availability_status=AssetAvailabilityStatus.AVAILABLE,
            health_status=health_status,
            region_code=region_code,
            min_health_score=min_health_score,
            viewer_user_id=viewer_user_id,
        )
        grouped: dict[str, dict[str, Any]] = {}
        for asset in assets:
            region_key = asset.region_code or "UNASSIGNED"
            bucket = grouped.setdefault(
                region_key,
                {
                    "region_code": region_key,
                    "total_assets": 0,
                    "available_assets": 0,
                    "by_type": {},
                    "by_availability": {},
                    "healthy_assets": 0,
                    "_health_score_total": 0.0,
                    "_health_score_count": 0,
                },
            )
            bucket["total_assets"] += 1
            if asset.availability_status == AssetAvailabilityStatus.AVAILABLE:
                bucket["available_assets"] += 1
            type_key = asset.asset_type.value
            status_key = asset.availability_status.value
            bucket["by_type"][type_key] = int(bucket["by_type"].get(type_key, 0)) + 1
            bucket["by_availability"][status_key] = int(bucket["by_availability"].get(status_key, 0)) + 1
            if asset.health_status == AssetHealthStatus.HEALTHY:
                bucket["healthy_assets"] += 1
            if asset.health_score is not None:
                bucket["_health_score_total"] += float(asset.health_score)
                bucket["_health_score_count"] += 1
        result: list[dict[str, Any]] = []
        for region_key in sorted(grouped.keys()):
            bucket = grouped[region_key]
            avg_health: float | None = None
            if bucket["_health_score_count"] > 0:
                avg_health = round(bucket["_health_score_total"] / bucket["_health_score_count"], 2)
            result.append(
                {
                    "region_code": bucket["region_code"],
                    "total_assets": bucket["total_assets"],
                    "available_assets": bucket["available_assets"],
                    "by_type": bucket["by_type"],
                    "by_availability": bucket["by_availability"],
                    "healthy_assets": bucket["healthy_assets"],
                    "average_health_score": avg_health,
                }
            )
        return result

    def get_asset(self, tenant_id: str, asset_id: str, viewer_user_id: str | None = None) -> Asset:
        with self._session() as session:
            asset = self._get_scoped_asset(session, tenant_id, asset_id)
            self._ensure_asset_visible(session, tenant_id, viewer_user_id, asset)
            return asset

    def bind_asset(
        self,
        tenant_id: str,
        asset_id: str,
        payload: AssetBindRequest,
        viewer_user_id: str | None = None,
    ) -> Asset:
        with self._session() as session:
            asset = self._get_scoped_asset(session, tenant_id, asset_id)
            self._ensure_asset_visible(session, tenant_id, viewer_user_id, asset)
            if asset.lifecycle_status == AssetLifecycleStatus.RETIRED:
                raise ConflictError("retired asset cannot be bound")
            self._ensure_scoped_drone(session, tenant_id, payload.bound_to_drone_id)
            asset.bound_to_drone_id = payload.bound_to_drone_id
            asset.lifecycle_status = AssetLifecycleStatus.BOUND
            asset.bound_at = datetime.now(UTC)
            asset.updated_at = datetime.now(UTC)
            session.add(asset)
            session.commit()
            session.refresh(asset)

        event_bus.publish_dict(
            "asset.bound",
            tenant_id,
            {
                "asset_id": asset.id,
                "asset_type": asset.asset_type,
                "bound_to_drone_id": asset.bound_to_drone_id,
                "lifecycle_status": asset.lifecycle_status,
            },
        )
        return asset

    def retire_asset(
        self,
        tenant_id: str,
        asset_id: str,
        payload: AssetRetireRequest,
        viewer_user_id: str | None = None,
    ) -> Asset:
        with self._session() as session:
            asset = self._get_scoped_asset(session, tenant_id, asset_id)
            self._ensure_asset_visible(session, tenant_id, viewer_user_id, asset)
            asset.lifecycle_status = AssetLifecycleStatus.RETIRED
            asset.retired_reason = payload.reason
            asset.retired_at = datetime.now(UTC)
            asset.bound_to_drone_id = None
            asset.updated_at = datetime.now(UTC)
            session.add(asset)
            session.commit()
            session.refresh(asset)

        event_bus.publish_dict(
            "asset.retired",
            tenant_id,
            {
                "asset_id": asset.id,
                "asset_type": asset.asset_type,
                "retired_reason": asset.retired_reason,
                "lifecycle_status": asset.lifecycle_status,
            },
        )
        return asset

    def update_availability(
        self,
        tenant_id: str,
        asset_id: str,
        payload: AssetAvailabilityUpdateRequest,
        viewer_user_id: str | None = None,
    ) -> Asset:
        with self._session() as session:
            asset = self._get_scoped_asset(session, tenant_id, asset_id)
            self._ensure_asset_visible(session, tenant_id, viewer_user_id, asset)
            if asset.lifecycle_status == AssetLifecycleStatus.RETIRED:
                raise ConflictError("retired asset cannot update availability")
            asset.availability_status = payload.availability_status
            asset.region_code = payload.region_code
            asset.updated_at = datetime.now(UTC)
            session.add(asset)
            session.commit()
            session.refresh(asset)

        event_bus.publish_dict(
            "asset.availability_updated",
            tenant_id,
            {
                "asset_id": asset.id,
                "availability_status": asset.availability_status,
                "region_code": asset.region_code,
            },
        )
        return asset

    def update_health(
        self,
        tenant_id: str,
        asset_id: str,
        payload: AssetHealthUpdateRequest,
        viewer_user_id: str | None = None,
    ) -> Asset:
        with self._session() as session:
            asset = self._get_scoped_asset(session, tenant_id, asset_id)
            self._ensure_asset_visible(session, tenant_id, viewer_user_id, asset)
            if asset.lifecycle_status == AssetLifecycleStatus.RETIRED:
                raise ConflictError("retired asset cannot update health")
            asset.health_status = payload.health_status
            asset.health_score = payload.health_score
            if payload.detail:
                merged_detail = dict(asset.detail)
                merged_detail.update(payload.detail)
                asset.detail = merged_detail
            asset.last_health_at = datetime.now(UTC)
            asset.updated_at = datetime.now(UTC)
            session.add(asset)
            session.commit()
            session.refresh(asset)

        event_bus.publish_dict(
            "asset.health_updated",
            tenant_id,
            {
                "asset_id": asset.id,
                "health_status": asset.health_status,
                "health_score": asset.health_score,
            },
        )
        return asset
