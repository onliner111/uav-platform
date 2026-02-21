from __future__ import annotations

from datetime import UTC, datetime

from sqlmodel import Session, select

from app.domain.models import (
    AlertRecord,
    AlertStatus,
    DashboardStatsRead,
    Defect,
    Drone,
    InspectionObservation,
    InspectionTask,
)
from app.infra.db import get_engine


class DashboardService:
    def _session(self) -> Session:
        return Session(get_engine(), expire_on_commit=False)

    def get_stats(self, tenant_id: str) -> DashboardStatsRead:
        with self._session() as session:
            drones = list(session.exec(select(Drone).where(Drone.tenant_id == tenant_id)).all())
            tasks = list(session.exec(select(InspectionTask).where(InspectionTask.tenant_id == tenant_id)).all())
            defects = list(session.exec(select(Defect).where(Defect.tenant_id == tenant_id)).all())
            alerts = list(
                session.exec(
                    select(AlertRecord)
                    .where(AlertRecord.tenant_id == tenant_id)
                    .where(AlertRecord.status == AlertStatus.OPEN)
                ).all()
            )
        today = datetime.now(UTC).date()
        today_inspections = len([item for item in tasks if item.created_at.date() == today])
        return DashboardStatsRead(
            online_devices=len(drones),
            today_inspections=today_inspections,
            defects_total=len(defects),
            realtime_alerts=len(alerts),
        )

    def latest_observations(self, tenant_id: str, limit: int = 100) -> list[InspectionObservation]:
        with self._session() as session:
            statement = select(InspectionObservation).where(InspectionObservation.tenant_id == tenant_id)
            rows = list(session.exec(statement).all())
        return rows[:limit]
