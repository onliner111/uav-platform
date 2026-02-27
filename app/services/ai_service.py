from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, col, select

from app.domain.models import (
    AiAnalysisJob,
    AiAnalysisJobBindModelVersionRequest,
    AiAnalysisJobCreate,
    AiAnalysisOutput,
    AiAnalysisRun,
    AiAnalysisRunRetryRequest,
    AiAnalysisRunTriggerRequest,
    AiEvaluationCompareRead,
    AiEvaluationRecomputeRequest,
    AiEvaluationSummaryRead,
    AiEvidenceRecord,
    AiEvidenceType,
    AiJobStatus,
    AiModelCatalog,
    AiModelCatalogCreate,
    AiModelRolloutPolicy,
    AiModelRolloutPolicyUpsertRequest,
    AiModelRolloutRollbackRequest,
    AiModelVersion,
    AiModelVersionCreate,
    AiModelVersionPromoteRequest,
    AiModelVersionStatus,
    AiOutputReviewAction,
    AiOutputReviewActionCreate,
    AiOutputReviewStatus,
    AiReviewActionType,
    AiRunStatus,
    AiScheduleTickRead,
    AiScheduleTickRequest,
    AiTriggerMode,
    AlertRecord,
    AlertStatus,
    InspectionTask,
    Mission,
    OutcomeCatalogRecord,
)
from app.infra.db import get_engine
from app.infra.events import event_bus
from app.services.data_perimeter_service import DataPerimeterService


class AiAssistantError(Exception):
    pass


class NotFoundError(AiAssistantError):
    pass


class ConflictError(AiAssistantError):
    pass


class AiAssistantService:
    MAX_RETRY_COUNT = 3

    def __init__(self) -> None:
        self._data_perimeter = DataPerimeterService()

    def _session(self) -> Session:
        return Session(get_engine(), expire_on_commit=False)

    @staticmethod
    def _hash_payload(payload: dict[str, Any]) -> str:
        serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    def _get_scoped_task(self, session: Session, tenant_id: str, task_id: str) -> InspectionTask:
        row = session.exec(
            select(InspectionTask)
            .where(InspectionTask.tenant_id == tenant_id)
            .where(InspectionTask.id == task_id)
        ).first()
        if row is None:
            raise NotFoundError("inspection task not found")
        return row

    def _get_scoped_mission(self, session: Session, tenant_id: str, mission_id: str) -> Mission:
        row = session.exec(
            select(Mission)
            .where(Mission.tenant_id == tenant_id)
            .where(Mission.id == mission_id)
        ).first()
        if row is None:
            raise NotFoundError("mission not found")
        return row

    def _get_scoped_job(self, session: Session, tenant_id: str, job_id: str) -> AiAnalysisJob:
        row = session.exec(
            select(AiAnalysisJob)
            .where(AiAnalysisJob.tenant_id == tenant_id)
            .where(AiAnalysisJob.id == job_id)
        ).first()
        if row is None:
            raise NotFoundError("ai analysis job not found")
        return row

    def _get_scoped_run(self, session: Session, tenant_id: str, run_id: str) -> AiAnalysisRun:
        row = session.exec(
            select(AiAnalysisRun)
            .where(AiAnalysisRun.tenant_id == tenant_id)
            .where(AiAnalysisRun.id == run_id)
        ).first()
        if row is None:
            raise NotFoundError("ai analysis run not found")
        return row

    def _get_scoped_output(self, session: Session, tenant_id: str, output_id: str) -> AiAnalysisOutput:
        row = session.exec(
            select(AiAnalysisOutput)
            .where(AiAnalysisOutput.tenant_id == tenant_id)
            .where(AiAnalysisOutput.id == output_id)
        ).first()
        if row is None:
            raise NotFoundError("ai analysis output not found")
        return row

    @staticmethod
    def _normalize_model_key(provider: str, model_name: str) -> str:
        provider_key = provider.strip().lower()
        name_key = model_name.strip().lower()
        if not provider_key or not name_key:
            raise ConflictError("model provider/name cannot be empty")
        return f"{provider_key}:{name_key}"

    def _get_scoped_model_catalog(self, session: Session, tenant_id: str, model_id: str) -> AiModelCatalog:
        row = session.exec(
            select(AiModelCatalog)
            .where(AiModelCatalog.tenant_id == tenant_id)
            .where(AiModelCatalog.id == model_id)
        ).first()
        if row is None:
            raise NotFoundError("ai model catalog not found")
        return row

    def _get_scoped_model_version(self, session: Session, tenant_id: str, version_id: str) -> AiModelVersion:
        row = session.exec(
            select(AiModelVersion)
            .where(AiModelVersion.tenant_id == tenant_id)
            .where(AiModelVersion.id == version_id)
        ).first()
        if row is None:
            raise NotFoundError("ai model version not found")
        return row

    def _get_scoped_rollout_policy(
        self,
        session: Session,
        tenant_id: str,
        model_id: str,
    ) -> AiModelRolloutPolicy:
        row = session.exec(
            select(AiModelRolloutPolicy)
            .where(AiModelRolloutPolicy.tenant_id == tenant_id)
            .where(AiModelRolloutPolicy.model_id == model_id)
        ).first()
        if row is None:
            raise NotFoundError("ai model rollout policy not found")
        return row

    def _upsert_default_rollout_policy(
        self,
        session: Session,
        *,
        tenant_id: str,
        model_id: str,
        actor_id: str,
        stable_version_id: str | None,
    ) -> AiModelRolloutPolicy | None:
        policy = session.exec(
            select(AiModelRolloutPolicy)
            .where(AiModelRolloutPolicy.tenant_id == tenant_id)
            .where(AiModelRolloutPolicy.model_id == model_id)
        ).first()
        if policy is None and stable_version_id is None:
            return None
        if policy is None:
            policy = AiModelRolloutPolicy(
                tenant_id=tenant_id,
                model_id=model_id,
                default_version_id=stable_version_id,
                traffic_allocation=(
                    [{"version_id": stable_version_id, "weight": 100}] if stable_version_id else []
                ),
                threshold_overrides={},
                detail={},
                is_active=True,
                updated_by=actor_id,
            )
            session.add(policy)
            return policy

        policy.updated_by = actor_id
        policy.updated_at = datetime.now(UTC)
        if stable_version_id is not None:
            policy.default_version_id = stable_version_id
            policy.traffic_allocation = [{"version_id": stable_version_id, "weight": 100}]
        session.add(policy)
        return policy

    def _resolve_job_model_version(
        self,
        session: Session,
        *,
        tenant_id: str,
        actor_id: str,
        payload: AiAnalysisJobCreate,
    ) -> tuple[AiModelCatalog, AiModelVersion]:
        if payload.model_version_id:
            version = self._get_scoped_model_version(session, tenant_id, payload.model_version_id)
            model = self._get_scoped_model_catalog(session, tenant_id, version.model_id)
            return model, version

        model_key = self._normalize_model_key(payload.model_provider, payload.model_name)
        model_row = session.exec(
            select(AiModelCatalog)
            .where(AiModelCatalog.tenant_id == tenant_id)
            .where(AiModelCatalog.model_key == model_key)
        ).first()
        if model_row is None:
            model_row = AiModelCatalog(
                tenant_id=tenant_id,
                model_key=model_key,
                provider=payload.model_provider.strip(),
                display_name=payload.model_name.strip(),
                description="auto-provisioned from ai analysis job",
                is_active=True,
                created_by=actor_id,
            )
            session.add(model_row)
            session.flush()
        model = model_row

        version_row = session.exec(
            select(AiModelVersion)
            .where(AiModelVersion.tenant_id == tenant_id)
            .where(AiModelVersion.model_id == model.id)
            .where(AiModelVersion.version == payload.model_version)
        ).first()
        if version_row is None:
            has_stable = session.exec(
                select(AiModelVersion.id)
                .where(AiModelVersion.tenant_id == tenant_id)
                .where(AiModelVersion.model_id == model.id)
                .where(AiModelVersion.status == AiModelVersionStatus.STABLE)
            ).first()
            version_row = AiModelVersion(
                tenant_id=tenant_id,
                model_id=model.id,
                version=payload.model_version,
                status=AiModelVersionStatus.STABLE if has_stable is None else AiModelVersionStatus.DRAFT,
                threshold_defaults=dict(payload.threshold_config),
                detail={"source": "auto_job_provision"},
                artifact_ref=None,
                created_by=actor_id,
                promoted_at=datetime.now(UTC) if has_stable is None else None,
            )
            session.add(version_row)
            session.flush()
            self._upsert_default_rollout_policy(
                session,
                tenant_id=tenant_id,
                model_id=model.id,
                actor_id=actor_id,
                stable_version_id=(
                    version_row.id if version_row.status == AiModelVersionStatus.STABLE else has_stable
                ),
            )
        else:
            stable = session.exec(
                select(AiModelVersion.id)
                .where(AiModelVersion.tenant_id == tenant_id)
                .where(AiModelVersion.model_id == model.id)
                .where(AiModelVersion.status == AiModelVersionStatus.STABLE)
            ).first()
            self._upsert_default_rollout_policy(
                session,
                tenant_id=tenant_id,
                model_id=model.id,
                actor_id=actor_id,
                stable_version_id=stable,
            )
        version = version_row
        return model, version

    def _validate_rollout_traffic(
        self,
        session: Session,
        *,
        tenant_id: str,
        model_id: str,
        traffic_allocation: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        normalized: list[dict[str, Any]] = []
        total_weight = 0
        seen_version_ids: set[str] = set()
        for item in traffic_allocation:
            if not isinstance(item, dict):
                raise ConflictError("traffic_allocation item must be object")
            version_id_raw = item.get("version_id")
            weight_raw = item.get("weight")
            if not isinstance(version_id_raw, str) or not version_id_raw.strip():
                raise ConflictError("traffic_allocation.version_id must be non-empty string")
            if not isinstance(weight_raw, int):
                raise ConflictError("traffic_allocation.weight must be integer")
            version_id = version_id_raw.strip()
            if version_id in seen_version_ids:
                raise ConflictError("traffic_allocation has duplicated version_id")
            if weight_raw <= 0 or weight_raw > 100:
                raise ConflictError("traffic_allocation.weight must be in 1..100")
            seen_version_ids.add(version_id)
            total_weight += weight_raw
            normalized.append({"version_id": version_id, "weight": weight_raw})

        if not normalized:
            raise ConflictError("traffic_allocation cannot be empty")
        if len(normalized) > 1:
            for item in normalized:
                if item["weight"] >= 100:
                    raise ConflictError("canary allocation weight must be in 1..99")
        if total_weight != 100:
            raise ConflictError("traffic_allocation total weight must equal 100")

        for item in normalized:
            version = self._get_scoped_model_version(session, tenant_id, item["version_id"])
            if version.model_id != model_id:
                raise ConflictError("traffic_allocation version must belong to the same model")
        return normalized

    def _select_version_by_rollout(
        self,
        *,
        run_id: str,
        traffic_allocation: list[dict[str, Any]],
    ) -> str:
        hash_value = hashlib.sha256(run_id.encode("utf-8")).hexdigest()
        bucket = int(hash_value[:8], 16) % 100
        cursor = 0
        for item in traffic_allocation:
            cursor += int(item["weight"])
            if bucket < cursor:
                return str(item["version_id"])
        return str(traffic_allocation[-1]["version_id"])

    def _resolve_run_model_context(
        self,
        session: Session,
        *,
        tenant_id: str,
        job: AiAnalysisJob,
        payload: AiAnalysisRunTriggerRequest,
        run_id: str,
    ) -> dict[str, Any]:
        selection_source = "JOB_BINDING"
        policy: AiModelRolloutPolicy | None = None
        if payload.force_model_version_id:
            version = self._get_scoped_model_version(session, tenant_id, payload.force_model_version_id)
            model = self._get_scoped_model_catalog(session, tenant_id, version.model_id)
            selection_source = "MANUAL_FORCE"
        elif job.model_version_id:
            version = self._get_scoped_model_version(session, tenant_id, job.model_version_id)
            model = self._get_scoped_model_catalog(session, tenant_id, version.model_id)
        else:
            model_key = self._normalize_model_key(job.model_provider, job.model_name)
            model_row = session.exec(
                select(AiModelCatalog)
                .where(AiModelCatalog.tenant_id == tenant_id)
                .where(AiModelCatalog.model_key == model_key)
            ).first()
            if model_row is None:
                raise ConflictError("unable to resolve model catalog for run")
            model = model_row
            selection_source = "MODEL_DEFAULT"
            policy = self._get_scoped_rollout_policy(session, tenant_id, model.id)
            if not policy.default_version_id:
                raise ConflictError("rollout policy default version is missing")
            version = self._get_scoped_model_version(session, tenant_id, policy.default_version_id)

        if policy is None:
            try:
                policy = self._get_scoped_rollout_policy(session, tenant_id, model.id)
            except NotFoundError:
                policy = None

        if selection_source == "MODEL_DEFAULT":
            if policy is not None and policy.is_active and policy.traffic_allocation:
                selected_version_id = self._select_version_by_rollout(
                    run_id=run_id,
                    traffic_allocation=policy.traffic_allocation,
                )
                version = self._get_scoped_model_version(session, tenant_id, selected_version_id)
            elif policy is not None and policy.default_version_id:
                version = self._get_scoped_model_version(session, tenant_id, policy.default_version_id)
            else:
                stable_row = session.exec(
                    select(AiModelVersion)
                    .where(AiModelVersion.tenant_id == tenant_id)
                    .where(AiModelVersion.model_id == model.id)
                    .where(AiModelVersion.status == AiModelVersionStatus.STABLE)
                ).first()
                if stable_row is None:
                    raise ConflictError("unable to resolve model default version for run")
                version = stable_row

        threshold_snapshot: dict[str, Any] = dict(version.threshold_defaults)
        if policy is not None and policy.is_active:
            threshold_snapshot.update(policy.threshold_overrides)
        threshold_snapshot.update(job.threshold_config)
        threshold_snapshot.update(payload.force_threshold_config)

        policy_snapshot = None
        if policy is not None:
            policy_snapshot = {
                "policy_id": policy.id,
                "default_version_id": policy.default_version_id,
                "traffic_allocation": policy.traffic_allocation,
                "threshold_overrides": policy.threshold_overrides,
                "is_active": policy.is_active,
            }

        return {
            "selection_source": selection_source,
            "model_id": model.id,
            "model_key": model.model_key,
            "model_provider": model.provider,
            "model_name": model.display_name,
            "model_version_id": version.id,
            "model_version": version.version,
            "model_version_status": version.status.value,
            "threshold_snapshot": threshold_snapshot,
            "policy_snapshot": policy_snapshot,
        }

    @staticmethod
    def _calc_p95(values: list[int]) -> int | None:
        if not values:
            return None
        sorted_values = sorted(values)
        if len(sorted_values) == 1:
            return sorted_values[0]
        rank = int(round((len(sorted_values) - 1) * 0.95))
        if rank < 0:
            rank = 0
        if rank >= len(sorted_values):
            rank = len(sorted_values) - 1
        return sorted_values[rank]

    def _build_evaluation_summary(
        self,
        *,
        model_version_id: str,
        runs: list[AiAnalysisRun],
        outputs: list[AiAnalysisOutput],
    ) -> AiEvaluationSummaryRead:
        total = len(runs)
        succeeded = sum(1 for item in runs if item.status == AiRunStatus.SUCCEEDED)
        success_rate = (succeeded / total) if total else 0.0
        output_by_run = {item.run_id: item for item in outputs}
        override_count = 0
        for run in runs:
            output = output_by_run.get(run.id)
            if output is not None and output.review_status == AiOutputReviewStatus.OVERRIDDEN:
                override_count += 1
        override_rate = (override_count / total) if total else 0.0

        duration_values: list[int] = []
        for run in runs:
            duration_raw = run.metrics.get("duration_ms")
            if isinstance(duration_raw, int) and duration_raw >= 0:
                duration_values.append(duration_raw)

        return AiEvaluationSummaryRead(
            model_version_id=model_version_id,
            total_runs=total,
            succeeded_runs=succeeded,
            success_rate=round(success_rate, 4),
            review_override_rate=round(override_rate, 4),
            p95_latency_ms=self._calc_p95(duration_values),
        )

    def _collect_runs_for_evaluation(
        self,
        session: Session,
        *,
        tenant_id: str,
        model_id: str | None,
        job_id: str | None,
        model_version_id: str | None,
        from_ts: datetime | None,
        to_ts: datetime | None,
    ) -> list[AiAnalysisRun]:
        statement = select(AiAnalysisRun).where(AiAnalysisRun.tenant_id == tenant_id)
        if job_id is not None:
            statement = statement.where(AiAnalysisRun.job_id == job_id)
        if from_ts is not None:
            statement = statement.where(AiAnalysisRun.started_at >= from_ts)
        if to_ts is not None:
            statement = statement.where(AiAnalysisRun.started_at <= to_ts)
        runs = list(session.exec(statement).all())

        if not runs:
            return []

        jobs_by_id = {
            item.id: item
            for item in session.exec(select(AiAnalysisJob).where(AiAnalysisJob.tenant_id == tenant_id)).all()
        }
        filtered: list[AiAnalysisRun] = []
        for run in runs:
            selected_version_id = run.metrics.get("model_version_id")
            if not isinstance(selected_version_id, str) or not selected_version_id:
                job = jobs_by_id.get(run.job_id)
                selected_version_id = job.model_version_id if job else None
            if not isinstance(selected_version_id, str) or not selected_version_id:
                continue
            if model_version_id is not None and selected_version_id != model_version_id:
                continue
            if model_id is not None:
                version = self._get_scoped_model_version(session, tenant_id, selected_version_id)
                if version.model_id != model_id:
                    continue
            run.metrics["model_version_id"] = selected_version_id
            filtered.append(run)
        return filtered

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

    def create_model_catalog(
        self,
        tenant_id: str,
        actor_id: str,
        payload: AiModelCatalogCreate,
    ) -> AiModelCatalog:
        model_key = payload.model_key.strip().lower()
        provider = payload.provider.strip()
        display_name = payload.display_name.strip()
        if not model_key or not provider or not display_name:
            raise ConflictError("model_key/provider/display_name cannot be empty")
        with self._session() as session:
            row = AiModelCatalog(
                tenant_id=tenant_id,
                model_key=model_key,
                provider=provider,
                display_name=display_name,
                description=payload.description,
                is_active=payload.is_active,
                created_by=actor_id,
            )
            session.add(row)
            try:
                session.commit()
            except IntegrityError as exc:
                session.rollback()
                raise ConflictError("ai model catalog already exists") from exc
            session.refresh(row)
            return row

    def list_model_catalogs(
        self,
        tenant_id: str,
        *,
        model_key: str | None = None,
        provider: str | None = None,
    ) -> list[AiModelCatalog]:
        with self._session() as session:
            statement = select(AiModelCatalog).where(AiModelCatalog.tenant_id == tenant_id)
            if model_key is not None:
                statement = statement.where(AiModelCatalog.model_key == model_key.strip().lower())
            if provider is not None:
                statement = statement.where(AiModelCatalog.provider == provider.strip())
            rows = list(session.exec(statement).all())
            return sorted(rows, key=lambda item: item.created_at, reverse=True)

    def create_model_version(
        self,
        tenant_id: str,
        model_id: str,
        actor_id: str,
        payload: AiModelVersionCreate,
    ) -> AiModelVersion:
        with self._session() as session:
            model = self._get_scoped_model_catalog(session, tenant_id, model_id)
            if payload.status == AiModelVersionStatus.STABLE:
                existing_stable = session.exec(
                    select(AiModelVersion.id)
                    .where(AiModelVersion.tenant_id == tenant_id)
                    .where(AiModelVersion.model_id == model.id)
                    .where(AiModelVersion.status == AiModelVersionStatus.STABLE)
                ).first()
                if existing_stable is not None:
                    raise ConflictError("stable model version already exists")

            row = AiModelVersion(
                tenant_id=tenant_id,
                model_id=model.id,
                version=payload.version,
                status=payload.status,
                artifact_ref=payload.artifact_ref,
                threshold_defaults=payload.threshold_defaults,
                detail=payload.detail,
                created_by=actor_id,
                promoted_at=datetime.now(UTC) if payload.status == AiModelVersionStatus.STABLE else None,
            )
            session.add(row)
            try:
                session.flush()
            except IntegrityError as exc:
                session.rollback()
                raise ConflictError("model version already exists") from exc

            stable_version_id = row.id if row.status == AiModelVersionStatus.STABLE else None
            self._upsert_default_rollout_policy(
                session,
                tenant_id=tenant_id,
                model_id=model.id,
                actor_id=actor_id,
                stable_version_id=stable_version_id,
            )
            session.commit()
            session.refresh(row)
            return row

    def list_model_versions(
        self,
        tenant_id: str,
        model_id: str,
        *,
        status: AiModelVersionStatus | None = None,
    ) -> list[AiModelVersion]:
        with self._session() as session:
            _ = self._get_scoped_model_catalog(session, tenant_id, model_id)
            statement = (
                select(AiModelVersion)
                .where(AiModelVersion.tenant_id == tenant_id)
                .where(AiModelVersion.model_id == model_id)
            )
            if status is not None:
                statement = statement.where(AiModelVersion.status == status)
            rows = list(session.exec(statement).all())
            return sorted(rows, key=lambda item: item.created_at, reverse=True)

    def promote_model_version(
        self,
        tenant_id: str,
        model_id: str,
        version_id: str,
        actor_id: str,
        payload: AiModelVersionPromoteRequest,
    ) -> AiModelVersion:
        with self._session() as session:
            _ = self._get_scoped_model_catalog(session, tenant_id, model_id)
            version = self._get_scoped_model_version(session, tenant_id, version_id)
            if version.model_id != model_id:
                raise NotFoundError("ai model version not found")

            if payload.target_status == AiModelVersionStatus.STABLE:
                stable_rows = list(
                    session.exec(
                        select(AiModelVersion)
                        .where(AiModelVersion.tenant_id == tenant_id)
                        .where(AiModelVersion.model_id == model_id)
                        .where(AiModelVersion.status == AiModelVersionStatus.STABLE)
                        .where(AiModelVersion.id != version.id)
                    ).all()
                )
                for item in stable_rows:
                    item.status = AiModelVersionStatus.DEPRECATED
                    item.updated_at = datetime.now(UTC)
                    session.add(item)

            version.status = payload.target_status
            version.updated_at = datetime.now(UTC)
            if payload.target_status == AiModelVersionStatus.STABLE:
                version.promoted_at = datetime.now(UTC)
                self._upsert_default_rollout_policy(
                    session,
                    tenant_id=tenant_id,
                    model_id=model_id,
                    actor_id=actor_id,
                    stable_version_id=version.id,
                )
            session.add(version)
            session.commit()
            session.refresh(version)
            return version

    def get_rollout_policy(self, tenant_id: str, model_id: str) -> AiModelRolloutPolicy:
        with self._session() as session:
            _ = self._get_scoped_model_catalog(session, tenant_id, model_id)
            return self._get_scoped_rollout_policy(session, tenant_id, model_id)

    def upsert_rollout_policy(
        self,
        tenant_id: str,
        model_id: str,
        actor_id: str,
        payload: AiModelRolloutPolicyUpsertRequest,
    ) -> AiModelRolloutPolicy:
        with self._session() as session:
            _ = self._get_scoped_model_catalog(session, tenant_id, model_id)

            default_version_id = payload.default_version_id
            if default_version_id is None:
                existing = session.exec(
                    select(AiModelVersion.id)
                    .where(AiModelVersion.tenant_id == tenant_id)
                    .where(AiModelVersion.model_id == model_id)
                    .where(AiModelVersion.status == AiModelVersionStatus.STABLE)
                ).first()
                if existing is None:
                    raise ConflictError("rollout policy requires default stable version")
                default_version_id = existing

            default_version = self._get_scoped_model_version(session, tenant_id, default_version_id)
            if default_version.model_id != model_id:
                raise ConflictError("default_version_id must belong to model")

            if payload.traffic_allocation:
                traffic_allocation = self._validate_rollout_traffic(
                    session,
                    tenant_id=tenant_id,
                    model_id=model_id,
                    traffic_allocation=payload.traffic_allocation,
                )
            else:
                traffic_allocation = [{"version_id": default_version_id, "weight": 100}]

            if not any(item["version_id"] == default_version_id for item in traffic_allocation):
                raise ConflictError("traffic_allocation must include default_version_id")

            policy = session.exec(
                select(AiModelRolloutPolicy)
                .where(AiModelRolloutPolicy.tenant_id == tenant_id)
                .where(AiModelRolloutPolicy.model_id == model_id)
            ).first()
            if policy is None:
                policy = AiModelRolloutPolicy(
                    tenant_id=tenant_id,
                    model_id=model_id,
                    default_version_id=default_version_id,
                    traffic_allocation=traffic_allocation,
                    threshold_overrides=payload.threshold_overrides,
                    detail=payload.detail,
                    is_active=payload.is_active,
                    updated_by=actor_id,
                )
            else:
                policy.default_version_id = default_version_id
                policy.traffic_allocation = traffic_allocation
                policy.threshold_overrides = payload.threshold_overrides
                policy.detail = payload.detail
                policy.is_active = payload.is_active
                policy.updated_by = actor_id
                policy.updated_at = datetime.now(UTC)
            session.add(policy)
            session.commit()
            session.refresh(policy)
            return policy

    def bind_job_model_version(
        self,
        tenant_id: str,
        job_id: str,
        actor_id: str,
        payload: AiAnalysisJobBindModelVersionRequest,
    ) -> AiAnalysisJob:
        with self._session() as session:
            job = self._get_scoped_job(session, tenant_id, job_id)
            version = self._get_scoped_model_version(session, tenant_id, payload.model_version_id)
            model = self._get_scoped_model_catalog(session, tenant_id, version.model_id)

            job.model_version_id = version.id
            job.model_provider = model.provider
            job.model_name = model.display_name
            job.model_version = version.version
            if not job.threshold_config:
                job.threshold_config = dict(version.threshold_defaults)
            job.updated_at = datetime.now(UTC)
            session.add(job)
            session.commit()
            session.refresh(job)

        event_bus.publish_dict(
            "ai.job.model_version.bound",
            tenant_id,
            {
                "job_id": job.id,
                "model_version_id": job.model_version_id,
                "actor_id": actor_id,
            },
        )
        return job

    def recompute_evaluations(
        self,
        tenant_id: str,
        payload: AiEvaluationRecomputeRequest,
    ) -> list[AiEvaluationSummaryRead]:
        with self._session() as session:
            if payload.model_id is not None:
                _ = self._get_scoped_model_catalog(session, tenant_id, payload.model_id)
            if payload.job_id is not None:
                _ = self._get_scoped_job(session, tenant_id, payload.job_id)

            runs = self._collect_runs_for_evaluation(
                session,
                tenant_id=tenant_id,
                model_id=payload.model_id,
                job_id=payload.job_id,
                model_version_id=None,
                from_ts=payload.from_ts,
                to_ts=payload.to_ts,
            )
            if not runs:
                return []

            run_ids = {item.id for item in runs}
            outputs = [
                item
                for item in session.exec(select(AiAnalysisOutput).where(AiAnalysisOutput.tenant_id == tenant_id)).all()
                if item.run_id in run_ids
            ]

            grouped: dict[str, list[AiAnalysisRun]] = {}
            for run in runs:
                version_id = run.metrics.get("model_version_id")
                if not isinstance(version_id, str) or not version_id:
                    continue
                grouped.setdefault(version_id, []).append(run)

            summaries: list[AiEvaluationSummaryRead] = []
            for version_id, run_group in grouped.items():
                output_group = [item for item in outputs if item.run_id in {row.id for row in run_group}]
                summaries.append(
                    self._build_evaluation_summary(
                        model_version_id=version_id,
                        runs=run_group,
                        outputs=output_group,
                    )
                )
            return sorted(summaries, key=lambda item: item.model_version_id)

    def compare_evaluations(
        self,
        tenant_id: str,
        *,
        left_version_id: str,
        right_version_id: str,
        job_id: str | None = None,
        from_ts: datetime | None = None,
        to_ts: datetime | None = None,
    ) -> AiEvaluationCompareRead:
        with self._session() as session:
            _ = self._get_scoped_model_version(session, tenant_id, left_version_id)
            _ = self._get_scoped_model_version(session, tenant_id, right_version_id)
            if job_id is not None:
                _ = self._get_scoped_job(session, tenant_id, job_id)

            def _one(version_id: str) -> AiEvaluationSummaryRead:
                runs = self._collect_runs_for_evaluation(
                    session,
                    tenant_id=tenant_id,
                    model_id=None,
                    job_id=job_id,
                    model_version_id=version_id,
                    from_ts=from_ts,
                    to_ts=to_ts,
                )
                run_ids = {item.id for item in runs}
                outputs = [
                    item
                    for item in session.exec(
                        select(AiAnalysisOutput).where(AiAnalysisOutput.tenant_id == tenant_id)
                    ).all()
                    if item.run_id in run_ids
                ]
                return self._build_evaluation_summary(
                    model_version_id=version_id,
                    runs=runs,
                    outputs=outputs,
                )

            left = _one(left_version_id)
            right = _one(right_version_id)
            delta_p95 = None
            if left.p95_latency_ms is not None and right.p95_latency_ms is not None:
                delta_p95 = right.p95_latency_ms - left.p95_latency_ms
            return AiEvaluationCompareRead(
                left=left,
                right=right,
                delta_success_rate=round(right.success_rate - left.success_rate, 4),
                delta_review_override_rate=round(right.review_override_rate - left.review_override_rate, 4),
                delta_p95_latency_ms=delta_p95,
            )

    def rollback_rollout_policy(
        self,
        tenant_id: str,
        model_id: str,
        actor_id: str,
        payload: AiModelRolloutRollbackRequest,
    ) -> AiModelRolloutPolicy:
        with self._session() as session:
            _ = self._get_scoped_model_catalog(session, tenant_id, model_id)
            target = self._get_scoped_model_version(session, tenant_id, payload.target_version_id)
            if target.model_id != model_id:
                raise ConflictError("target_version_id must belong to model")

            stable_rows = list(
                session.exec(
                    select(AiModelVersion)
                    .where(AiModelVersion.tenant_id == tenant_id)
                    .where(AiModelVersion.model_id == model_id)
                    .where(AiModelVersion.status == AiModelVersionStatus.STABLE)
                    .where(AiModelVersion.id != target.id)
                ).all()
            )
            for item in stable_rows:
                item.status = AiModelVersionStatus.DEPRECATED
                item.updated_at = datetime.now(UTC)
                session.add(item)

            target.status = AiModelVersionStatus.STABLE
            target.promoted_at = datetime.now(UTC)
            target.updated_at = datetime.now(UTC)
            session.add(target)

            policy = session.exec(
                select(AiModelRolloutPolicy)
                .where(AiModelRolloutPolicy.tenant_id == tenant_id)
                .where(AiModelRolloutPolicy.model_id == model_id)
            ).first()
            if policy is None:
                policy = AiModelRolloutPolicy(
                    tenant_id=tenant_id,
                    model_id=model_id,
                    default_version_id=target.id,
                    traffic_allocation=[{"version_id": target.id, "weight": 100}],
                    threshold_overrides={},
                    detail={},
                    is_active=True,
                    updated_by=actor_id,
                )
            else:
                history = policy.detail.get("rollback_history", [])
                if not isinstance(history, list):
                    history = []
                history.append(
                    {
                        "at": datetime.now(UTC).isoformat(),
                        "by": actor_id,
                        "target_version_id": target.id,
                        "reason": payload.reason,
                    }
                )
                policy.default_version_id = target.id
                policy.traffic_allocation = [{"version_id": target.id, "weight": 100}]
                policy.detail = {**policy.detail, "rollback_history": history}
                policy.updated_by = actor_id
                policy.updated_at = datetime.now(UTC)
            session.add(policy)
            session.commit()
            session.refresh(policy)

        event_bus.publish_dict(
            "ai.rollout.rollback",
            tenant_id,
            {
                "model_id": model_id,
                "target_version_id": payload.target_version_id,
                "actor_id": actor_id,
                "reason": payload.reason,
            },
        )
        return policy

    def schedule_tick(
        self,
        tenant_id: str,
        actor_id: str,
        payload: AiScheduleTickRequest,
    ) -> AiScheduleTickRead:
        window_key = payload.window_key.strip()
        if not window_key:
            raise ConflictError("window_key cannot be empty")
        run_rows: list[tuple[AiAnalysisRun, AiAnalysisOutput | None]] = []
        skipped_jobs = 0
        scanned_jobs = 0
        with self._session() as session:
            statement = (
                select(AiAnalysisJob)
                .where(AiAnalysisJob.tenant_id == tenant_id)
                .where(AiAnalysisJob.status == AiJobStatus.ACTIVE)
                .where(col(AiAnalysisJob.trigger_mode).in_([AiTriggerMode.SCHEDULED, AiTriggerMode.NEAR_REALTIME]))
            )
            if payload.job_ids:
                statement = statement.where(col(AiAnalysisJob.id).in_(payload.job_ids))
            jobs = list(session.exec(statement).all())
            jobs = sorted(jobs, key=lambda item: item.created_at)[: payload.max_jobs]
            scanned_jobs = len(jobs)

            for job in jobs:
                previous_runs = list(
                    session.exec(
                        select(AiAnalysisRun)
                        .where(AiAnalysisRun.tenant_id == tenant_id)
                        .where(AiAnalysisRun.job_id == job.id)
                    ).all()
                )
                already_executed = any(run.metrics.get("schedule_window_key") == window_key for run in previous_runs)
                if already_executed:
                    skipped_jobs += 1
                    continue

                run, output = self._execute_run(
                    session,
                    tenant_id=tenant_id,
                    job=job,
                    actor_id=actor_id,
                    payload=AiAnalysisRunTriggerRequest(
                        force_fail=False,
                        trigger_mode=AiTriggerMode.NEAR_REALTIME,
                        context={**payload.context, "schedule_window_key": window_key},
                    ),
                    retry_of_run_id=None,
                    retry_count=0,
                )
                run_rows.append((run, output))
            session.commit()
            for run, _ in run_rows:
                session.refresh(run)

        for run, output in run_rows:
            if run.status == AiRunStatus.SUCCEEDED:
                event_bus.publish_dict(
                    "ai.run.succeeded",
                    tenant_id,
                    {"job_id": run.job_id, "run_id": run.id, "output_id": output.id if output else None},
                )
            else:
                event_bus.publish_dict(
                    "ai.run.failed",
                    tenant_id,
                    {"job_id": run.job_id, "run_id": run.id, "error_message": run.error_message},
                )
        event_bus.publish_dict(
            "ai.schedule.tick.executed",
            tenant_id,
            {
                "window_key": window_key,
                "scanned_jobs": scanned_jobs,
                "triggered_jobs": len(run_rows),
                "skipped_jobs": skipped_jobs,
            },
        )
        return AiScheduleTickRead(
            window_key=window_key,
            scanned_jobs=scanned_jobs,
            triggered_jobs=len(run_rows),
            skipped_jobs=skipped_jobs,
            run_ids=[run.id for run, _ in run_rows],
        )

    def create_job(self, tenant_id: str, actor_id: str, payload: AiAnalysisJobCreate) -> AiAnalysisJob:
        with self._session() as session:
            if payload.task_id is not None:
                _ = self._get_scoped_task(session, tenant_id, payload.task_id)
            if payload.mission_id is not None:
                _ = self._get_scoped_mission(session, tenant_id, payload.mission_id)
            model, model_version = self._resolve_job_model_version(
                session,
                tenant_id=tenant_id,
                actor_id=actor_id,
                payload=payload,
            )
            threshold_config = dict(payload.threshold_config)
            if not threshold_config and model_version.threshold_defaults:
                threshold_config = dict(model_version.threshold_defaults)

            row = AiAnalysisJob(
                tenant_id=tenant_id,
                task_id=payload.task_id,
                mission_id=payload.mission_id,
                topic=payload.topic,
                job_type=payload.job_type,
                trigger_mode=payload.trigger_mode,
                status=AiJobStatus.ACTIVE,
                model_version_id=model_version.id,
                model_provider=model.provider,
                model_name=model.display_name,
                model_version=model_version.version,
                threshold_config=threshold_config,
                input_config=payload.input_config,
                created_by=actor_id,
            )
            session.add(row)
            session.commit()
            session.refresh(row)

        event_bus.publish_dict(
            "ai.job.created",
            tenant_id,
            {
                "job_id": row.id,
                "job_type": row.job_type,
                "trigger_mode": row.trigger_mode,
                "model_version_id": row.model_version_id,
                "task_id": row.task_id,
                "mission_id": row.mission_id,
            },
        )
        return row

    def list_jobs(
        self,
        tenant_id: str,
        *,
        task_id: str | None = None,
        mission_id: str | None = None,
        viewer_user_id: str | None = None,
    ) -> list[AiAnalysisJob]:
        with self._session() as session:
            statement = select(AiAnalysisJob).where(AiAnalysisJob.tenant_id == tenant_id)
            if task_id is not None:
                statement = statement.where(AiAnalysisJob.task_id == task_id)
            if mission_id is not None:
                statement = statement.where(AiAnalysisJob.mission_id == mission_id)
            rows = list(session.exec(statement).all())
            visible = [
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
            return sorted(visible, key=lambda item: item.created_at, reverse=True)

    def _build_input_context(
        self,
        session: Session,
        tenant_id: str,
        job: AiAnalysisJob,
        context: dict[str, Any],
    ) -> tuple[dict[str, Any], list[OutcomeCatalogRecord], list[AlertRecord]]:
        outcomes_statement = select(OutcomeCatalogRecord).where(OutcomeCatalogRecord.tenant_id == tenant_id)
        if job.task_id is not None:
            outcomes_statement = outcomes_statement.where(OutcomeCatalogRecord.task_id == job.task_id)
        if job.mission_id is not None:
            outcomes_statement = outcomes_statement.where(OutcomeCatalogRecord.mission_id == job.mission_id)
        outcomes = list(session.exec(outcomes_statement).all())

        alerts_statement = select(AlertRecord).where(AlertRecord.tenant_id == tenant_id)
        alerts = list(session.exec(alerts_statement).all())

        if job.topic:
            topic = job.topic.strip().lower()
            outcomes = [
                item
                for item in outcomes
                if topic in item.outcome_type.value.lower() or topic in str(item.payload).lower()
            ]
            alerts = [
                item
                for item in alerts
                if topic in item.alert_type.value.lower()
                or topic in item.message.lower()
                or topic in str(item.detail).lower()
            ]

        open_alerts = [item for item in alerts if item.status != AlertStatus.CLOSED]
        input_payload = {
            "job": {
                "job_id": job.id,
                "job_type": job.job_type.value,
                "trigger_mode": job.trigger_mode.value,
                "task_id": job.task_id,
                "mission_id": job.mission_id,
                "topic": job.topic,
            },
            "context": context,
            "stats": {
                "outcomes_total": len(outcomes),
                "alerts_total": len(alerts),
                "open_alerts_total": len(open_alerts),
            },
        }
        return input_payload, outcomes, alerts

    def _write_evidence(
        self,
        session: Session,
        *,
        tenant_id: str,
        run: AiAnalysisRun,
        output: AiAnalysisOutput | None,
        job: AiAnalysisJob,
        model_snapshot: dict[str, Any] | None,
        input_payload: dict[str, Any],
        output_payload: dict[str, Any] | None,
    ) -> None:
        model_payload = model_snapshot or {
            "model_version_id": job.model_version_id,
            "provider": job.model_provider,
            "name": job.model_name,
            "version": job.model_version,
            "threshold_config": job.threshold_config,
        }
        records = [
            AiEvidenceRecord(
                tenant_id=tenant_id,
                run_id=run.id,
                output_id=output.id if output else None,
                evidence_type=AiEvidenceType.MODEL_CONFIG,
                content_hash=self._hash_payload(model_payload),
                payload=model_payload,
            ),
            AiEvidenceRecord(
                tenant_id=tenant_id,
                run_id=run.id,
                output_id=output.id if output else None,
                evidence_type=AiEvidenceType.INPUT_SNAPSHOT,
                content_hash=self._hash_payload(input_payload),
                payload=input_payload,
            ),
            AiEvidenceRecord(
                tenant_id=tenant_id,
                run_id=run.id,
                output_id=output.id if output else None,
                evidence_type=AiEvidenceType.TRACE,
                content_hash=self._hash_payload({"run_id": run.id, "status": run.status.value}),
                payload={
                    "run_id": run.id,
                    "status": run.status.value,
                    "retry_count": run.retry_count,
                    "trigger_mode": run.trigger_mode.value,
                    "selection_source": run.metrics.get("selection_source"),
                    "model_version_id": run.metrics.get("model_version_id"),
                    "started_at": run.started_at.isoformat(),
                    "finished_at": run.finished_at.isoformat() if run.finished_at else None,
                },
            ),
        ]
        if output is not None and output_payload is not None:
            records.append(
                AiEvidenceRecord(
                    tenant_id=tenant_id,
                    run_id=run.id,
                    output_id=output.id,
                    evidence_type=AiEvidenceType.OUTPUT_SNAPSHOT,
                    content_hash=self._hash_payload(output_payload),
                    payload=output_payload,
                )
            )
        session.add_all(records)

    def _execute_run(
        self,
        session: Session,
        *,
        tenant_id: str,
        job: AiAnalysisJob,
        actor_id: str,
        payload: AiAnalysisRunTriggerRequest,
        retry_of_run_id: str | None,
        retry_count: int,
    ) -> tuple[AiAnalysisRun, AiAnalysisOutput | None]:
        trigger_mode = payload.trigger_mode or job.trigger_mode
        run = AiAnalysisRun(
            tenant_id=tenant_id,
            job_id=job.id,
            retry_of_run_id=retry_of_run_id,
            retry_count=retry_count,
            status=AiRunStatus.RUNNING,
            trigger_mode=trigger_mode,
            triggered_by=actor_id,
        )
        session.add(run)
        session.flush()

        model_context = self._resolve_run_model_context(
            session,
            tenant_id=tenant_id,
            job=job,
            payload=payload,
            run_id=run.id,
        )
        input_payload, outcomes, alerts = self._build_input_context(session, tenant_id, job, payload.context)
        input_payload["model_selection"] = {
            "selection_source": model_context["selection_source"],
            "model_id": model_context["model_id"],
            "model_key": model_context["model_key"],
            "model_version_id": model_context["model_version_id"],
            "model_version": model_context["model_version"],
            "policy_snapshot": model_context["policy_snapshot"],
            "threshold_snapshot": model_context["threshold_snapshot"],
        }
        run.input_hash = self._hash_payload(input_payload)
        started_at = datetime.now(UTC)
        schedule_window_key = payload.context.get("schedule_window_key")
        if payload.force_fail:
            run.status = AiRunStatus.FAILED
            run.error_message = "forced failure for retry flow"
            run.metrics = {
                "duration_ms": int((datetime.now(UTC) - started_at).total_seconds() * 1000),
                "outcomes_total": len(outcomes),
                "alerts_total": len(alerts),
                "selection_source": model_context["selection_source"],
                "model_version_id": model_context["model_version_id"],
                "model_version": model_context["model_version"],
                "threshold_snapshot": model_context["threshold_snapshot"],
                "schedule_window_key": schedule_window_key if isinstance(schedule_window_key, str) else None,
            }
            run.finished_at = datetime.now(UTC)
            run.updated_at = datetime.now(UTC)
            self._write_evidence(
                session,
                tenant_id=tenant_id,
                run=run,
                output=None,
                job=job,
                model_snapshot={
                    "selection_source": model_context["selection_source"],
                    "policy_snapshot": model_context["policy_snapshot"],
                    "model_version_id": model_context["model_version_id"],
                    "provider": model_context["model_provider"],
                    "name": model_context["model_name"],
                    "version": model_context["model_version"],
                    "model_version_status": model_context["model_version_status"],
                    "threshold_config": model_context["threshold_snapshot"],
                },
                input_payload=input_payload,
                output_payload=None,
            )
            session.add(run)
            return run, None

        open_alerts = [item for item in alerts if item.status != AlertStatus.CLOSED]
        summary = (
            f"AI summary for job {job.id}: outcomes={len(outcomes)}, alerts={len(alerts)}, "
            f"open_alerts={len(open_alerts)}."
        )
        if open_alerts:
            suggestion = (
                "Prioritize open critical alerts, assign reviewer, and verify outcome status "
                "before closure."
            )
        else:
            suggestion = "No open alerts detected; continue scheduled verification and archive routine outcomes."

        output_payload = {
            "summary": summary,
            "suggestion": suggestion,
            "non_control_policy": {"flight_control_allowed": False},
            "source_stats": input_payload["stats"],
            "model_selection": input_payload["model_selection"],
        }
        run.output_hash = self._hash_payload(output_payload)
        run.status = AiRunStatus.SUCCEEDED
        run.metrics = {
            "duration_ms": int((datetime.now(UTC) - started_at).total_seconds() * 1000),
            "outcomes_total": len(outcomes),
            "alerts_total": len(alerts),
            "open_alerts_total": len(open_alerts),
            "selection_source": model_context["selection_source"],
            "model_version_id": model_context["model_version_id"],
            "model_version": model_context["model_version"],
            "threshold_snapshot": model_context["threshold_snapshot"],
            "schedule_window_key": schedule_window_key if isinstance(schedule_window_key, str) else None,
        }
        run.finished_at = datetime.now(UTC)
        run.updated_at = datetime.now(UTC)
        output = AiAnalysisOutput(
            tenant_id=tenant_id,
            job_id=job.id,
            run_id=run.id,
            summary_text=summary,
            suggestion_text=suggestion,
            payload=output_payload,
            control_allowed=False,
            review_status=AiOutputReviewStatus.PENDING_REVIEW,
        )
        session.add(run)
        session.add(output)
        session.flush()
        self._write_evidence(
            session,
            tenant_id=tenant_id,
            run=run,
            output=output,
            job=job,
            model_snapshot={
                "selection_source": model_context["selection_source"],
                "policy_snapshot": model_context["policy_snapshot"],
                "model_version_id": model_context["model_version_id"],
                "provider": model_context["model_provider"],
                "name": model_context["model_name"],
                "version": model_context["model_version"],
                "model_version_status": model_context["model_version_status"],
                "threshold_config": model_context["threshold_snapshot"],
            },
            input_payload=input_payload,
            output_payload=output_payload,
        )
        return run, output

    def trigger_run(
        self,
        tenant_id: str,
        job_id: str,
        actor_id: str,
        payload: AiAnalysisRunTriggerRequest,
    ) -> AiAnalysisRun:
        output: AiAnalysisOutput | None
        with self._session() as session:
            job = self._get_scoped_job(session, tenant_id, job_id)
            if job.status != AiJobStatus.ACTIVE:
                raise ConflictError("ai analysis job is not active")
            run, output = self._execute_run(
                session,
                tenant_id=tenant_id,
                job=job,
                actor_id=actor_id,
                payload=payload,
                retry_of_run_id=None,
                retry_count=0,
            )
            session.commit()
            session.refresh(run)

        if run.status == AiRunStatus.SUCCEEDED:
            event_bus.publish_dict(
                "ai.run.succeeded",
                tenant_id,
                {"job_id": run.job_id, "run_id": run.id, "output_id": output.id if output else None},
            )
        else:
            event_bus.publish_dict(
                "ai.run.failed",
                tenant_id,
                {"job_id": run.job_id, "run_id": run.id, "error_message": run.error_message},
            )
        return run

    def retry_run(
        self,
        tenant_id: str,
        run_id: str,
        actor_id: str,
        payload: AiAnalysisRunRetryRequest,
    ) -> AiAnalysisRun:
        output: AiAnalysisOutput | None
        with self._session() as session:
            previous = self._get_scoped_run(session, tenant_id, run_id)
            if previous.status != AiRunStatus.FAILED:
                raise ConflictError("only failed runs can be retried")
            if previous.retry_count >= self.MAX_RETRY_COUNT:
                raise ConflictError("retry limit reached")
            job = self._get_scoped_job(session, tenant_id, previous.job_id)
            run, output = self._execute_run(
                session,
                tenant_id=tenant_id,
                job=job,
                actor_id=actor_id,
                payload=AiAnalysisRunTriggerRequest(
                    force_fail=payload.force_fail,
                    trigger_mode=job.trigger_mode,
                    context=payload.context,
                ),
                retry_of_run_id=previous.id,
                retry_count=previous.retry_count + 1,
            )
            session.commit()
            session.refresh(run)

        if run.status == AiRunStatus.SUCCEEDED:
            event_bus.publish_dict(
                "ai.run.retry_succeeded",
                tenant_id,
                {"job_id": run.job_id, "run_id": run.id, "retry_of_run_id": run.retry_of_run_id},
            )
        else:
            event_bus.publish_dict(
                "ai.run.retry_failed",
                tenant_id,
                {
                    "job_id": run.job_id,
                    "run_id": run.id,
                    "retry_of_run_id": run.retry_of_run_id,
                    "error_message": run.error_message,
                },
            )
        return run

    def list_runs(self, tenant_id: str, job_id: str) -> list[AiAnalysisRun]:
        with self._session() as session:
            _ = self._get_scoped_job(session, tenant_id, job_id)
            rows = list(
                session.exec(
                    select(AiAnalysisRun)
                    .where(AiAnalysisRun.tenant_id == tenant_id)
                    .where(AiAnalysisRun.job_id == job_id)
                ).all()
            )
            return sorted(rows, key=lambda item: item.created_at, reverse=True)

    def list_outputs(
        self,
        tenant_id: str,
        *,
        job_id: str | None = None,
        run_id: str | None = None,
        review_status: AiOutputReviewStatus | None = None,
        viewer_user_id: str | None = None,
    ) -> list[AiAnalysisOutput]:
        with self._session() as session:
            statement = select(AiAnalysisOutput).where(AiAnalysisOutput.tenant_id == tenant_id)
            if job_id is not None:
                statement = statement.where(AiAnalysisOutput.job_id == job_id)
            if run_id is not None:
                statement = statement.where(AiAnalysisOutput.run_id == run_id)
            if review_status is not None:
                statement = statement.where(AiAnalysisOutput.review_status == review_status)
            rows = list(session.exec(statement).all())
            jobs = {
                item.id: item
                for item in session.exec(select(AiAnalysisJob).where(AiAnalysisJob.tenant_id == tenant_id)).all()
            }
            visible = []
            for item in rows:
                job = jobs.get(item.job_id)
                if job is None:
                    continue
                if self._is_visible(
                    session,
                    tenant_id,
                    viewer_user_id,
                    task_id=job.task_id,
                    mission_id=job.mission_id,
                ):
                    visible.append(item)
            return sorted(visible, key=lambda item: item.created_at, reverse=True)

    def get_output(self, tenant_id: str, output_id: str, viewer_user_id: str | None = None) -> AiAnalysisOutput:
        with self._session() as session:
            output = self._get_scoped_output(session, tenant_id, output_id)
            job = self._get_scoped_job(session, tenant_id, output.job_id)
            if not self._is_visible(
                session,
                tenant_id,
                viewer_user_id,
                task_id=job.task_id,
                mission_id=job.mission_id,
            ):
                raise NotFoundError("ai analysis output not found")
            return output

    def list_review_actions(self, tenant_id: str, output_id: str) -> list[AiOutputReviewAction]:
        with self._session() as session:
            output = self._get_scoped_output(session, tenant_id, output_id)
            rows = list(
                session.exec(
                    select(AiOutputReviewAction)
                    .where(AiOutputReviewAction.tenant_id == tenant_id)
                    .where(AiOutputReviewAction.output_id == output.id)
                ).all()
            )
            return sorted(rows, key=lambda item: item.created_at)

    def list_evidences(self, tenant_id: str, output_id: str) -> list[AiEvidenceRecord]:
        with self._session() as session:
            output = self._get_scoped_output(session, tenant_id, output_id)
            rows = list(
                session.exec(
                    select(AiEvidenceRecord)
                    .where(AiEvidenceRecord.tenant_id == tenant_id)
                    .where(AiEvidenceRecord.output_id == output.id)
                ).all()
            )
            return sorted(rows, key=lambda item: item.created_at)

    def review_output(
        self,
        tenant_id: str,
        output_id: str,
        actor_id: str,
        payload: AiOutputReviewActionCreate,
    ) -> tuple[AiAnalysisOutput, AiOutputReviewAction]:
        with self._session() as session:
            output = self._get_scoped_output(session, tenant_id, output_id)
            if payload.action_type == AiReviewActionType.OVERRIDE and not payload.override_payload:
                raise ConflictError("override action requires override_payload")

            if payload.action_type == AiReviewActionType.APPROVE:
                next_status = AiOutputReviewStatus.APPROVED
            elif payload.action_type == AiReviewActionType.REJECT:
                next_status = AiOutputReviewStatus.REJECTED
            else:
                next_status = AiOutputReviewStatus.OVERRIDDEN

            previous_status = output.review_status
            output.review_status = next_status
            output.reviewed_by = actor_id
            output.reviewed_at = datetime.now(UTC)
            output.review_note = payload.note
            output.updated_at = datetime.now(UTC)
            if payload.action_type == AiReviewActionType.OVERRIDE:
                output.override_payload = payload.override_payload
                override_summary = payload.override_payload.get("summary")
                override_suggestion = payload.override_payload.get("suggestion")
                if isinstance(override_summary, str) and override_summary.strip():
                    output.summary_text = override_summary.strip()
                if isinstance(override_suggestion, str) and override_suggestion.strip():
                    output.suggestion_text = override_suggestion.strip()
                merged_payload = dict(output.payload)
                merged_payload["human_override"] = payload.override_payload
                output.payload = merged_payload

            action = AiOutputReviewAction(
                tenant_id=tenant_id,
                output_id=output.id,
                run_id=output.run_id,
                action_type=payload.action_type,
                note=payload.note,
                actor_id=actor_id,
                detail={
                    "from_status": previous_status.value,
                    "to_status": next_status.value,
                    "review_payload": payload.detail,
                },
            )
            session.add(output)
            session.add(action)
            session.commit()
            session.refresh(output)
            session.refresh(action)

        event_bus.publish_dict(
            "ai.output.reviewed",
            tenant_id,
            {
                "output_id": output.id,
                "run_id": output.run_id,
                "action_type": action.action_type,
                "review_status": output.review_status,
                "reviewed_by": output.reviewed_by,
            },
        )
        return output, action

    def get_output_review(
        self,
        tenant_id: str,
        output_id: str,
        viewer_user_id: str | None = None,
    ) -> tuple[AiAnalysisOutput, list[AiOutputReviewAction], list[AiEvidenceRecord]]:
        with self._session() as session:
            output = self._get_scoped_output(session, tenant_id, output_id)
            job = self._get_scoped_job(session, tenant_id, output.job_id)
            if not self._is_visible(
                session,
                tenant_id,
                viewer_user_id,
                task_id=job.task_id,
                mission_id=job.mission_id,
            ):
                raise NotFoundError("ai analysis output not found")
        actions = self.list_review_actions(tenant_id, output_id)
        evidences = self.list_evidences(tenant_id, output_id)
        return output, actions, evidences
