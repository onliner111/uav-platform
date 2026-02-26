from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field

from sqlmodel import Session, col, select

from app.domain.models import (
    Asset,
    DataAccessPolicy,
    DataScopeMode,
    Defect,
    Drone,
    Incident,
    InspectionTask,
    Mission,
    RoleDataAccessPolicy,
    TaskCenterTask,
    UserRole,
)


@dataclass(frozen=True)
class DataPerimeterRule:
    org_unit_ids: frozenset[str] = frozenset()
    project_codes: frozenset[str] = frozenset()
    area_codes: frozenset[str] = frozenset()
    task_ids: frozenset[str] = frozenset()
    resource_ids: frozenset[str] = frozenset()

    def has_constraints(self) -> bool:
        return any(
            (
                self.org_unit_ids,
                self.project_codes,
                self.area_codes,
                self.task_ids,
                self.resource_ids,
            )
        )


@dataclass(frozen=True)
class DataPerimeterScope:
    mode: DataScopeMode = DataScopeMode.ALL
    explicit_deny: DataPerimeterRule = field(default_factory=DataPerimeterRule)
    explicit_allow: DataPerimeterRule = field(default_factory=DataPerimeterRule)
    inherited_allow: DataPerimeterRule = field(default_factory=DataPerimeterRule)
    inherited_allow_all: bool = False

    def is_all(self) -> bool:
        return self.mode == DataScopeMode.ALL


class DataPerimeterService:
    def _normalize_values(self, values: Iterable[str]) -> frozenset[str]:
        normalized = {item.strip() for item in values if isinstance(item, str) and item.strip()}
        return frozenset(normalized)

    def _make_rule(
        self,
        *,
        org_unit_ids: Iterable[str],
        project_codes: Iterable[str],
        area_codes: Iterable[str],
        task_ids: Iterable[str],
        resource_ids: Iterable[str],
    ) -> DataPerimeterRule:
        return DataPerimeterRule(
            org_unit_ids=self._normalize_values(org_unit_ids),
            project_codes=self._normalize_values(project_codes),
            area_codes=self._normalize_values(area_codes),
            task_ids=self._normalize_values(task_ids),
            resource_ids=self._normalize_values(resource_ids),
        )

    def _rule_matches(
        self,
        rule: DataPerimeterRule,
        *,
        org_unit_id: str | None,
        project_code: str | None,
        area_code: str | None,
        task_id: str | None,
        resource_id: str | None,
    ) -> bool:
        if rule.org_unit_ids and org_unit_id is not None and org_unit_id not in rule.org_unit_ids:
            return False
        if rule.project_codes and project_code is not None and project_code not in rule.project_codes:
            return False
        if rule.area_codes and area_code is not None and area_code not in rule.area_codes:
            return False
        if rule.task_ids and task_id is not None and task_id not in rule.task_ids:
            return False
        return not (rule.resource_ids and resource_id is not None and resource_id not in rule.resource_ids)

    def resolve_scope(self, session: Session, tenant_id: str, user_id: str | None) -> DataPerimeterScope:
        if user_id is None:
            return DataPerimeterScope(mode=DataScopeMode.ALL)

        user_policy = session.exec(
            select(DataAccessPolicy)
            .where(DataAccessPolicy.tenant_id == tenant_id)
            .where(DataAccessPolicy.user_id == user_id)
        ).first()

        mode = DataScopeMode.ALL if user_policy is None else user_policy.scope_mode
        explicit_allow = self._make_rule(
            org_unit_ids=[] if user_policy is None else user_policy.org_unit_ids,
            project_codes=[] if user_policy is None else user_policy.project_codes,
            area_codes=[] if user_policy is None else user_policy.area_codes,
            task_ids=[] if user_policy is None else user_policy.task_ids,
            resource_ids=[] if user_policy is None else user_policy.resource_ids,
        )
        explicit_deny = self._make_rule(
            org_unit_ids=[] if user_policy is None else user_policy.denied_org_unit_ids,
            project_codes=[] if user_policy is None else user_policy.denied_project_codes,
            area_codes=[] if user_policy is None else user_policy.denied_area_codes,
            task_ids=[] if user_policy is None else user_policy.denied_task_ids,
            resource_ids=[] if user_policy is None else user_policy.denied_resource_ids,
        )

        inherited_allow = DataPerimeterRule()
        inherited_allow_all = False
        role_ids = list(
            session.exec(
                select(UserRole.role_id)
                .where(UserRole.tenant_id == tenant_id)
                .where(UserRole.user_id == user_id)
            ).all()
        )
        if role_ids:
            role_policies = list(
                session.exec(
                    select(RoleDataAccessPolicy)
                    .where(RoleDataAccessPolicy.tenant_id == tenant_id)
                    .where(col(RoleDataAccessPolicy.role_id).in_(role_ids))
                ).all()
            )
            inherited_allow_all = any(item.scope_mode == DataScopeMode.ALL for item in role_policies)
            inherited_allow = self._make_rule(
                org_unit_ids=[value for item in role_policies for value in item.org_unit_ids],
                project_codes=[value for item in role_policies for value in item.project_codes],
                area_codes=[value for item in role_policies for value in item.area_codes],
                task_ids=[value for item in role_policies for value in item.task_ids],
                resource_ids=[value for item in role_policies for value in item.resource_ids],
            )

        return DataPerimeterScope(
            mode=mode,
            explicit_deny=explicit_deny,
            explicit_allow=explicit_allow,
            inherited_allow=inherited_allow,
            inherited_allow_all=inherited_allow_all,
        )

    def allows(
        self,
        scope: DataPerimeterScope,
        *,
        org_unit_id: str | None,
        project_code: str | None,
        area_code: str | None,
        task_id: str | None,
        resource_id: str | None = None,
    ) -> bool:
        if scope.explicit_deny.has_constraints() and self._rule_matches(
            scope.explicit_deny,
            org_unit_id=org_unit_id,
            project_code=project_code,
            area_code=area_code,
            task_id=task_id,
            resource_id=resource_id,
        ):
            return False

        if scope.mode == DataScopeMode.ALL:
            return True

        if scope.explicit_allow.has_constraints() and self._rule_matches(
            scope.explicit_allow,
            org_unit_id=org_unit_id,
            project_code=project_code,
            area_code=area_code,
            task_id=task_id,
            resource_id=resource_id,
        ):
            return True

        if scope.inherited_allow_all:
            return True

        return scope.inherited_allow.has_constraints() and self._rule_matches(
            scope.inherited_allow,
            org_unit_id=org_unit_id,
            project_code=project_code,
            area_code=area_code,
            task_id=task_id,
            resource_id=resource_id,
        )

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

    def asset_visible(self, asset: Asset, scope: DataPerimeterScope) -> bool:
        return self.allows(
            scope,
            org_unit_id=None,
            project_code=None,
            area_code=asset.region_code,
            task_id=None,
            resource_id=asset.id,
        )

    def drone_visible(self, drone: Drone, scope: DataPerimeterScope) -> bool:
        return self.allows(
            scope,
            org_unit_id=None,
            project_code=None,
            area_code=None,
            task_id=None,
            resource_id=drone.id,
        )
