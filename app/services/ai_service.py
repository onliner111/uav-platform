from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any

from sqlmodel import Session, select

from app.domain.models import (
    AiAnalysisJob,
    AiAnalysisJobCreate,
    AiAnalysisOutput,
    AiAnalysisRun,
    AiAnalysisRunRetryRequest,
    AiAnalysisRunTriggerRequest,
    AiEvidenceRecord,
    AiEvidenceType,
    AiJobStatus,
    AiOutputReviewAction,
    AiOutputReviewActionCreate,
    AiOutputReviewStatus,
    AiReviewActionType,
    AiRunStatus,
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

    def create_job(self, tenant_id: str, actor_id: str, payload: AiAnalysisJobCreate) -> AiAnalysisJob:
        with self._session() as session:
            if payload.task_id is not None:
                _ = self._get_scoped_task(session, tenant_id, payload.task_id)
            if payload.mission_id is not None:
                _ = self._get_scoped_mission(session, tenant_id, payload.mission_id)

            row = AiAnalysisJob(
                tenant_id=tenant_id,
                task_id=payload.task_id,
                mission_id=payload.mission_id,
                topic=payload.topic,
                job_type=payload.job_type,
                trigger_mode=payload.trigger_mode,
                status=AiJobStatus.ACTIVE,
                model_provider=payload.model_provider,
                model_name=payload.model_name,
                model_version=payload.model_version,
                threshold_config=payload.threshold_config,
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
        input_payload: dict[str, Any],
        output_payload: dict[str, Any] | None,
    ) -> None:
        model_payload = {
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

        input_payload, outcomes, alerts = self._build_input_context(session, tenant_id, job, payload.context)
        run.input_hash = self._hash_payload(input_payload)
        started_at = datetime.now(UTC)
        if payload.force_fail:
            run.status = AiRunStatus.FAILED
            run.error_message = "forced failure for retry flow"
            run.metrics = {
                "duration_ms": int((datetime.now(UTC) - started_at).total_seconds() * 1000),
                "outcomes_total": len(outcomes),
                "alerts_total": len(alerts),
            }
            run.finished_at = datetime.now(UTC)
            run.updated_at = datetime.now(UTC)
            self._write_evidence(
                session,
                tenant_id=tenant_id,
                run=run,
                output=None,
                job=job,
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
        }
        run.output_hash = self._hash_payload(output_payload)
        run.status = AiRunStatus.SUCCEEDED
        run.metrics = {
            "duration_ms": int((datetime.now(UTC) - started_at).total_seconds() * 1000),
            "outcomes_total": len(outcomes),
            "alerts_total": len(alerts),
            "open_alerts_total": len(open_alerts),
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
