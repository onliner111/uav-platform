from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlmodel import Session, select

from app.domain.models import (
    InspectionObservation,
    InspectionTask,
    Mission,
    OutcomeCatalogCreate,
    OutcomeCatalogRecord,
    OutcomeCatalogStatusUpdateRequest,
    OutcomeSourceType,
    OutcomeStatus,
    OutcomeType,
    RawDataCatalogCreate,
    RawDataCatalogRecord,
    RawDataType,
)
from app.infra.db import get_engine
from app.infra.events import event_bus
from app.services.data_perimeter_service import DataPerimeterService


class OutcomeError(Exception):
    pass


class NotFoundError(OutcomeError):
    pass


class ConflictError(OutcomeError):
    pass


class OutcomeService:
    def __init__(self) -> None:
        self._data_perimeter = DataPerimeterService()

    def _session(self) -> Session:
        return Session(get_engine(), expire_on_commit=False)

    def _get_scoped_task(self, session: Session, tenant_id: str, task_id: str) -> InspectionTask:
        task = session.exec(
            select(InspectionTask)
            .where(InspectionTask.tenant_id == tenant_id)
            .where(InspectionTask.id == task_id)
        ).first()
        if task is None:
            raise NotFoundError("inspection task not found")
        return task

    def _get_scoped_mission(self, session: Session, tenant_id: str, mission_id: str) -> Mission:
        mission = session.exec(
            select(Mission)
            .where(Mission.tenant_id == tenant_id)
            .where(Mission.id == mission_id)
        ).first()
        if mission is None:
            raise NotFoundError("mission not found")
        return mission

    def _get_scoped_observation(
        self,
        session: Session,
        tenant_id: str,
        observation_id: str,
    ) -> InspectionObservation:
        row = session.exec(
            select(InspectionObservation)
            .where(InspectionObservation.tenant_id == tenant_id)
            .where(InspectionObservation.id == observation_id)
        ).first()
        if row is None:
            raise NotFoundError("observation not found")
        return row

    def _get_scoped_outcome(self, session: Session, tenant_id: str, outcome_id: str) -> OutcomeCatalogRecord:
        row = session.exec(
            select(OutcomeCatalogRecord)
            .where(OutcomeCatalogRecord.tenant_id == tenant_id)
            .where(OutcomeCatalogRecord.id == outcome_id)
        ).first()
        if row is None:
            raise NotFoundError("outcome record not found")
        return row

    def _is_visible(
        self,
        session: Session,
        tenant_id: str,
        viewer_user_id: str | None,
        *,
        task_id: str | None,
        mission_id: str | None,
    ) -> bool:
        if viewer_user_id is None:
            return True
        scope = self._data_perimeter.resolve_scope(session, tenant_id, viewer_user_id)
        if task_id is not None:
            task = self._get_scoped_task(session, tenant_id, task_id)
            return self._data_perimeter.inspection_task_visible(task, scope)
        if mission_id is not None:
            mission = self._get_scoped_mission(session, tenant_id, mission_id)
            return self._data_perimeter.mission_visible(mission, scope)
        return True

    def create_raw_record(self, tenant_id: str, actor_id: str, payload: RawDataCatalogCreate) -> RawDataCatalogRecord:
        with self._session() as session:
            if payload.task_id is not None:
                _ = self._get_scoped_task(session, tenant_id, payload.task_id)
            if payload.mission_id is not None:
                _ = self._get_scoped_mission(session, tenant_id, payload.mission_id)
            row = RawDataCatalogRecord(
                tenant_id=tenant_id,
                task_id=payload.task_id,
                mission_id=payload.mission_id,
                data_type=payload.data_type,
                source_uri=payload.source_uri,
                checksum=payload.checksum,
                meta=payload.meta,
                captured_at=payload.captured_at,
                created_by=actor_id,
            )
            session.add(row)
            session.commit()
            session.refresh(row)

        event_bus.publish_dict(
            "outcome.raw.created",
            tenant_id,
            {"raw_id": row.id, "task_id": row.task_id, "mission_id": row.mission_id, "data_type": row.data_type},
        )
        return row

    def list_raw_records(
        self,
        tenant_id: str,
        *,
        task_id: str | None = None,
        mission_id: str | None = None,
        data_type: RawDataType | None = None,
        from_ts: datetime | None = None,
        to_ts: datetime | None = None,
        viewer_user_id: str | None = None,
    ) -> list[RawDataCatalogRecord]:
        with self._session() as session:
            statement = select(RawDataCatalogRecord).where(RawDataCatalogRecord.tenant_id == tenant_id)
            if task_id is not None:
                statement = statement.where(RawDataCatalogRecord.task_id == task_id)
            if mission_id is not None:
                statement = statement.where(RawDataCatalogRecord.mission_id == mission_id)
            if data_type is not None:
                statement = statement.where(RawDataCatalogRecord.data_type == data_type)
            if from_ts is not None:
                statement = statement.where(RawDataCatalogRecord.captured_at >= from_ts)
            if to_ts is not None:
                statement = statement.where(RawDataCatalogRecord.captured_at <= to_ts)
            rows = list(session.exec(statement).all())
            return [
                item
                for item in rows
                if self._is_visible(
                    session,
                    tenant_id,
                    viewer_user_id,
                    task_id=item.task_id,
                    mission_id=item.mission_id,
                )
            ]

    def create_outcome_record(
        self,
        tenant_id: str,
        actor_id: str,
        payload: OutcomeCatalogCreate,
    ) -> OutcomeCatalogRecord:
        with self._session() as session:
            if payload.task_id is not None:
                _ = self._get_scoped_task(session, tenant_id, payload.task_id)
            if payload.mission_id is not None:
                _ = self._get_scoped_mission(session, tenant_id, payload.mission_id)
            if payload.source_type == OutcomeSourceType.INSPECTION_OBSERVATION:
                _ = self._get_scoped_observation(session, tenant_id, payload.source_id)

            row = OutcomeCatalogRecord(
                tenant_id=tenant_id,
                task_id=payload.task_id,
                mission_id=payload.mission_id,
                source_type=payload.source_type,
                source_id=payload.source_id,
                outcome_type=payload.outcome_type,
                status=payload.status,
                point_lat=payload.point_lat,
                point_lon=payload.point_lon,
                alt_m=payload.alt_m,
                confidence=payload.confidence,
                payload=payload.payload,
                created_by=actor_id,
            )
            session.add(row)
            session.commit()
            session.refresh(row)

        event_bus.publish_dict(
            "outcome.record.created",
            tenant_id,
            {
                "outcome_id": row.id,
                "task_id": row.task_id,
                "mission_id": row.mission_id,
                "source_type": row.source_type,
                "source_id": row.source_id,
                "status": row.status,
            },
        )
        return row

    def materialize_outcome_from_observation(
        self,
        tenant_id: str,
        actor_id: str,
        observation_id: str,
    ) -> OutcomeCatalogRecord:
        with self._session() as session:
            observation = self._get_scoped_observation(session, tenant_id, observation_id)
            existing = session.exec(
                select(OutcomeCatalogRecord)
                .where(OutcomeCatalogRecord.tenant_id == tenant_id)
                .where(OutcomeCatalogRecord.source_type == OutcomeSourceType.INSPECTION_OBSERVATION)
                .where(OutcomeCatalogRecord.source_id == observation_id)
            ).first()
            if existing is not None:
                return existing

            row = OutcomeCatalogRecord(
                tenant_id=tenant_id,
                task_id=observation.task_id,
                mission_id=None,
                source_type=OutcomeSourceType.INSPECTION_OBSERVATION,
                source_id=observation.id,
                outcome_type=OutcomeType.OTHER,
                status=OutcomeStatus.NEW,
                point_lat=observation.position_lat,
                point_lon=observation.position_lon,
                alt_m=observation.alt_m,
                confidence=observation.confidence,
                payload={
                    "item_code": observation.item_code,
                    "severity": observation.severity,
                    "note": observation.note,
                    "media_url": observation.media_url,
                    "ts": observation.ts.isoformat(),
                },
                created_by=actor_id,
            )
            session.add(row)
            session.commit()
            session.refresh(row)

        event_bus.publish_dict(
            "outcome.record.materialized",
            tenant_id,
            {"outcome_id": row.id, "source_type": row.source_type, "source_id": row.source_id},
        )
        return row

    def list_outcome_records(
        self,
        tenant_id: str,
        *,
        task_id: str | None = None,
        mission_id: str | None = None,
        source_type: OutcomeSourceType | None = None,
        outcome_type: OutcomeType | None = None,
        status: OutcomeStatus | None = None,
        from_ts: datetime | None = None,
        to_ts: datetime | None = None,
        viewer_user_id: str | None = None,
    ) -> list[OutcomeCatalogRecord]:
        with self._session() as session:
            statement = select(OutcomeCatalogRecord).where(OutcomeCatalogRecord.tenant_id == tenant_id)
            if task_id is not None:
                statement = statement.where(OutcomeCatalogRecord.task_id == task_id)
            if mission_id is not None:
                statement = statement.where(OutcomeCatalogRecord.mission_id == mission_id)
            if source_type is not None:
                statement = statement.where(OutcomeCatalogRecord.source_type == source_type)
            if outcome_type is not None:
                statement = statement.where(OutcomeCatalogRecord.outcome_type == outcome_type)
            if status is not None:
                statement = statement.where(OutcomeCatalogRecord.status == status)
            if from_ts is not None:
                statement = statement.where(OutcomeCatalogRecord.created_at >= from_ts)
            if to_ts is not None:
                statement = statement.where(OutcomeCatalogRecord.created_at <= to_ts)
            rows = list(session.exec(statement).all())
            return [
                item
                for item in rows
                if self._is_visible(
                    session,
                    tenant_id,
                    viewer_user_id,
                    task_id=item.task_id,
                    mission_id=item.mission_id,
                )
            ]

    def update_outcome_status(
        self,
        tenant_id: str,
        outcome_id: str,
        actor_id: str,
        payload: OutcomeCatalogStatusUpdateRequest,
    ) -> OutcomeCatalogRecord:
        with self._session() as session:
            row = self._get_scoped_outcome(session, tenant_id, outcome_id)
            row.status = payload.status
            row.reviewed_by = actor_id
            row.reviewed_at = datetime.now(UTC)
            row.updated_at = datetime.now(UTC)
            if payload.note:
                detail: dict[str, Any] = dict(row.payload)
                detail["status_note"] = payload.note
                row.payload = detail
            session.add(row)
            session.commit()
            session.refresh(row)

        event_bus.publish_dict(
            "outcome.record.status_changed",
            tenant_id,
            {"outcome_id": row.id, "status": row.status, "reviewed_by": row.reviewed_by},
        )
        return row
