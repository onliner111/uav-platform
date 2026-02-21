from __future__ import annotations

import json
from pathlib import Path

from sqlmodel import Session, select

from app.domain.models import ApprovalRecord, ApprovalRecordCreate, AuditLog
from app.infra.db import get_engine
from app.infra.events import event_bus


class ComplianceError(Exception):
    pass


class NotFoundError(ComplianceError):
    pass


class ComplianceService:
    def _session(self) -> Session:
        return Session(get_engine(), expire_on_commit=False)

    def create_approval(
        self,
        tenant_id: str,
        actor_id: str,
        payload: ApprovalRecordCreate,
    ) -> ApprovalRecord:
        with self._session() as session:
            record = ApprovalRecord(
                tenant_id=tenant_id,
                entity_type=payload.entity_type,
                entity_id=payload.entity_id,
                status=payload.status,
                approved_by=actor_id,
            )
            session.add(record)
            session.commit()
            session.refresh(record)
        event_bus.publish_dict(
            "approval.recorded",
            tenant_id,
            {"approval_id": record.id, "entity_type": record.entity_type, "status": record.status},
        )
        return record

    def list_approvals(
        self,
        tenant_id: str,
        entity_type: str | None = None,
        entity_id: str | None = None,
    ) -> list[ApprovalRecord]:
        with self._session() as session:
            statement = select(ApprovalRecord).where(ApprovalRecord.tenant_id == tenant_id)
            if entity_type is not None:
                statement = statement.where(ApprovalRecord.entity_type == entity_type)
            if entity_id is not None:
                statement = statement.where(ApprovalRecord.entity_id == entity_id)
            return list(session.exec(statement).all())

    def export_audit(self, tenant_id: str) -> str:
        with self._session() as session:
            rows = list(session.exec(select(AuditLog).where(AuditLog.tenant_id == tenant_id)).all())
        export_dir = Path("logs") / "exports"
        export_dir.mkdir(parents=True, exist_ok=True)
        output_file = export_dir / f"audit_{tenant_id}.json"
        payload = [
            {
                "id": item.id,
                "action": item.action,
                "resource": item.resource,
                "method": item.method,
                "status_code": item.status_code,
                "ts": item.ts.isoformat(),
                "actor_id": item.actor_id,
            }
            for item in rows
        ]
        output_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return str(output_file)
