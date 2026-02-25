from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from sqlmodel import Session, select

from app.domain.models import (
    DataAccessPolicy,
    DataScopeMode,
    Defect,
    Incident,
    InspectionTask,
    Mission,
    TaskCenterTask,
)


@dataclass(frozen=True)
class DataPerimeterScope:
    mode: DataScopeMode = DataScopeMode.ALL
    org_unit_ids: frozenset[str] = frozenset()
    project_codes: frozenset[str] = frozenset()
    area_codes: frozenset[str] = frozenset()
    task_ids: frozenset[str] = frozenset()

    def is_all(self) -> bool:
        return self.mode == DataScopeMode.ALL


class DataPerimeterService:
    def _normalize_values(self, values: Iterable[str]) -> frozenset[str]:
        normalized = {item.strip() for item in values if isinstance(item, str) and item.strip()}
        return frozenset(normalized)

    def resolve_scope(self, session: Session, tenant_id: str, user_id: str | None) -> DataPerimeterScope:
        if user_id is None:
            return DataPerimeterScope(mode=DataScopeMode.ALL)
        policy = session.exec(
            select(DataAccessPolicy)
            .where(DataAccessPolicy.tenant_id == tenant_id)
            .where(DataAccessPolicy.user_id == user_id)
        ).first()
        if policy is None or policy.scope_mode == DataScopeMode.ALL:
            return DataPerimeterScope(mode=DataScopeMode.ALL)
        return DataPerimeterScope(
            mode=DataScopeMode.SCOPED,
            org_unit_ids=self._normalize_values(policy.org_unit_ids),
            project_codes=self._normalize_values(policy.project_codes),
            area_codes=self._normalize_values(policy.area_codes),
            task_ids=self._normalize_values(policy.task_ids),
        )

    def allows(
        self,
        scope: DataPerimeterScope,
        *,
        org_unit_id: str | None,
        project_code: str | None,
        area_code: str | None,
        task_id: str | None,
    ) -> bool:
        if scope.is_all():
            return True
        if scope.org_unit_ids and org_unit_id not in scope.org_unit_ids:
            return False
        if scope.project_codes and project_code not in scope.project_codes:
            return False
        if scope.area_codes and area_code not in scope.area_codes:
            return False
        return not (scope.task_ids and task_id not in scope.task_ids)

    def mission_visible(self, mission: Mission, scope: DataPerimeterScope) -> bool:
        return self.allows(
            scope,
            org_unit_id=mission.org_unit_id,
            project_code=mission.project_code,
            area_code=mission.area_code,
            task_id=mission.id,
        )

    def inspection_task_visible(self, task: InspectionTask, scope: DataPerimeterScope) -> bool:
        return self.allows(
            scope,
            org_unit_id=task.org_unit_id,
            project_code=task.project_code,
            area_code=task.area_code,
            task_id=task.id,
        )

    def defect_visible(self, defect: Defect, scope: DataPerimeterScope) -> bool:
        return self.allows(
            scope,
            org_unit_id=defect.org_unit_id,
            project_code=defect.project_code,
            area_code=defect.area_code,
            task_id=defect.task_id,
        )

    def incident_visible(self, incident: Incident, scope: DataPerimeterScope) -> bool:
        return self.allows(
            scope,
            org_unit_id=incident.org_unit_id,
            project_code=incident.project_code,
            area_code=incident.area_code,
            task_id=incident.linked_task_id,
        )

    def task_center_visible(self, task: TaskCenterTask, scope: DataPerimeterScope) -> bool:
        return self.allows(
            scope,
            org_unit_id=task.org_unit_id,
            project_code=task.project_code,
            area_code=task.area_code,
            task_id=task.id,
        )
