from __future__ import annotations

import hashlib
import os
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, col, select

from app.domain.models import (
    BootstrapAdminRequest,
    DataAccessPolicy,
    DataAccessPolicyUpdate,
    DataScopeMode,
    OrgUnit,
    OrgUnitCreate,
    OrgUnitUpdate,
    Permission,
    PermissionCreate,
    PermissionUpdate,
    Role,
    RoleCreate,
    RoleDataAccessPolicy,
    RoleDataAccessPolicyUpdate,
    RolePermission,
    RoleUpdate,
    Tenant,
    TenantCreate,
    TenantUpdate,
    User,
    UserCreate,
    UserOrgMembership,
    UserRole,
    UserUpdate,
    now_utc,
)
from app.domain.permissions import (
    DEFAULT_PERMISSION_NAMES,
    PERM_ALERT_READ,
    PERM_COMMAND_READ,
    PERM_COMMAND_WRITE,
    PERM_DASHBOARD_READ,
    PERM_IDENTITY_READ,
    PERM_INCIDENT_READ,
    PERM_INCIDENT_WRITE,
    PERM_INSPECTION_READ,
    PERM_INSPECTION_WRITE,
    PERM_MISSION_READ,
    PERM_MISSION_WRITE,
    PERM_REGISTRY_READ,
    PERM_REPORTING_READ,
    PERM_WILDCARD,
)
from app.infra.db import get_engine


class IdentityError(Exception):
    pass


class NotFoundError(IdentityError):
    pass


class ConflictError(IdentityError):
    pass


class AuthError(IdentityError):
    pass


class IdentityService:
    ROLE_TEMPLATES: tuple[dict[str, Any], ...] = (
        {
            "key": "dispatcher",
            "name": "dispatcher",
            "description": "mission and command dispatcher",
            "permissions": [
                PERM_MISSION_READ,
                PERM_MISSION_WRITE,
                PERM_COMMAND_READ,
                PERM_COMMAND_WRITE,
                PERM_ALERT_READ,
                PERM_DASHBOARD_READ,
                PERM_REGISTRY_READ,
            ],
        },
        {
            "key": "inspector",
            "name": "inspector",
            "description": "inspection operator",
            "permissions": [
                PERM_INSPECTION_READ,
                PERM_INSPECTION_WRITE,
                PERM_MISSION_READ,
                PERM_DASHBOARD_READ,
            ],
        },
        {
            "key": "incident_operator",
            "name": "incident-operator",
            "description": "incident response operator",
            "permissions": [
                PERM_INCIDENT_READ,
                PERM_INCIDENT_WRITE,
                PERM_MISSION_READ,
                PERM_COMMAND_READ,
                PERM_DASHBOARD_READ,
            ],
        },
        {
            "key": "auditor",
            "name": "auditor",
            "description": "read-only governance reviewer",
            "permissions": [
                PERM_IDENTITY_READ,
                PERM_MISSION_READ,
                PERM_INSPECTION_READ,
                PERM_INCIDENT_READ,
                PERM_REPORTING_READ,
                PERM_DASHBOARD_READ,
                PERM_COMMAND_READ,
                PERM_ALERT_READ,
            ],
        },
    )

    def _session(self) -> Session:
        return Session(get_engine(), expire_on_commit=False)

    def _hash_password(self, raw_password: str) -> str:
        salt = os.getenv("PASSWORD_SALT", "phase1-dev-salt")
        return hashlib.sha256(f"{salt}:{raw_password}".encode()).hexdigest()

    def _ensure_default_permissions(self, session: Session) -> list[Permission]:
        existing = session.exec(select(Permission)).all()
        by_name = {item.name: item for item in existing}
        created: list[Permission] = []
        for name in DEFAULT_PERMISSION_NAMES:
            if name in by_name:
                continue
            perm = Permission(name=name, description=f"default permission {name}")
            session.add(perm)
            created.append(perm)
        if created:
            session.commit()
            for perm in created:
                session.refresh(perm)
        return list(session.exec(select(Permission)).all())

    def _get_scoped_user(self, session: Session, tenant_id: str, user_id: str) -> User | None:
        statement = select(User).where(User.tenant_id == tenant_id).where(User.id == user_id)
        return session.exec(statement).first()

    def _get_scoped_role(self, session: Session, tenant_id: str, role_id: str) -> Role | None:
        statement = select(Role).where(Role.tenant_id == tenant_id).where(Role.id == role_id)
        return session.exec(statement).first()

    def _get_scoped_org_unit(self, session: Session, tenant_id: str, org_unit_id: str) -> OrgUnit | None:
        statement = select(OrgUnit).where(OrgUnit.tenant_id == tenant_id).where(OrgUnit.id == org_unit_id)
        return session.exec(statement).first()

    def _resolve_org_parent(
        self,
        session: Session,
        tenant_id: str,
        current_org_id: str,
        parent_id: str | None,
    ) -> OrgUnit | None:
        if parent_id is None:
            return None
        if parent_id == current_org_id:
            raise ConflictError("org unit cannot be parent of itself")
        parent = self._get_scoped_org_unit(session, tenant_id, parent_id)
        if parent is None:
            raise NotFoundError("parent org unit not found")
        return parent

    def _org_level_path(self, org_unit_id: str, parent: OrgUnit | None) -> tuple[int, str]:
        if parent is None:
            return 0, f"/{org_unit_id}"
        return parent.level + 1, f"{parent.path}/{org_unit_id}"

    def _normalize_scope_values(self, values: list[str]) -> list[str]:
        return sorted({item.strip() for item in values if isinstance(item, str) and item.strip()})

    def _empty_scope_values(self) -> dict[str, list[str]]:
        return {
            "org_unit_ids": [],
            "project_codes": [],
            "area_codes": [],
            "task_ids": [],
            "resource_ids": [],
        }

    def _empty_deny_scope_values(self) -> dict[str, list[str]]:
        return {
            "denied_org_unit_ids": [],
            "denied_project_codes": [],
            "denied_area_codes": [],
            "denied_task_ids": [],
            "denied_resource_ids": [],
        }

    def user_exists_any_tenant(self, user_id: str) -> bool:
        with self._session() as session:
            statement = select(User.id).where(User.id == user_id)
            return session.exec(statement).first() is not None

    def role_exists_any_tenant(self, role_id: str) -> bool:
        with self._session() as session:
            statement = select(Role.id).where(Role.id == role_id)
            return session.exec(statement).first() is not None

    def create_tenant(self, payload: TenantCreate) -> Tenant:
        with self._session() as session:
            tenant = Tenant(name=payload.name)
            session.add(tenant)
            try:
                session.commit()
            except IntegrityError as exc:
                session.rollback()
                raise ConflictError("tenant name already exists") from exc
            session.refresh(tenant)
            return tenant

    def list_tenants(self, tenant_id: str) -> list[Tenant]:
        with self._session() as session:
            tenant = session.get(Tenant, tenant_id)
            return [tenant] if tenant is not None else []

    def list_all_tenants(self) -> list[Tenant]:
        with self._session() as session:
            return list(session.exec(select(Tenant)).all())

    def get_tenant(self, tenant_id: str) -> Tenant:
        with self._session() as session:
            tenant = session.get(Tenant, tenant_id)
            if tenant is None:
                raise NotFoundError("tenant not found")
            return tenant

    def update_tenant(self, tenant_id: str, payload: TenantUpdate) -> Tenant:
        with self._session() as session:
            tenant = session.get(Tenant, tenant_id)
            if tenant is None:
                raise NotFoundError("tenant not found")
            tenant.name = payload.name
            session.add(tenant)
            try:
                session.commit()
            except IntegrityError as exc:
                session.rollback()
                raise ConflictError("tenant name already exists") from exc
            session.refresh(tenant)
            return tenant

    def delete_tenant(self, tenant_id: str) -> None:
        with self._session() as session:
            tenant = session.get(Tenant, tenant_id)
            if tenant is None:
                raise NotFoundError("tenant not found")
            session.delete(tenant)
            session.commit()

    def count_users(self, tenant_id: str) -> int:
        with self._session() as session:
            users = session.exec(select(User).where(User.tenant_id == tenant_id)).all()
            return len(users)

    def create_user(self, tenant_id: str, payload: UserCreate) -> User:
        with self._session() as session:
            if session.get(Tenant, tenant_id) is None:
                raise NotFoundError("tenant not found")
            user = User(
                tenant_id=tenant_id,
                username=payload.username,
                password_hash=self._hash_password(payload.password),
                is_active=payload.is_active,
            )
            session.add(user)
            try:
                session.commit()
            except IntegrityError as exc:
                session.rollback()
                raise ConflictError("username already exists in tenant") from exc
            session.refresh(user)
            return user

    def bootstrap_admin(self, payload: BootstrapAdminRequest) -> User:
        with self._session() as session:
            tenant = session.get(Tenant, payload.tenant_id)
            if tenant is None:
                raise NotFoundError("tenant not found")
            tenant_users = session.exec(select(User).where(User.tenant_id == payload.tenant_id)).all()
            if tenant_users:
                raise ConflictError("tenant already initialized")

            all_permissions = self._ensure_default_permissions(session)
            admin_role = Role(
                tenant_id=payload.tenant_id,
                name="admin",
                description="bootstrap admin role",
            )
            session.add(admin_role)
            session.commit()
            session.refresh(admin_role)

            for permission in all_permissions:
                session.add(RolePermission(role_id=admin_role.id, permission_id=permission.id))

            admin_user = User(
                tenant_id=payload.tenant_id,
                username=payload.username,
                password_hash=self._hash_password(payload.password),
                is_active=True,
            )
            session.add(admin_user)
            session.commit()
            session.refresh(admin_user)

            session.add(UserRole(tenant_id=payload.tenant_id, user_id=admin_user.id, role_id=admin_role.id))
            session.commit()
            return admin_user

    def list_users(self, tenant_id: str) -> list[User]:
        with self._session() as session:
            return list(session.exec(select(User).where(User.tenant_id == tenant_id)).all())

    def get_user(self, tenant_id: str, user_id: str) -> User:
        with self._session() as session:
            user = self._get_scoped_user(session, tenant_id, user_id)
            if user is None:
                raise NotFoundError("user not found")
            return user

    def update_user(self, tenant_id: str, user_id: str, payload: UserUpdate) -> User:
        with self._session() as session:
            user = self._get_scoped_user(session, tenant_id, user_id)
            if user is None:
                raise NotFoundError("user not found")
            if payload.password is not None:
                user.password_hash = self._hash_password(payload.password)
            if payload.is_active is not None:
                user.is_active = payload.is_active
            session.add(user)
            session.commit()
            session.refresh(user)
            return user

    def delete_user(self, tenant_id: str, user_id: str) -> None:
        with self._session() as session:
            user = self._get_scoped_user(session, tenant_id, user_id)
            if user is None:
                raise NotFoundError("user not found")
            session.delete(user)
            session.commit()

    def create_role(self, tenant_id: str, payload: RoleCreate) -> Role:
        with self._session() as session:
            role = Role(tenant_id=tenant_id, name=payload.name, description=payload.description)
            session.add(role)
            try:
                session.commit()
            except IntegrityError as exc:
                session.rollback()
                raise ConflictError("role name already exists in tenant") from exc
            session.refresh(role)
            return role

    def list_roles(self, tenant_id: str) -> list[Role]:
        with self._session() as session:
            return list(session.exec(select(Role).where(Role.tenant_id == tenant_id)).all())

    def get_role(self, tenant_id: str, role_id: str) -> Role:
        with self._session() as session:
            role = self._get_scoped_role(session, tenant_id, role_id)
            if role is None:
                raise NotFoundError("role not found")
            return role

    def update_role(self, tenant_id: str, role_id: str, payload: RoleUpdate) -> Role:
        with self._session() as session:
            role = self._get_scoped_role(session, tenant_id, role_id)
            if role is None:
                raise NotFoundError("role not found")
            if payload.name is not None:
                role.name = payload.name
            if payload.description is not None:
                role.description = payload.description
            session.add(role)
            try:
                session.commit()
            except IntegrityError as exc:
                session.rollback()
                raise ConflictError("role name already exists in tenant") from exc
            session.refresh(role)
            return role

    def delete_role(self, tenant_id: str, role_id: str) -> None:
        with self._session() as session:
            role = self._get_scoped_role(session, tenant_id, role_id)
            if role is None:
                raise NotFoundError("role not found")
            session.delete(role)
            session.commit()

    def list_role_templates(self) -> list[dict[str, Any]]:
        return [
            {
                "key": str(item["key"]),
                "name": str(item["name"]),
                "description": str(item["description"]),
                "permissions": list(item["permissions"]),
            }
            for item in self.ROLE_TEMPLATES
        ]

    def create_role_from_template(
        self,
        *,
        tenant_id: str,
        template_key: str,
        name: str | None = None,
    ) -> Role:
        template = next((item for item in self.ROLE_TEMPLATES if item["key"] == template_key), None)
        if template is None:
            raise NotFoundError("role template not found")

        role_name = name or str(template["name"])
        role_description = str(template["description"])
        template_permissions = list(template["permissions"])

        with self._session() as session:
            _ = self._ensure_default_permissions(session)

            role = Role(
                tenant_id=tenant_id,
                name=role_name,
                description=role_description,
            )
            session.add(role)
            try:
                session.commit()
            except IntegrityError as exc:
                session.rollback()
                raise ConflictError("role name already exists in tenant") from exc
            session.refresh(role)

            permissions = list(
                session.exec(
                    select(Permission).where(col(Permission.name).in_(template_permissions))
                ).all()
            )
            permission_by_name = {item.name: item for item in permissions}
            missing_permissions = [perm for perm in template_permissions if perm not in permission_by_name]
            if missing_permissions:
                raise ConflictError(f"missing permissions for template: {missing_permissions}")

            for perm_name in template_permissions:
                permission = permission_by_name[perm_name]
                if session.get(RolePermission, (role.id, permission.id)) is None:
                    session.add(RolePermission(role_id=role.id, permission_id=permission.id))
            session.commit()
            session.refresh(role)
            return role

    def create_org_unit(self, tenant_id: str, payload: OrgUnitCreate) -> OrgUnit:
        with self._session() as session:
            if session.get(Tenant, tenant_id) is None:
                raise NotFoundError("tenant not found")

            org_unit = OrgUnit(
                tenant_id=tenant_id,
                name=payload.name,
                code=payload.code,
                unit_type=payload.unit_type,
                parent_id=payload.parent_id,
                is_active=payload.is_active,
            )
            parent = self._resolve_org_parent(session, tenant_id, org_unit.id, payload.parent_id)
            org_unit.level, org_unit.path = self._org_level_path(org_unit.id, parent)
            session.add(org_unit)
            try:
                session.commit()
            except IntegrityError as exc:
                session.rollback()
                raise ConflictError("org unit code already exists in tenant") from exc
            session.refresh(org_unit)
            return org_unit

    def list_org_units(self, tenant_id: str) -> list[OrgUnit]:
        with self._session() as session:
            units = list(session.exec(select(OrgUnit).where(OrgUnit.tenant_id == tenant_id)).all())
            return sorted(units, key=lambda item: item.path)

    def get_org_unit(self, tenant_id: str, org_unit_id: str) -> OrgUnit:
        with self._session() as session:
            org_unit = self._get_scoped_org_unit(session, tenant_id, org_unit_id)
            if org_unit is None:
                raise NotFoundError("org unit not found")
            return org_unit

    def update_org_unit(self, tenant_id: str, org_unit_id: str, payload: OrgUnitUpdate) -> OrgUnit:
        with self._session() as session:
            org_unit = self._get_scoped_org_unit(session, tenant_id, org_unit_id)
            if org_unit is None:
                raise NotFoundError("org unit not found")

            if "name" in payload.model_fields_set and payload.name is not None:
                org_unit.name = payload.name
            if "code" in payload.model_fields_set and payload.code is not None:
                org_unit.code = payload.code
            if "unit_type" in payload.model_fields_set and payload.unit_type is not None:
                org_unit.unit_type = payload.unit_type
            if "is_active" in payload.model_fields_set and payload.is_active is not None:
                org_unit.is_active = payload.is_active

            if "parent_id" in payload.model_fields_set and payload.parent_id != org_unit.parent_id:
                old_path = org_unit.path
                old_level = org_unit.level
                parent = self._resolve_org_parent(session, tenant_id, org_unit.id, payload.parent_id)
                if parent is not None and parent.path.startswith(f"{old_path}/"):
                    raise ConflictError("org unit cannot move under its descendant")

                org_unit.parent_id = payload.parent_id
                org_unit.level, org_unit.path = self._org_level_path(org_unit.id, parent)
                depth_delta = org_unit.level - old_level
                descendants = list(
                    session.exec(
                        select(OrgUnit)
                        .where(OrgUnit.tenant_id == tenant_id)
                        .where(col(OrgUnit.path).like(f"{old_path}/%"))
                    ).all()
                )
                for child in descendants:
                    suffix = child.path[len(old_path) :]
                    child.path = f"{org_unit.path}{suffix}"
                    child.level = child.level + depth_delta
                    child.updated_at = now_utc()
                    session.add(child)

            org_unit.updated_at = now_utc()
            session.add(org_unit)
            try:
                session.commit()
            except IntegrityError as exc:
                session.rollback()
                raise ConflictError("org unit code already exists in tenant") from exc
            session.refresh(org_unit)
            return org_unit

    def delete_org_unit(self, tenant_id: str, org_unit_id: str) -> None:
        with self._session() as session:
            org_unit = self._get_scoped_org_unit(session, tenant_id, org_unit_id)
            if org_unit is None:
                raise NotFoundError("org unit not found")

            child = session.exec(
                select(OrgUnit.id)
                .where(OrgUnit.tenant_id == tenant_id)
                .where(OrgUnit.parent_id == org_unit_id)
            ).first()
            if child is not None:
                raise ConflictError("org unit has child units")

            membership = session.exec(
                select(UserOrgMembership.user_id)
                .where(UserOrgMembership.tenant_id == tenant_id)
                .where(UserOrgMembership.org_unit_id == org_unit_id)
            ).first()
            if membership is not None:
                raise ConflictError("org unit has memberships")

            session.delete(org_unit)
            session.commit()

    def bind_user_org_unit(
        self,
        tenant_id: str,
        user_id: str,
        org_unit_id: str,
        *,
        is_primary: bool = False,
        job_title: str | None = None,
        job_code: str | None = None,
        is_manager: bool | None = None,
    ) -> UserOrgMembership:
        with self._session() as session:
            user = self._get_scoped_user(session, tenant_id, user_id)
            org_unit = self._get_scoped_org_unit(session, tenant_id, org_unit_id)
            if user is None or org_unit is None:
                raise NotFoundError("user or org unit not found")

            link = session.get(UserOrgMembership, (tenant_id, user_id, org_unit_id))
            if link is None:
                link = UserOrgMembership(
                    tenant_id=tenant_id,
                    user_id=user_id,
                    org_unit_id=org_unit_id,
                    is_primary=is_primary,
                    job_title=job_title,
                    job_code=job_code,
                    is_manager=bool(is_manager),
                )
            else:
                if job_title is not None:
                    link.job_title = job_title
                if job_code is not None:
                    link.job_code = job_code
                if is_manager is not None:
                    link.is_manager = is_manager

            if is_primary:
                all_links = list(
                    session.exec(
                        select(UserOrgMembership)
                        .where(UserOrgMembership.tenant_id == tenant_id)
                        .where(UserOrgMembership.user_id == user_id)
                    ).all()
                )
                for item in all_links:
                    if item.org_unit_id == org_unit_id:
                        continue
                    if item.is_primary:
                        item.is_primary = False
                        session.add(item)
                link.is_primary = True

            session.add(link)
            session.commit()
            session.refresh(link)
            return link

    def unbind_user_org_unit(self, tenant_id: str, user_id: str, org_unit_id: str) -> None:
        with self._session() as session:
            user = self._get_scoped_user(session, tenant_id, user_id)
            org_unit = self._get_scoped_org_unit(session, tenant_id, org_unit_id)
            if user is None or org_unit is None:
                raise NotFoundError("user or org unit not found")
            link = session.get(UserOrgMembership, (tenant_id, user_id, org_unit_id))
            if link is None:
                return
            session.delete(link)
            session.commit()

    def list_user_org_units(self, tenant_id: str, user_id: str) -> list[UserOrgMembership]:
        with self._session() as session:
            user = self._get_scoped_user(session, tenant_id, user_id)
            if user is None:
                raise NotFoundError("user not found")
            links = list(
                session.exec(
                    select(UserOrgMembership)
                    .where(UserOrgMembership.tenant_id == tenant_id)
                    .where(UserOrgMembership.user_id == user_id)
                ).all()
            )
            return sorted(links, key=lambda item: (not item.is_primary, item.org_unit_id))

    def get_user_data_policy(self, tenant_id: str, user_id: str) -> DataAccessPolicy:
        with self._session() as session:
            user = self._get_scoped_user(session, tenant_id, user_id)
            if user is None:
                raise NotFoundError("user not found")
            policy = session.exec(
                select(DataAccessPolicy)
                .where(DataAccessPolicy.tenant_id == tenant_id)
                .where(DataAccessPolicy.user_id == user_id)
            ).first()
            if policy is not None:
                return policy
            return DataAccessPolicy(
                tenant_id=tenant_id,
                user_id=user_id,
                scope_mode=DataScopeMode.ALL,
                org_unit_ids=[],
                project_codes=[],
                area_codes=[],
                task_ids=[],
                resource_ids=[],
                denied_org_unit_ids=[],
                denied_project_codes=[],
                denied_area_codes=[],
                denied_task_ids=[],
                denied_resource_ids=[],
            )

    def upsert_user_data_policy(
        self,
        tenant_id: str,
        user_id: str,
        payload: DataAccessPolicyUpdate,
    ) -> DataAccessPolicy:
        with self._session() as session:
            user = self._get_scoped_user(session, tenant_id, user_id)
            if user is None:
                raise NotFoundError("user not found")
            policy = session.exec(
                select(DataAccessPolicy)
                .where(DataAccessPolicy.tenant_id == tenant_id)
                .where(DataAccessPolicy.user_id == user_id)
            ).first()
            if policy is None:
                policy = DataAccessPolicy(
                    tenant_id=tenant_id,
                    user_id=user_id,
                )

            policy.scope_mode = payload.scope_mode
            policy.org_unit_ids = self._normalize_scope_values(payload.org_unit_ids)
            policy.project_codes = self._normalize_scope_values(payload.project_codes)
            policy.area_codes = self._normalize_scope_values(payload.area_codes)
            policy.task_ids = self._normalize_scope_values(payload.task_ids)
            policy.resource_ids = self._normalize_scope_values(payload.resource_ids)
            policy.denied_org_unit_ids = self._normalize_scope_values(payload.denied_org_unit_ids)
            policy.denied_project_codes = self._normalize_scope_values(payload.denied_project_codes)
            policy.denied_area_codes = self._normalize_scope_values(payload.denied_area_codes)
            policy.denied_task_ids = self._normalize_scope_values(payload.denied_task_ids)
            policy.denied_resource_ids = self._normalize_scope_values(payload.denied_resource_ids)
            policy.updated_at = now_utc()
            session.add(policy)
            session.commit()
            session.refresh(policy)
            return policy

    def get_role_data_policy(self, tenant_id: str, role_id: str) -> RoleDataAccessPolicy:
        with self._session() as session:
            role = self._get_scoped_role(session, tenant_id, role_id)
            if role is None:
                raise NotFoundError("role not found")
            policy = session.exec(
                select(RoleDataAccessPolicy)
                .where(RoleDataAccessPolicy.tenant_id == tenant_id)
                .where(RoleDataAccessPolicy.role_id == role_id)
            ).first()
            if policy is not None:
                return policy
            return RoleDataAccessPolicy(
                tenant_id=tenant_id,
                role_id=role_id,
                scope_mode=DataScopeMode.SCOPED,
                org_unit_ids=[],
                project_codes=[],
                area_codes=[],
                task_ids=[],
                resource_ids=[],
            )

    def upsert_role_data_policy(
        self,
        tenant_id: str,
        role_id: str,
        payload: RoleDataAccessPolicyUpdate,
    ) -> RoleDataAccessPolicy:
        with self._session() as session:
            role = self._get_scoped_role(session, tenant_id, role_id)
            if role is None:
                raise NotFoundError("role not found")
            policy = session.exec(
                select(RoleDataAccessPolicy)
                .where(RoleDataAccessPolicy.tenant_id == tenant_id)
                .where(RoleDataAccessPolicy.role_id == role_id)
            ).first()
            if policy is None:
                policy = RoleDataAccessPolicy(
                    tenant_id=tenant_id,
                    role_id=role_id,
                )

            policy.scope_mode = payload.scope_mode
            policy.org_unit_ids = self._normalize_scope_values(payload.org_unit_ids)
            policy.project_codes = self._normalize_scope_values(payload.project_codes)
            policy.area_codes = self._normalize_scope_values(payload.area_codes)
            policy.task_ids = self._normalize_scope_values(payload.task_ids)
            policy.resource_ids = self._normalize_scope_values(payload.resource_ids)
            policy.updated_at = now_utc()
            session.add(policy)
            session.commit()
            session.refresh(policy)
            return policy

    def get_effective_user_data_policy(self, tenant_id: str, user_id: str) -> dict[str, Any]:
        with self._session() as session:
            user = self._get_scoped_user(session, tenant_id, user_id)
            if user is None:
                raise NotFoundError("user not found")

            user_policy = session.exec(
                select(DataAccessPolicy)
                .where(DataAccessPolicy.tenant_id == tenant_id)
                .where(DataAccessPolicy.user_id == user_id)
            ).first()

            explicit_allow = self._empty_scope_values()
            explicit_deny = self._empty_deny_scope_values()
            mode = DataScopeMode.ALL
            if user_policy is not None:
                mode = user_policy.scope_mode
                explicit_allow["org_unit_ids"] = self._normalize_scope_values(user_policy.org_unit_ids)
                explicit_allow["project_codes"] = self._normalize_scope_values(user_policy.project_codes)
                explicit_allow["area_codes"] = self._normalize_scope_values(user_policy.area_codes)
                explicit_allow["task_ids"] = self._normalize_scope_values(user_policy.task_ids)
                explicit_allow["resource_ids"] = self._normalize_scope_values(user_policy.resource_ids)
                explicit_deny["denied_org_unit_ids"] = self._normalize_scope_values(user_policy.denied_org_unit_ids)
                explicit_deny["denied_project_codes"] = self._normalize_scope_values(
                    user_policy.denied_project_codes
                )
                explicit_deny["denied_area_codes"] = self._normalize_scope_values(user_policy.denied_area_codes)
                explicit_deny["denied_task_ids"] = self._normalize_scope_values(user_policy.denied_task_ids)
                explicit_deny["denied_resource_ids"] = self._normalize_scope_values(user_policy.denied_resource_ids)

            inherited_allow = self._empty_scope_values()
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
                for policy in role_policies:
                    if policy.scope_mode != DataScopeMode.SCOPED:
                        continue
                    inherited_allow["org_unit_ids"] = self._normalize_scope_values(
                        inherited_allow["org_unit_ids"] + list(policy.org_unit_ids)
                    )
                    inherited_allow["project_codes"] = self._normalize_scope_values(
                        inherited_allow["project_codes"] + list(policy.project_codes)
                    )
                    inherited_allow["area_codes"] = self._normalize_scope_values(
                        inherited_allow["area_codes"] + list(policy.area_codes)
                    )
                    inherited_allow["task_ids"] = self._normalize_scope_values(
                        inherited_allow["task_ids"] + list(policy.task_ids)
                    )
                    inherited_allow["resource_ids"] = self._normalize_scope_values(
                        inherited_allow["resource_ids"] + list(policy.resource_ids)
                    )

            return {
                "scope_mode": mode,
                "explicit_allow_org_unit_ids": explicit_allow["org_unit_ids"],
                "explicit_allow_project_codes": explicit_allow["project_codes"],
                "explicit_allow_area_codes": explicit_allow["area_codes"],
                "explicit_allow_task_ids": explicit_allow["task_ids"],
                "explicit_allow_resource_ids": explicit_allow["resource_ids"],
                "explicit_deny_org_unit_ids": explicit_deny["denied_org_unit_ids"],
                "explicit_deny_project_codes": explicit_deny["denied_project_codes"],
                "explicit_deny_area_codes": explicit_deny["denied_area_codes"],
                "explicit_deny_task_ids": explicit_deny["denied_task_ids"],
                "explicit_deny_resource_ids": explicit_deny["denied_resource_ids"],
                "inherited_allow_org_unit_ids": inherited_allow["org_unit_ids"],
                "inherited_allow_project_codes": inherited_allow["project_codes"],
                "inherited_allow_area_codes": inherited_allow["area_codes"],
                "inherited_allow_task_ids": inherited_allow["task_ids"],
                "inherited_allow_resource_ids": inherited_allow["resource_ids"],
                "inherited_allow_all": inherited_allow_all,
                "resolution_order": [
                    "explicit_deny",
                    "explicit_allow",
                    "inherited_allow",
                    "default_deny",
                ],
            }

    def create_permission(self, payload: PermissionCreate) -> Permission:
        with self._session() as session:
            permission = Permission(name=payload.name, description=payload.description)
            session.add(permission)
            try:
                session.commit()
            except IntegrityError as exc:
                session.rollback()
                raise ConflictError("permission name already exists") from exc
            session.refresh(permission)
            return permission

    def list_permissions(self) -> list[Permission]:
        with self._session() as session:
            return list(session.exec(select(Permission)).all())

    def get_permission(self, permission_id: str) -> Permission:
        with self._session() as session:
            permission = session.get(Permission, permission_id)
            if permission is None:
                raise NotFoundError("permission not found")
            return permission

    def update_permission(self, permission_id: str, payload: PermissionUpdate) -> Permission:
        with self._session() as session:
            permission = session.get(Permission, permission_id)
            if permission is None:
                raise NotFoundError("permission not found")
            if payload.name is not None:
                permission.name = payload.name
            if payload.description is not None:
                permission.description = payload.description
            session.add(permission)
            try:
                session.commit()
            except IntegrityError as exc:
                session.rollback()
                raise ConflictError("permission name already exists") from exc
            session.refresh(permission)
            return permission

    def delete_permission(self, permission_id: str) -> None:
        with self._session() as session:
            permission = session.get(Permission, permission_id)
            if permission is None:
                raise NotFoundError("permission not found")
            session.delete(permission)
            session.commit()

    def bind_user_role(self, tenant_id: str, user_id: str, role_id: str) -> None:
        with self._session() as session:
            user = self._get_scoped_user(session, tenant_id, user_id)
            role = self._get_scoped_role(session, tenant_id, role_id)
            if user is None or role is None:
                raise NotFoundError("user or role not found")
            if session.get(UserRole, (tenant_id, user_id, role_id)) is not None:
                return
            session.add(UserRole(tenant_id=tenant_id, user_id=user_id, role_id=role_id))
            session.commit()

    def bind_user_roles_batch(
        self,
        tenant_id: str,
        user_id: str,
        role_ids: list[str],
    ) -> dict[str, Any]:
        with self._session() as session:
            user = self._get_scoped_user(session, tenant_id, user_id)
            if user is None:
                raise NotFoundError("user not found")

            normalized_role_ids = [item.strip() for item in role_ids if isinstance(item, str) and item.strip()]
            if not normalized_role_ids:
                return {
                    "user_id": user_id,
                    "requested_count": 0,
                    "bound_count": 0,
                    "already_bound_count": 0,
                    "denied_count": 0,
                    "missing_count": 0,
                    "results": [],
                }

            scoped_roles = list(
                session.exec(
                    select(Role)
                    .where(Role.tenant_id == tenant_id)
                    .where(col(Role.id).in_(normalized_role_ids))
                ).all()
            )
            scoped_role_ids = {item.id for item in scoped_roles}

            global_role_ids = set(
                session.exec(select(Role.id).where(col(Role.id).in_(normalized_role_ids))).all()
            )
            existing_role_links = set(
                session.exec(
                    select(UserRole.role_id)
                    .where(UserRole.tenant_id == tenant_id)
                    .where(UserRole.user_id == user_id)
                ).all()
            )

            results: list[dict[str, str]] = []
            for role_id in normalized_role_ids:
                if role_id in scoped_role_ids:
                    if role_id in existing_role_links:
                        results.append({"role_id": role_id, "status": "already_bound"})
                        continue
                    session.add(UserRole(tenant_id=tenant_id, user_id=user_id, role_id=role_id))
                    existing_role_links.add(role_id)
                    results.append({"role_id": role_id, "status": "bound"})
                    continue

                status_name = "cross_tenant_denied" if role_id in global_role_ids else "not_found"
                results.append({"role_id": role_id, "status": status_name})

            if any(item["status"] == "bound" for item in results):
                session.commit()

            return {
                "user_id": user_id,
                "requested_count": len(normalized_role_ids),
                "bound_count": sum(1 for item in results if item["status"] == "bound"),
                "already_bound_count": sum(1 for item in results if item["status"] == "already_bound"),
                "denied_count": sum(1 for item in results if item["status"] == "cross_tenant_denied"),
                "missing_count": sum(1 for item in results if item["status"] == "not_found"),
                "results": results,
            }

    def unbind_user_role(self, tenant_id: str, user_id: str, role_id: str) -> None:
        with self._session() as session:
            user = self._get_scoped_user(session, tenant_id, user_id)
            role = self._get_scoped_role(session, tenant_id, role_id)
            if user is None or role is None:
                raise NotFoundError("user or role not found")
            user_role = session.get(UserRole, (tenant_id, user_id, role_id))
            if user_role is None:
                return
            session.delete(user_role)
            session.commit()

    def bind_role_permission(self, tenant_id: str, role_id: str, permission_id: str) -> None:
        with self._session() as session:
            role = self._get_scoped_role(session, tenant_id, role_id)
            permission = session.get(Permission, permission_id)
            if role is None or permission is None:
                raise NotFoundError("role or permission not found")
            if session.get(RolePermission, (role_id, permission_id)) is not None:
                return
            session.add(RolePermission(role_id=role_id, permission_id=permission_id))
            session.commit()

    def unbind_role_permission(self, tenant_id: str, role_id: str, permission_id: str) -> None:
        with self._session() as session:
            role = self._get_scoped_role(session, tenant_id, role_id)
            permission = session.get(Permission, permission_id)
            if role is None or permission is None:
                raise NotFoundError("role or permission not found")
            role_permission = session.get(RolePermission, (role_id, permission_id))
            if role_permission is None:
                return
            session.delete(role_permission)
            session.commit()

    def collect_user_permissions(self, tenant_id: str, user_id: str) -> list[str]:
        with self._session() as session:
            user = self._get_scoped_user(session, tenant_id, user_id)
            if user is None:
                return []

            user_role_links = list(
                session.exec(
                    select(UserRole)
                    .where(UserRole.tenant_id == tenant_id)
                    .where(UserRole.user_id == user_id)
                ).all()
            )
            role_ids = [item.role_id for item in user_role_links]
            if not role_ids:
                return []

            scoped_roles = list(
                session.exec(
                    select(Role).where(Role.tenant_id == tenant_id).where(col(Role.id).in_(role_ids))
                ).all()
            )
            scoped_role_ids = [role.id for role in scoped_roles]
            if not scoped_role_ids:
                return []

            all_role_permissions = list(session.exec(select(RolePermission)).all())
            role_perm_links = [item for item in all_role_permissions if item.role_id in scoped_role_ids]
            permission_ids = [item.permission_id for item in role_perm_links]
            if not permission_ids:
                return []

            all_permissions = list(session.exec(select(Permission)).all())
            permissions = [permission for permission in all_permissions if permission.id in permission_ids]
            names = [permission.name for permission in permissions]
            return sorted(set(names))

    def dev_login(self, tenant_id: str, username: str, password: str) -> tuple[User, list[str]]:
        with self._session() as session:
            statement = select(User).where(User.tenant_id == tenant_id).where(User.username == username)
            user = session.exec(statement).first()
            if user is None:
                raise AuthError("invalid credentials")
            if not user.is_active:
                raise AuthError("user disabled")
            if user.password_hash != self._hash_password(password):
                raise AuthError("invalid credentials")

        permissions = self.collect_user_permissions(tenant_id, user.id)
        if PERM_WILDCARD not in permissions and not permissions:
            # Explicitly returns empty perms; require_perm will block protected routes.
            return user, []
        return user, permissions
