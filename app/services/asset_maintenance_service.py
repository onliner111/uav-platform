from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlmodel import Session, select

from app.domain.models import (
    Asset,
    AssetLifecycleStatus,
    AssetMaintenanceHistory,
    AssetMaintenanceWorkOrder,
    MaintenanceWorkOrderCloseRequest,
    MaintenanceWorkOrderCreate,
    MaintenanceWorkOrderStatus,
    MaintenanceWorkOrderTransitionRequest,
)
from app.infra.db import get_engine
from app.infra.events import event_bus


class AssetMaintenanceError(Exception):
    pass


class NotFoundError(AssetMaintenanceError):
    pass


class ConflictError(AssetMaintenanceError):
    pass


class AssetMaintenanceService:
    def _session(self) -> Session:
        return Session(get_engine(), expire_on_commit=False)

    def _get_scoped_asset(self, session: Session, tenant_id: str, asset_id: str) -> Asset:
        asset = session.exec(select(Asset).where(Asset.tenant_id == tenant_id).where(Asset.id == asset_id)).first()
        if asset is None:
            raise NotFoundError("asset not found")
        return asset

    def _get_scoped_workorder(
        self,
        session: Session,
        tenant_id: str,
        workorder_id: str,
    ) -> AssetMaintenanceWorkOrder:
        workorder = session.exec(
            select(AssetMaintenanceWorkOrder)
            .where(AssetMaintenanceWorkOrder.tenant_id == tenant_id)
            .where(AssetMaintenanceWorkOrder.id == workorder_id)
        ).first()
        if workorder is None:
            raise NotFoundError("maintenance workorder not found")
        return workorder

    def _append_history(
        self,
        session: Session,
        *,
        tenant_id: str,
        workorder_id: str,
        action: str,
        actor_id: str | None,
        from_status: MaintenanceWorkOrderStatus | None,
        to_status: MaintenanceWorkOrderStatus | None,
        note: str | None,
        detail: dict[str, Any] | None = None,
    ) -> None:
        history = AssetMaintenanceHistory(
            tenant_id=tenant_id,
            workorder_id=workorder_id,
            action=action,
            actor_id=actor_id,
            from_status=from_status,
            to_status=to_status,
            note=note,
            detail=detail or {},
        )
        session.add(history)

    def create_workorder(
        self,
        tenant_id: str,
        actor_id: str,
        payload: MaintenanceWorkOrderCreate,
    ) -> AssetMaintenanceWorkOrder:
        with self._session() as session:
            asset = self._get_scoped_asset(session, tenant_id, payload.asset_id)
            if asset.lifecycle_status == AssetLifecycleStatus.RETIRED:
                raise ConflictError("cannot create maintenance workorder for retired asset")
            workorder = AssetMaintenanceWorkOrder(
                tenant_id=tenant_id,
                asset_id=payload.asset_id,
                title=payload.title,
                description=payload.description,
                priority=payload.priority,
                status=MaintenanceWorkOrderStatus.OPEN,
                created_by=actor_id,
                assigned_to=payload.assigned_to,
            )
            session.add(workorder)
            session.flush()
            self._append_history(
                session,
                tenant_id=tenant_id,
                workorder_id=workorder.id,
                action="created",
                actor_id=actor_id,
                from_status=None,
                to_status=MaintenanceWorkOrderStatus.OPEN,
                note=payload.note,
            )
            session.commit()
            session.refresh(workorder)

        event_bus.publish_dict(
            "asset.maintenance_workorder.created",
            tenant_id,
            {
                "workorder_id": workorder.id,
                "asset_id": workorder.asset_id,
                "status": workorder.status,
            },
        )
        return workorder

    def list_workorders(
        self,
        tenant_id: str,
        *,
        asset_id: str | None = None,
        status: MaintenanceWorkOrderStatus | None = None,
    ) -> list[AssetMaintenanceWorkOrder]:
        with self._session() as session:
            statement = select(AssetMaintenanceWorkOrder).where(AssetMaintenanceWorkOrder.tenant_id == tenant_id)
            if asset_id is not None:
                statement = statement.where(AssetMaintenanceWorkOrder.asset_id == asset_id)
            if status is not None:
                statement = statement.where(AssetMaintenanceWorkOrder.status == status)
            return list(session.exec(statement).all())

    def get_workorder(self, tenant_id: str, workorder_id: str) -> AssetMaintenanceWorkOrder:
        with self._session() as session:
            return self._get_scoped_workorder(session, tenant_id, workorder_id)

    def transition_workorder(
        self,
        tenant_id: str,
        workorder_id: str,
        actor_id: str,
        payload: MaintenanceWorkOrderTransitionRequest,
    ) -> AssetMaintenanceWorkOrder:
        with self._session() as session:
            workorder = self._get_scoped_workorder(session, tenant_id, workorder_id)
            previous_status = workorder.status
            if workorder.status in {MaintenanceWorkOrderStatus.CLOSED, MaintenanceWorkOrderStatus.CANCELED}:
                raise ConflictError("closed/canceled workorder cannot transition")
            if payload.status == MaintenanceWorkOrderStatus.CLOSED:
                raise ConflictError("use close endpoint to close workorder")
            if payload.status == workorder.status and payload.assigned_to is None:
                raise ConflictError("workorder already in requested status")
            workorder.status = payload.status
            if payload.assigned_to is not None:
                workorder.assigned_to = payload.assigned_to
            workorder.updated_at = datetime.now(UTC)
            session.add(workorder)
            self._append_history(
                session,
                tenant_id=tenant_id,
                workorder_id=workorder.id,
                action="status_changed",
                actor_id=actor_id,
                from_status=previous_status,
                to_status=workorder.status,
                note=payload.note,
                detail={"assigned_to": workorder.assigned_to},
            )
            session.commit()
            session.refresh(workorder)

        event_bus.publish_dict(
            "asset.maintenance_workorder.status_changed",
            tenant_id,
            {
                "workorder_id": workorder.id,
                "asset_id": workorder.asset_id,
                "from_status": previous_status,
                "to_status": workorder.status,
            },
        )
        return workorder

    def close_workorder(
        self,
        tenant_id: str,
        workorder_id: str,
        actor_id: str,
        payload: MaintenanceWorkOrderCloseRequest,
    ) -> AssetMaintenanceWorkOrder:
        with self._session() as session:
            workorder = self._get_scoped_workorder(session, tenant_id, workorder_id)
            previous_status = workorder.status
            if workorder.status == MaintenanceWorkOrderStatus.CLOSED:
                raise ConflictError("workorder already closed")
            if workorder.status == MaintenanceWorkOrderStatus.CANCELED:
                raise ConflictError("canceled workorder cannot be closed")
            workorder.status = MaintenanceWorkOrderStatus.CLOSED
            workorder.close_note = payload.note
            workorder.closed_at = datetime.now(UTC)
            workorder.closed_by = actor_id
            workorder.updated_at = datetime.now(UTC)
            session.add(workorder)
            self._append_history(
                session,
                tenant_id=tenant_id,
                workorder_id=workorder.id,
                action="closed",
                actor_id=actor_id,
                from_status=previous_status,
                to_status=MaintenanceWorkOrderStatus.CLOSED,
                note=payload.note,
            )
            session.commit()
            session.refresh(workorder)

        event_bus.publish_dict(
            "asset.maintenance_workorder.closed",
            tenant_id,
            {
                "workorder_id": workorder.id,
                "asset_id": workorder.asset_id,
                "status": workorder.status,
            },
        )
        return workorder

    def list_history(self, tenant_id: str, workorder_id: str) -> list[AssetMaintenanceHistory]:
        with self._session() as session:
            self._get_scoped_workorder(session, tenant_id, workorder_id)
            statement = (
                select(AssetMaintenanceHistory)
                .where(AssetMaintenanceHistory.tenant_id == tenant_id)
                .where(AssetMaintenanceHistory.workorder_id == workorder_id)
            )
            rows = list(session.exec(statement).all())
        rows.sort(key=lambda item: item.created_at)
        return rows
