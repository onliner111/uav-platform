from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.api.deps import get_current_claims, require_perm
from app.domain.models import (
    AiAnalysisJobCreate,
    AiAnalysisJobRead,
    AiAnalysisOutputRead,
    AiAnalysisRunRead,
    AiAnalysisRunRetryRequest,
    AiAnalysisRunTriggerRequest,
    AiEvidenceRecordRead,
    AiOutputReviewActionCreate,
    AiOutputReviewActionRead,
    AiOutputReviewRead,
    AiOutputReviewStatus,
)
from app.domain.permissions import PERM_REPORTING_READ, PERM_REPORTING_WRITE
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
    "/jobs",
    response_model=AiAnalysisJobRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_perm(PERM_REPORTING_WRITE))],
)
def create_job(payload: AiAnalysisJobCreate, claims: Claims, service: Service) -> AiAnalysisJobRead:
    try:
        row = service.create_job(claims["tenant_id"], claims["sub"], payload)
        return AiAnalysisJobRead.model_validate(row)
    except (NotFoundError, ConflictError) as exc:
        _handle_ai_error(exc)
        raise


@router.get(
    "/jobs",
    response_model=list[AiAnalysisJobRead],
    dependencies=[Depends(require_perm(PERM_REPORTING_READ))],
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
    dependencies=[Depends(require_perm(PERM_REPORTING_WRITE))],
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
    dependencies=[Depends(require_perm(PERM_REPORTING_READ))],
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
    dependencies=[Depends(require_perm(PERM_REPORTING_WRITE))],
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
    dependencies=[Depends(require_perm(PERM_REPORTING_READ))],
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
    dependencies=[Depends(require_perm(PERM_REPORTING_READ))],
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
    dependencies=[Depends(require_perm(PERM_REPORTING_WRITE))],
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
    dependencies=[Depends(require_perm(PERM_REPORTING_READ))],
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
