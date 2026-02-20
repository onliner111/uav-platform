from __future__ import annotations

import hashlib
import os

from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.domain.models import (
    BootstrapAdminRequest,
    Permission,
    PermissionCreate,
    PermissionUpdate,
    Role,
    RoleCreate,
    RolePermission,
    RoleUpdate,
    Tenant,
    TenantCreate,
    TenantUpdate,
    User,
    UserCreate,
    UserRole,
    UserUpdate,
)
from app.domain.permissions import DEFAULT_PERMISSION_NAMES, PERM_WILDCARD
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

            session.add(UserRole(user_id=admin_user.id, role_id=admin_role.id))
            session.commit()
            return admin_user

    def list_users(self, tenant_id: str) -> list[User]:
        with self._session() as session:
            return list(session.exec(select(User).where(User.tenant_id == tenant_id)).all())

    def get_user(self, tenant_id: str, user_id: str) -> User:
        with self._session() as session:
            user = session.get(User, user_id)
            if user is None or user.tenant_id != tenant_id:
                raise NotFoundError("user not found")
            return user

    def update_user(self, tenant_id: str, user_id: str, payload: UserUpdate) -> User:
        with self._session() as session:
            user = session.get(User, user_id)
            if user is None or user.tenant_id != tenant_id:
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
            user = session.get(User, user_id)
            if user is None or user.tenant_id != tenant_id:
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
            role = session.get(Role, role_id)
            if role is None or role.tenant_id != tenant_id:
                raise NotFoundError("role not found")
            return role

    def update_role(self, tenant_id: str, role_id: str, payload: RoleUpdate) -> Role:
        with self._session() as session:
            role = session.get(Role, role_id)
            if role is None or role.tenant_id != tenant_id:
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
            role = session.get(Role, role_id)
            if role is None or role.tenant_id != tenant_id:
                raise NotFoundError("role not found")
            session.delete(role)
            session.commit()

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
            user = session.get(User, user_id)
            role = session.get(Role, role_id)
            if user is None or role is None or user.tenant_id != tenant_id or role.tenant_id != tenant_id:
                raise NotFoundError("user or role not found")
            if session.get(UserRole, (user_id, role_id)) is not None:
                return
            session.add(UserRole(user_id=user_id, role_id=role_id))
            session.commit()

    def unbind_user_role(self, tenant_id: str, user_id: str, role_id: str) -> None:
        with self._session() as session:
            user = session.get(User, user_id)
            role = session.get(Role, role_id)
            if user is None or role is None or user.tenant_id != tenant_id or role.tenant_id != tenant_id:
                raise NotFoundError("user or role not found")
            user_role = session.get(UserRole, (user_id, role_id))
            if user_role is None:
                return
            session.delete(user_role)
            session.commit()

    def bind_role_permission(self, tenant_id: str, role_id: str, permission_id: str) -> None:
        with self._session() as session:
            role = session.get(Role, role_id)
            permission = session.get(Permission, permission_id)
            if role is None or permission is None or role.tenant_id != tenant_id:
                raise NotFoundError("role or permission not found")
            if session.get(RolePermission, (role_id, permission_id)) is not None:
                return
            session.add(RolePermission(role_id=role_id, permission_id=permission_id))
            session.commit()

    def unbind_role_permission(self, tenant_id: str, role_id: str, permission_id: str) -> None:
        with self._session() as session:
            role = session.get(Role, role_id)
            permission = session.get(Permission, permission_id)
            if role is None or permission is None or role.tenant_id != tenant_id:
                raise NotFoundError("role or permission not found")
            role_permission = session.get(RolePermission, (role_id, permission_id))
            if role_permission is None:
                return
            session.delete(role_permission)
            session.commit()

    def collect_user_permissions(self, tenant_id: str, user_id: str) -> list[str]:
        with self._session() as session:
            user = session.get(User, user_id)
            if user is None or user.tenant_id != tenant_id:
                return []

            user_role_links = list(session.exec(select(UserRole).where(UserRole.user_id == user_id)).all())
            role_ids = [item.role_id for item in user_role_links]
            if not role_ids:
                return []

            all_roles = list(session.exec(select(Role)).all())
            scoped_roles = [role for role in all_roles if role.id in role_ids and role.tenant_id == tenant_id]
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
