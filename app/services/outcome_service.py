from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import uuid4

from sqlmodel import Session, col, select

from app.domain.models import (
    InspectionObservation,
    InspectionTask,
    Mission,
    OutcomeCatalogCreate,
    OutcomeCatalogRecord,
    OutcomeCatalogStatusUpdateRequest,
    OutcomeCatalogVersion,
    OutcomeSourceType,
    OutcomeStatus,
    OutcomeType,
    OutcomeVersionChangeType,
    RawDataAccessTier,
    RawDataCatalogCreate,
    RawDataCatalogRecord,
    RawDataStorageTransitionRequest,
    RawDataType,
    RawUploadInitRequest,
    RawUploadSession,
    RawUploadSessionStatus,
    now_utc,
)
from app.infra.db import get_engine
from app.infra.events import event_bus
from app.services.data_perimeter_service import DataPerimeterService
from app.services.object_storage_service import ObjectStorageNotFoundError, ObjectStorageService


class OutcomeError(Exception):
    pass


class NotFoundError(OutcomeError):
    pass


class ConflictError(OutcomeError):
    pass


class OutcomeService:
    def __init__(self) -> None:
        self._data_perimeter = DataPerimeterService()
        self._storage = ObjectStorageService()

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

    def _get_scoped_raw(self, session: Session, tenant_id: str, raw_id: str) -> RawDataCatalogRecord:
        row = session.exec(
            select(RawDataCatalogRecord)
            .where(RawDataCatalogRecord.tenant_id == tenant_id)
            .where(RawDataCatalogRecord.id == raw_id)
        ).first()
        if row is None:
            raise NotFoundError("raw data record not found")
        return row

    def _get_scoped_raw_upload_session(self, session: Session, tenant_id: str, session_id: str) -> RawUploadSession:
        row = session.exec(
            select(RawUploadSession)
            .where(RawUploadSession.tenant_id == tenant_id)
            .where(RawUploadSession.id == session_id)
        ).first()
        if row is None:
            raise NotFoundError("raw upload session not found")
        return row

    def _normalize_checksum(self, checksum: str | None) -> str | None:
        if checksum is None:
            return None
        value = checksum.strip().lower()
        if not value:
            return None
        if value.startswith("sha256:"):
            return value
        return f"sha256:{value}"

    def _resolve_access_tier(self, storage_class: str | None) -> RawDataAccessTier:
        if storage_class is None:
            return RawDataAccessTier.HOT
        normalized = storage_class.strip().upper()
        if normalized in {"ARCHIVE", "GLACIER", "DEEP_ARCHIVE"}:
            return RawDataAccessTier.COLD
        if normalized in {"STANDARD_IA", "INFREQUENT_ACCESS", "NEARLINE"}:
            return RawDataAccessTier.WARM
        return RawDataAccessTier.HOT

    def _is_expired(self, expires_at: datetime) -> bool:
        if expires_at.tzinfo is None:
            expires_at_utc = expires_at.replace(tzinfo=UTC)
        else:
            expires_at_utc = expires_at.astimezone(UTC)
        return expires_at_utc < now_utc()

    def _ensure_visible(
        self,
        session: Session,
        tenant_id: str,
        viewer_user_id: str | None,
        *,
        task_id: str | None,
        mission_id: str | None,
        not_found_detail: str,
    ) -> None:
        if self._is_visible(
            session,
            tenant_id,
            viewer_user_id,
            task_id=task_id,
            mission_id=mission_id,
        ):
            return
        raise NotFoundError(not_found_detail)

    def _next_outcome_version_no(self, session: Session, tenant_id: str, outcome_id: str) -> int:
        latest = session.exec(
            select(OutcomeCatalogVersion.version_no)
            .where(OutcomeCatalogVersion.tenant_id == tenant_id)
            .where(OutcomeCatalogVersion.outcome_id == outcome_id)
            .order_by(col(OutcomeCatalogVersion.version_no).desc())
        ).first()
        if latest is None:
            return 1
        return int(latest) + 1

    def _append_outcome_version(
        self,
        session: Session,
        row: OutcomeCatalogRecord,
        *,
        actor_id: str,
        change_type: OutcomeVersionChangeType,
        change_note: str | None = None,
    ) -> OutcomeCatalogVersion:
        version = OutcomeCatalogVersion(
            tenant_id=row.tenant_id,
            outcome_id=row.id,
            version_no=self._next_outcome_version_no(session, row.tenant_id, row.id),
            outcome_type=row.outcome_type,
            status=row.status,
            point_lat=row.point_lat,
            point_lon=row.point_lon,
            alt_m=row.alt_m,
            confidence=row.confidence,
            payload=row.payload,
            change_type=change_type,
            change_note=change_note,
            created_by=actor_id,
            created_at=now_utc(),
        )
        session.add(version)
        session.commit()
        session.refresh(version)
        return version

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
            self._ensure_visible(
                session,
                tenant_id,
                actor_id,
                task_id=payload.task_id,
                mission_id=payload.mission_id,
                not_found_detail="raw data record not found",
            )
            row = RawDataCatalogRecord(
                tenant_id=tenant_id,
                task_id=payload.task_id,
                mission_id=payload.mission_id,
                data_type=payload.data_type,
                source_uri=payload.source_uri,
                access_tier=RawDataAccessTier.HOT,
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

    def init_raw_upload_session(
        self,
        tenant_id: str,
        actor_id: str,
        payload: RawUploadInitRequest,
    ) -> dict[str, Any]:
        normalized_checksum = self._normalize_checksum(payload.checksum)
        with self._session() as session:
            if payload.task_id is not None:
                _ = self._get_scoped_task(session, tenant_id, payload.task_id)
            if payload.mission_id is not None:
                _ = self._get_scoped_mission(session, tenant_id, payload.mission_id)
            self._ensure_visible(
                session,
                tenant_id,
                actor_id,
                task_id=payload.task_id,
                mission_id=payload.mission_id,
                not_found_detail="raw upload session not found",
            )
            session_id = str(uuid4())
            upload_token = str(uuid4())
            object_key = self._storage.build_raw_object_key(
                tenant_id=tenant_id,
                session_id=session_id,
                file_name=payload.file_name,
            )
            row = RawUploadSession(
                id=session_id,
                tenant_id=tenant_id,
                task_id=payload.task_id,
                mission_id=payload.mission_id,
                data_type=payload.data_type,
                file_name=payload.file_name,
                content_type=payload.content_type,
                size_bytes=payload.size_bytes,
                checksum=normalized_checksum,
                meta=payload.meta,
                bucket=self._storage.default_bucket,
                object_key=object_key,
                storage_class=payload.storage_class,
                storage_region=payload.storage_region,
                status=RawUploadSessionStatus.INITIATED,
                upload_token=upload_token,
                expires_at=now_utc() + timedelta(seconds=self._storage.upload_url_ttl_seconds),
                created_by=actor_id,
                updated_at=now_utc(),
            )
            session.add(row)
            session.commit()
            session.refresh(row)

        event_bus.publish_dict(
            "outcome.raw.upload.initiated",
            tenant_id,
            {"session_id": row.id, "object_key": row.object_key, "size_bytes": row.size_bytes},
        )
        return {
            "session_id": row.id,
            "upload_token": row.upload_token,
            "upload_url": self._storage.build_upload_url(session_id=row.id),
            "bucket": row.bucket,
            "object_key": row.object_key,
            "expires_at": row.expires_at,
        }

    def write_raw_upload_content(
        self,
        tenant_id: str,
        session_id: str,
        upload_token: str,
        content: bytes,
        *,
        viewer_user_id: str | None,
    ) -> dict[str, Any]:
        with self._session() as session:
            row = self._get_scoped_raw_upload_session(session, tenant_id, session_id)
            self._ensure_visible(
                session,
                tenant_id,
                viewer_user_id,
                task_id=row.task_id,
                mission_id=row.mission_id,
                not_found_detail="raw upload session not found",
            )
            if row.upload_token != upload_token:
                raise ConflictError("invalid upload token")
            if row.status == RawUploadSessionStatus.COMPLETED:
                raise ConflictError("upload session already completed")
            if row.status == RawUploadSessionStatus.EXPIRED or self._is_expired(row.expires_at):
                row.status = RawUploadSessionStatus.EXPIRED
                row.updated_at = now_utc()
                session.add(row)
                session.commit()
                raise ConflictError("upload session expired")
            if row.size_bytes != len(content):
                raise ConflictError("uploaded content size mismatch")

            meta = self._storage.put_upload_content(
                bucket=row.bucket,
                object_key=row.object_key,
                content=content,
                content_type=row.content_type,
                storage_class=row.storage_class,
            )
            if row.checksum is not None and row.checksum != f"sha256:{meta.etag}":
                raise ConflictError("uploaded content checksum mismatch")

            row.etag = meta.etag
            row.status = RawUploadSessionStatus.UPLOADED
            row.updated_at = now_utc()
            session.add(row)
            session.commit()
            session.refresh(row)

        event_bus.publish_dict(
            "outcome.raw.uploaded",
            tenant_id,
            {"session_id": row.id, "etag": row.etag, "size_bytes": row.size_bytes},
        )
        return {"session_id": row.id, "status": row.status, "etag": row.etag}

    def complete_raw_upload_session(
        self,
        tenant_id: str,
        actor_id: str,
        session_id: str,
        upload_token: str,
    ) -> RawDataCatalogRecord:
        with self._session() as session:
            upload_row = self._get_scoped_raw_upload_session(session, tenant_id, session_id)
            self._ensure_visible(
                session,
                tenant_id,
                actor_id,
                task_id=upload_row.task_id,
                mission_id=upload_row.mission_id,
                not_found_detail="raw upload session not found",
            )
            if upload_row.upload_token != upload_token:
                raise ConflictError("invalid upload token")
            if upload_row.completed_raw_id is not None:
                return self._get_scoped_raw(session, tenant_id, upload_row.completed_raw_id)
            if upload_row.status == RawUploadSessionStatus.EXPIRED or self._is_expired(upload_row.expires_at):
                upload_row.status = RawUploadSessionStatus.EXPIRED
                upload_row.updated_at = now_utc()
                session.add(upload_row)
                session.commit()
                raise ConflictError("upload session expired")

            meta = self._storage.stat_upload_content(
                bucket=upload_row.bucket,
                object_key=upload_row.object_key,
                content_type=upload_row.content_type,
                storage_class=upload_row.storage_class,
            )
            if meta is None:
                raise ConflictError("uploaded object not found")
            if meta.size_bytes != upload_row.size_bytes:
                raise ConflictError("uploaded object size mismatch")
            if upload_row.checksum is not None and upload_row.checksum != f"sha256:{meta.etag}":
                raise ConflictError("uploaded object checksum mismatch")

            raw_row = RawDataCatalogRecord(
                tenant_id=tenant_id,
                task_id=upload_row.task_id,
                mission_id=upload_row.mission_id,
                data_type=upload_row.data_type,
                source_uri=f"storage://{upload_row.bucket}/{upload_row.object_key}",
                bucket=upload_row.bucket,
                object_key=upload_row.object_key,
                object_version=meta.object_version,
                size_bytes=meta.size_bytes,
                content_type=upload_row.content_type,
                storage_class=upload_row.storage_class,
                storage_region=upload_row.storage_region,
                access_tier=self._resolve_access_tier(upload_row.storage_class),
                etag=meta.etag,
                checksum=upload_row.checksum,
                meta=upload_row.meta,
                captured_at=now_utc(),
                created_by=actor_id,
            )
            session.add(raw_row)
            session.commit()
            session.refresh(raw_row)

            upload_row.status = RawUploadSessionStatus.COMPLETED
            upload_row.completed_raw_id = raw_row.id
            upload_row.etag = meta.etag
            upload_row.updated_at = now_utc()
            session.add(upload_row)
            session.commit()

        event_bus.publish_dict(
            "outcome.raw.upload.completed",
            tenant_id,
            {"session_id": session_id, "raw_id": raw_row.id, "object_key": raw_row.object_key},
        )
        event_bus.publish_dict(
            "outcome.raw.created",
            tenant_id,
            {
                "raw_id": raw_row.id,
                "task_id": raw_row.task_id,
                "mission_id": raw_row.mission_id,
                "data_type": raw_row.data_type,
            },
        )
        return raw_row

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

    def get_raw_download_path(
        self,
        tenant_id: str,
        raw_id: str,
        *,
        viewer_user_id: str | None,
    ) -> Path:
        with self._session() as session:
            row = self._get_scoped_raw(session, tenant_id, raw_id)
            if not self._is_visible(
                session,
                tenant_id,
                viewer_user_id,
                task_id=row.task_id,
                mission_id=row.mission_id,
            ):
                raise NotFoundError("raw data record not found")
            if not row.bucket or not row.object_key:
                raise NotFoundError("raw object not found")
            try:
                return self._storage.get_download_path(bucket=row.bucket, object_key=row.object_key)
            except ObjectStorageNotFoundError as exc:
                raise NotFoundError("raw object not found") from exc

    def create_outcome_record(
        self,
        tenant_id: str,
        actor_id: str,
        payload: OutcomeCatalogCreate,
    ) -> OutcomeCatalogRecord:
        with self._session() as session:
            observation: InspectionObservation | None = None
            if payload.task_id is not None:
                _ = self._get_scoped_task(session, tenant_id, payload.task_id)
            if payload.mission_id is not None:
                _ = self._get_scoped_mission(session, tenant_id, payload.mission_id)
            if payload.source_type == OutcomeSourceType.INSPECTION_OBSERVATION:
                observation = self._get_scoped_observation(session, tenant_id, payload.source_id)

            self._ensure_visible(
                session,
                tenant_id,
                actor_id,
                task_id=payload.task_id if payload.task_id is not None else (observation.task_id if observation else None),
                mission_id=payload.mission_id,
                not_found_detail="outcome record not found",
            )

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
            _ = self._append_outcome_version(
                session,
                row,
                actor_id=actor_id,
                change_type=OutcomeVersionChangeType.INIT_SNAPSHOT,
            )

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

    def transition_raw_storage(
        self,
        tenant_id: str,
        raw_id: str,
        actor_id: str,
        payload: RawDataStorageTransitionRequest,
        *,
        viewer_user_id: str | None,
    ) -> RawDataCatalogRecord:
        with self._session() as session:
            row = self._get_scoped_raw(session, tenant_id, raw_id)
            self._ensure_visible(
                session,
                tenant_id,
                viewer_user_id,
                task_id=row.task_id,
                mission_id=row.mission_id,
                not_found_detail="raw data record not found",
            )
            row.access_tier = payload.access_tier
            if payload.storage_region is not None:
                value = payload.storage_region.strip()
                row.storage_region = value if value else None

            if row.access_tier == RawDataAccessTier.COLD and (row.storage_class or "").upper() == "STANDARD":
                row.storage_class = "ARCHIVE"
            if row.access_tier == RawDataAccessTier.HOT and (row.storage_class or "").upper() in {
                "ARCHIVE",
                "GLACIER",
                "DEEP_ARCHIVE",
            }:
                row.storage_class = "STANDARD"

            detail: dict[str, Any] = dict(row.meta)
            history_raw = detail.get("storage_transitions")
            history: list[dict[str, Any]]
            if isinstance(history_raw, list):
                history = [item for item in history_raw if isinstance(item, dict)]
            else:
                history = []
            history.append(
                {
                    "ts": now_utc().isoformat(),
                    "actor_id": actor_id,
                    "access_tier": row.access_tier.value,
                    "storage_region": row.storage_region,
                    "storage_class": row.storage_class,
                }
            )
            detail["storage_transitions"] = history
            row.meta = detail
            session.add(row)
            session.commit()
            session.refresh(row)

        event_bus.publish_dict(
            "outcome.raw.storage.transitioned",
            tenant_id,
            {
                "raw_id": row.id,
                "access_tier": row.access_tier,
                "storage_region": row.storage_region,
                "storage_class": row.storage_class,
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
            self._ensure_visible(
                session,
                tenant_id,
                actor_id,
                task_id=observation.task_id,
                mission_id=None,
                not_found_detail="outcome record not found",
            )
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
            _ = self._append_outcome_version(
                session,
                row,
                actor_id=actor_id,
                change_type=OutcomeVersionChangeType.AUTO_MATERIALIZE,
                change_note=f"materialized from observation {observation_id}",
            )

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
            self._ensure_visible(
                session,
                tenant_id,
                actor_id,
                task_id=row.task_id,
                mission_id=row.mission_id,
                not_found_detail="outcome record not found",
            )
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
            _ = self._append_outcome_version(
                session,
                row,
                actor_id=actor_id,
                change_type=OutcomeVersionChangeType.STATUS_UPDATE,
                change_note=payload.note,
            )

        event_bus.publish_dict(
            "outcome.record.status_changed",
            tenant_id,
            {"outcome_id": row.id, "status": row.status, "reviewed_by": row.reviewed_by},
        )
        return row

    def list_outcome_versions(
        self,
        tenant_id: str,
        outcome_id: str,
        *,
        viewer_user_id: str | None,
    ) -> list[OutcomeCatalogVersion]:
        with self._session() as session:
            row = self._get_scoped_outcome(session, tenant_id, outcome_id)
            self._ensure_visible(
                session,
                tenant_id,
                viewer_user_id,
                task_id=row.task_id,
                mission_id=row.mission_id,
                not_found_detail="outcome record not found",
            )
            statement = (
                select(OutcomeCatalogVersion)
                .where(OutcomeCatalogVersion.tenant_id == tenant_id)
                .where(OutcomeCatalogVersion.outcome_id == outcome_id)
                .order_by(col(OutcomeCatalogVersion.version_no))
            )
            return list(session.exec(statement).all())
