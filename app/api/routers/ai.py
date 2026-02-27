from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.api.deps import get_current_claims, require_any_perm
from app.domain.models import (
    AiAnalysisJobBindModelVersionRequest,
    AiAnalysisJobCreate,
    AiAnalysisJobRead,
    AiAnalysisOutputRead,
    AiAnalysisRunRead,
    AiAnalysisRunRetryRequest,
    AiAnalysisRunTriggerRequest,
    AiEvaluationCompareRead,
    AiEvaluationRecomputeRequest,
    AiEvaluationSummaryRead,
    AiEvidenceRecordRead,
    AiModelCatalogCreate,
    AiModelCatalogRead,
    AiModelRolloutPolicyRead,
    AiModelRolloutPolicyUpsertRequest,
    AiModelRolloutRollbackRequest,
    AiModelVersionCreate,
    AiModelVersionPromoteRequest,
    AiModelVersionRead,
    AiModelVersionStatus,
    AiOutputReviewActionCreate,
    AiOutputReviewActionRead,
    AiOutputReviewRead,
    AiOutputReviewStatus,
    AiScheduleTickRead,
    AiScheduleTickRequest,
)
from app.domain.permissions import (
    PERM_AI_READ,
    PERM_AI_WRITE,
    PERM_REPORTING_READ,
    PERM_REPORTING_WRITE,
)
from app.infra.audit import set_audit_context
from app.services.ai_service import AiAssistantService, ConflictError, NotFoundError

router = APIRouter()


def get_ai_service() -> AiAssistantService:
    return AiAssistantService()


Claims = Annotated[dict[str, Any], Depends(get_current_claims)]
Service = Annotated[AiAssistantService, Depends(get_ai_service)]


def _handle_ai_error(exc: Exception) -> None:
    if isinstance(exc, NotFoundError):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    if isinstance(exc, ConflictError):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    raise exc


@router.post(
    "/models",
    response_model=AiModelCatalogRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_any_perm(PERM_AI_WRITE, PERM_REPORTING_WRITE))],
)
def create_model_catalog(
    payload: AiModelCatalogCreate,
    request: Request,
    claims: Claims,
    service: Service,
) -> AiModelCatalogRead:
    try:
        row = service.create_model_catalog(claims["tenant_id"], claims["sub"], payload)
        set_audit_context(
            request,
            action="ai.model.catalog.create",
            resource="/api/ai/models",
            detail={"what": {"model_id": row.id, "model_key": row.model_key}},
        )
        return AiModelCatalogRead.model_validate(row)
    except (NotFoundError, ConflictError) as exc:
        _handle_ai_error(exc)
        raise


@router.get(
    "/models",
    response_model=list[AiModelCatalogRead],
    dependencies=[Depends(require_any_perm(PERM_AI_READ, PERM_REPORTING_READ))],
)
def list_model_catalogs(
    claims: Claims,
    service: Service,
    model_key: str | None = None,
    provider: str | None = None,
) -> list[AiModelCatalogRead]:
    rows = service.list_model_catalogs(
        claims["tenant_id"],
        model_key=model_key,
        provider=provider,
    )
    return [AiModelCatalogRead.model_validate(item) for item in rows]


@router.post(
    "/models/{model_id}/versions",
    response_model=AiModelVersionRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_any_perm(PERM_AI_WRITE, PERM_REPORTING_WRITE))],
)
def create_model_version(
    model_id: str,
    payload: AiModelVersionCreate,
    request: Request,
    claims: Claims,
    service: Service,
) -> AiModelVersionRead:
    try:
        row = service.create_model_version(claims["tenant_id"], model_id, claims["sub"], payload)
        set_audit_context(
            request,
            action="ai.model.version.create",
            resource=f"/api/ai/models/{model_id}/versions",
            detail={"what": {"version_id": row.id, "version": row.version, "status": row.status.value}},
        )
        return AiModelVersionRead.model_validate(row)
    except (NotFoundError, ConflictError) as exc:
        _handle_ai_error(exc)
        raise


@router.get(
    "/models/{model_id}/versions",
    response_model=list[AiModelVersionRead],
    dependencies=[Depends(require_any_perm(PERM_AI_READ, PERM_REPORTING_READ))],
)
def list_model_versions(
    model_id: str,
    claims: Claims,
    service: Service,
    status_filter: AiModelVersionStatus | None = None,
) -> list[AiModelVersionRead]:
    try:
        rows = service.list_model_versions(claims["tenant_id"], model_id, status=status_filter)
        return [AiModelVersionRead.model_validate(item) for item in rows]
    except (NotFoundError, ConflictError) as exc:
        _handle_ai_error(exc)
        raise


@router.post(
    "/models/{model_id}/versions/{version_id}:promote",
    response_model=AiModelVersionRead,
    dependencies=[Depends(require_any_perm(PERM_AI_WRITE, PERM_REPORTING_WRITE))],
)
def promote_model_version(
    model_id: str,
    version_id: str,
    payload: AiModelVersionPromoteRequest,
    request: Request,
    claims: Claims,
    service: Service,
) -> AiModelVersionRead:
    try:
        row = service.promote_model_version(
            claims["tenant_id"],
            model_id,
            version_id,
            claims["sub"],
            payload,
        )
        set_audit_context(
            request,
            action="ai.model.version.promote",
            resource=f"/api/ai/models/{model_id}/versions/{version_id}:promote",
            detail={"what": {"version_id": row.id, "target_status": row.status.value}},
        )
        return AiModelVersionRead.model_validate(row)
    except (NotFoundError, ConflictError) as exc:
        _handle_ai_error(exc)
        raise


@router.get(
    "/models/{model_id}/rollout-policy",
    response_model=AiModelRolloutPolicyRead,
    dependencies=[Depends(require_any_perm(PERM_AI_READ, PERM_REPORTING_READ))],
)
def get_rollout_policy(model_id: str, claims: Claims, service: Service) -> AiModelRolloutPolicyRead:
    try:
        row = service.get_rollout_policy(claims["tenant_id"], model_id)
        return AiModelRolloutPolicyRead.model_validate(row)
    except (NotFoundError, ConflictError) as exc:
        _handle_ai_error(exc)
        raise


@router.put(
    "/models/{model_id}/rollout-policy",
    response_model=AiModelRolloutPolicyRead,
    dependencies=[Depends(require_any_perm(PERM_AI_WRITE, PERM_REPORTING_WRITE))],
)
def upsert_rollout_policy(
    model_id: str,
    payload: AiModelRolloutPolicyUpsertRequest,
    request: Request,
    claims: Claims,
    service: Service,
) -> AiModelRolloutPolicyRead:
    try:
        row = service.upsert_rollout_policy(claims["tenant_id"], model_id, claims["sub"], payload)
        set_audit_context(
            request,
            action="ai.model.rollout.upsert",
            resource=f"/api/ai/models/{model_id}/rollout-policy",
            detail={
                "what": {
                    "policy_id": row.id,
                    "default_version_id": row.default_version_id,
                    "is_active": row.is_active,
                }
            },
        )
        return AiModelRolloutPolicyRead.model_validate(row)
    except (NotFoundError, ConflictError) as exc:
        _handle_ai_error(exc)
        raise


@router.post(
    "/models/{model_id}/rollout-policy:rollback",
    response_model=AiModelRolloutPolicyRead,
    dependencies=[Depends(require_any_perm(PERM_AI_WRITE, PERM_REPORTING_WRITE))],
)
def rollback_rollout_policy(
    model_id: str,
    payload: AiModelRolloutRollbackRequest,
    request: Request,
    claims: Claims,
    service: Service,
) -> AiModelRolloutPolicyRead:
    try:
        row = service.rollback_rollout_policy(claims["tenant_id"], model_id, claims["sub"], payload)
        set_audit_context(
            request,
            action="ai.model.rollout.rollback",
            resource=f"/api/ai/models/{model_id}/rollout-policy:rollback",
            detail={"what": {"target_version_id": payload.target_version_id, "policy_id": row.id}},
        )
        return AiModelRolloutPolicyRead.model_validate(row)
    except (NotFoundError, ConflictError) as exc:
        _handle_ai_error(exc)
        raise


@router.post(
    "/evaluations:recompute",
    response_model=list[AiEvaluationSummaryRead],
    dependencies=[Depends(require_any_perm(PERM_AI_WRITE, PERM_REPORTING_WRITE))],
)
def recompute_evaluations(
    payload: AiEvaluationRecomputeRequest,
    request: Request,
    claims: Claims,
    service: Service,
) -> list[AiEvaluationSummaryRead]:
    rows = service.recompute_evaluations(claims["tenant_id"], payload)
    set_audit_context(
        request,
        action="ai.evaluation.recompute",
        resource="/api/ai/evaluations:recompute",
        detail={
            "what": {
                "model_id": payload.model_id,
                "job_id": payload.job_id,
                "from_ts": payload.from_ts.isoformat() if payload.from_ts else None,
                "to_ts": payload.to_ts.isoformat() if payload.to_ts else None,
                "summary_count": len(rows),
            }
        },
    )
    return rows


@router.get(
    "/evaluations/compare",
    response_model=AiEvaluationCompareRead,
    dependencies=[Depends(require_any_perm(PERM_AI_READ, PERM_REPORTING_READ))],
)
def compare_evaluations(
    left_version_id: str,
    right_version_id: str,
    claims: Claims,
    service: Service,
    job_id: str | None = None,
    from_ts: datetime | None = None,
    to_ts: datetime | None = None,
) -> AiEvaluationCompareRead:
    try:
        return service.compare_evaluations(
            claims["tenant_id"],
            left_version_id=left_version_id,
            right_version_id=right_version_id,
            job_id=job_id,
            from_ts=from_ts,
            to_ts=to_ts,
        )
    except (NotFoundError, ConflictError) as exc:
        _handle_ai_error(exc)
        raise


@router.post(
    "/jobs",
    response_model=AiAnalysisJobRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_any_perm(PERM_AI_WRITE, PERM_REPORTING_WRITE))],
)
def create_job(payload: AiAnalysisJobCreate, claims: Claims, service: Service) -> AiAnalysisJobRead:
    try:
        row = service.create_job(claims["tenant_id"], claims["sub"], payload)
        return AiAnalysisJobRead.model_validate(row)
    except (NotFoundError, ConflictError) as exc:
        _handle_ai_error(exc)
        raise


@router.post(
    "/jobs/{job_id}:bind-model-version",
    response_model=AiAnalysisJobRead,
    dependencies=[Depends(require_any_perm(PERM_AI_WRITE, PERM_REPORTING_WRITE))],
)
def bind_job_model_version(
    job_id: str,
    payload: AiAnalysisJobBindModelVersionRequest,
    request: Request,
    claims: Claims,
    service: Service,
) -> AiAnalysisJobRead:
    try:
        row = service.bind_job_model_version(claims["tenant_id"], job_id, claims["sub"], payload)
        set_audit_context(
            request,
            action="ai.job.bind_model_version",
            resource=f"/api/ai/jobs/{job_id}:bind-model-version",
            detail={"what": {"job_id": row.id, "model_version_id": row.model_version_id}},
        )
        return AiAnalysisJobRead.model_validate(row)
    except (NotFoundError, ConflictError) as exc:
        _handle_ai_error(exc)
        raise


@router.post(
    "/jobs:schedule-tick",
    response_model=AiScheduleTickRead,
    dependencies=[Depends(require_any_perm(PERM_AI_WRITE, PERM_REPORTING_WRITE))],
)
def schedule_tick(
    payload: AiScheduleTickRequest,
    request: Request,
    claims: Claims,
    service: Service,
) -> AiScheduleTickRead:
    try:
        row = service.schedule_tick(claims["tenant_id"], claims["sub"], payload)
        set_audit_context(
            request,
            action="ai.schedule.tick",
            resource="/api/ai/jobs:schedule-tick",
            detail={
                "what": {
                    "window_key": row.window_key,
                    "scanned_jobs": row.scanned_jobs,
                    "triggered_jobs": row.triggered_jobs,
                    "skipped_jobs": row.skipped_jobs,
                }
            },
        )
        return row
    except (NotFoundError, ConflictError) as exc:
        _handle_ai_error(exc)
        raise


@router.get(
    "/jobs",
    response_model=list[AiAnalysisJobRead],
    dependencies=[Depends(require_any_perm(PERM_AI_READ, PERM_REPORTING_READ))],
)
def list_jobs(
    claims: Claims,
    service: Service,
    task_id: str | None = None,
    mission_id: str | None = None,
) -> list[AiAnalysisJobRead]:
    rows = service.list_jobs(
        claims["tenant_id"],
        task_id=task_id,
        mission_id=mission_id,
        viewer_user_id=claims["sub"],
    )
    return [AiAnalysisJobRead.model_validate(item) for item in rows]


@router.post(
    "/jobs/{job_id}/runs",
    response_model=AiAnalysisRunRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_any_perm(PERM_AI_WRITE, PERM_REPORTING_WRITE))],
)
def trigger_run(
    job_id: str,
    payload: AiAnalysisRunTriggerRequest,
    claims: Claims,
    service: Service,
) -> AiAnalysisRunRead:
    try:
        row = service.trigger_run(claims["tenant_id"], job_id, claims["sub"], payload)
        return AiAnalysisRunRead.model_validate(row)
    except (NotFoundError, ConflictError) as exc:
        _handle_ai_error(exc)
        raise


@router.get(
    "/jobs/{job_id}/runs",
    response_model=list[AiAnalysisRunRead],
    dependencies=[Depends(require_any_perm(PERM_AI_READ, PERM_REPORTING_READ))],
)
def list_runs(job_id: str, claims: Claims, service: Service) -> list[AiAnalysisRunRead]:
    try:
        rows = service.list_runs(claims["tenant_id"], job_id)
        return [AiAnalysisRunRead.model_validate(item) for item in rows]
    except (NotFoundError, ConflictError) as exc:
        _handle_ai_error(exc)
        raise


@router.post(
    "/runs/{run_id}/retry",
    response_model=AiAnalysisRunRead,
    dependencies=[Depends(require_any_perm(PERM_AI_WRITE, PERM_REPORTING_WRITE))],
)
def retry_run(
    run_id: str,
    payload: AiAnalysisRunRetryRequest,
    claims: Claims,
    service: Service,
) -> AiAnalysisRunRead:
    try:
        row = service.retry_run(claims["tenant_id"], run_id, claims["sub"], payload)
        return AiAnalysisRunRead.model_validate(row)
    except (NotFoundError, ConflictError) as exc:
        _handle_ai_error(exc)
        raise


@router.get(
    "/outputs",
    response_model=list[AiAnalysisOutputRead],
    dependencies=[Depends(require_any_perm(PERM_AI_READ, PERM_REPORTING_READ))],
)
def list_outputs(
    claims: Claims,
    service: Service,
    job_id: str | None = None,
    run_id: str | None = None,
    review_status: AiOutputReviewStatus | None = None,
) -> list[AiAnalysisOutputRead]:
    rows = service.list_outputs(
        claims["tenant_id"],
        job_id=job_id,
        run_id=run_id,
        review_status=review_status,
        viewer_user_id=claims["sub"],
    )
    return [AiAnalysisOutputRead.model_validate(item) for item in rows]


@router.get(
    "/outputs/{output_id}",
    response_model=AiAnalysisOutputRead,
    dependencies=[Depends(require_any_perm(PERM_AI_READ, PERM_REPORTING_READ))],
)
def get_output(output_id: str, claims: Claims, service: Service) -> AiAnalysisOutputRead:
    try:
        row = service.get_output(claims["tenant_id"], output_id, viewer_user_id=claims["sub"])
        return AiAnalysisOutputRead.model_validate(row)
    except (NotFoundError, ConflictError) as exc:
        _handle_ai_error(exc)
        raise


@router.post(
    "/outputs/{output_id}/review",
    response_model=AiOutputReviewActionRead,
    dependencies=[Depends(require_any_perm(PERM_AI_WRITE, PERM_REPORTING_WRITE))],
)
def review_output(
    output_id: str,
    payload: AiOutputReviewActionCreate,
    request: Request,
    claims: Claims,
    service: Service,
) -> AiOutputReviewActionRead:
    try:
        output, action = service.review_output(claims["tenant_id"], output_id, claims["sub"], payload)
        set_audit_context(
            request,
            action="ai.output.review",
            resource=f"/api/ai/outputs/{output_id}/review",
            detail={
                "what": {
                    "output_id": output.id,
                    "run_id": output.run_id,
                    "action_type": action.action_type.value,
                    "review_status": output.review_status.value,
                }
            },
        )
        return AiOutputReviewActionRead.model_validate(action)
    except (NotFoundError, ConflictError) as exc:
        _handle_ai_error(exc)
        raise


@router.get(
    "/outputs/{output_id}/review",
    response_model=AiOutputReviewRead,
    dependencies=[Depends(require_any_perm(PERM_AI_READ, PERM_REPORTING_READ))],
)
def get_output_review(output_id: str, claims: Claims, service: Service) -> AiOutputReviewRead:
    try:
        output, actions, evidences = service.get_output_review(
            claims["tenant_id"],
            output_id,
            viewer_user_id=claims["sub"],
        )
        return AiOutputReviewRead(
            output=AiAnalysisOutputRead.model_validate(output),
            actions=[AiOutputReviewActionRead.model_validate(item) for item in actions],
            evidences=[AiEvidenceRecordRead.model_validate(item) for item in evidences],
        )
    except (NotFoundError, ConflictError) as exc:
        _handle_ai_error(exc)
        raise
