from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict
from pydantic import Field as PydanticField
from sqlalchemy import JSON, Column, UniqueConstraint
from sqlmodel import Field, SQLModel


def now_utc() -> datetime:
    return datetime.now(UTC)


class EventRecord(SQLModel, table=True):
    __tablename__ = "events"

    event_id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    event_type: str = Field(index=True)
    tenant_id: str = Field(index=True)
    ts: datetime = Field(default_factory=now_utc, index=True)
    actor_id: str | None = Field(default=None, index=True)
    correlation_id: str | None = Field(default=None, index=True)
    payload: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False),
    )


class AuditLog(SQLModel, table=True):
    __tablename__ = "audit_logs"

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    tenant_id: str = Field(index=True)
    actor_id: str | None = Field(default=None, index=True)
    action: str
    resource: str
    method: str
    status_code: int
    ts: datetime = Field(default_factory=now_utc, index=True)
    detail: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False),
    )


class Tenant(SQLModel, table=True):
    __tablename__ = "tenants"

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    name: str = Field(index=True, unique=True)
    created_at: datetime = Field(default_factory=now_utc, index=True)


class User(SQLModel, table=True):
    __tablename__ = "users"
    __table_args__ = (UniqueConstraint("tenant_id", "username", name="uq_users_tenant_username"),)

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    tenant_id: str = Field(foreign_key="tenants.id", index=True)
    username: str = Field(index=True)
    password_hash: str
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=now_utc, index=True)


class Role(SQLModel, table=True):
    __tablename__ = "roles"
    __table_args__ = (UniqueConstraint("tenant_id", "name", name="uq_roles_tenant_name"),)

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    tenant_id: str = Field(foreign_key="tenants.id", index=True)
    name: str = Field(index=True)
    description: str | None = None
    created_at: datetime = Field(default_factory=now_utc, index=True)


class Permission(SQLModel, table=True):
    __tablename__ = "permissions"

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    name: str = Field(index=True, unique=True)
    description: str | None = None
    created_at: datetime = Field(default_factory=now_utc, index=True)


class UserRole(SQLModel, table=True):
    __tablename__ = "user_roles"

    user_id: str = Field(foreign_key="users.id", primary_key=True)
    role_id: str = Field(foreign_key="roles.id", primary_key=True)
    created_at: datetime = Field(default_factory=now_utc, index=True)


class RolePermission(SQLModel, table=True):
    __tablename__ = "role_permissions"

    role_id: str = Field(foreign_key="roles.id", primary_key=True)
    permission_id: str = Field(foreign_key="permissions.id", primary_key=True)
    created_at: datetime = Field(default_factory=now_utc, index=True)


class EventEnvelope(BaseModel):
    event_id: str = PydanticField(default_factory=lambda: str(uuid4()))
    event_type: str
    tenant_id: str
    ts: datetime = PydanticField(default_factory=now_utc)
    actor_id: str | None = None
    correlation_id: str | None = None
    payload: dict[str, Any]


class TelemetryPosition(BaseModel):
    lat: float
    lon: float
    alt_m: float


class TelemetryBattery(BaseModel):
    percent: float
    voltage: float | None = None
    current: float | None = None


class TelemetryLink(BaseModel):
    rssi: int | None = None
    latency_ms: int | None = None


class TelemetryNormalized(BaseModel):
    tenant_id: str
    drone_id: str
    ts: datetime = PydanticField(default_factory=now_utc)
    position: TelemetryPosition
    battery: TelemetryBattery | None = None
    link: TelemetryLink | None = None
    mode: str
    health: dict[str, Any] = PydanticField(default_factory=dict)


class CommandType(StrEnum):
    RTH = "RTH"
    LAND = "LAND"
    HOLD = "HOLD"
    GOTO = "GOTO"
    START_MISSION = "START_MISSION"
    ABORT_MISSION = "ABORT_MISSION"
    PAUSE = "PAUSE"
    RESUME = "RESUME"


class Command(BaseModel):
    tenant_id: str
    command_id: str = PydanticField(default_factory=lambda: str(uuid4()))
    drone_id: str
    ts: datetime = PydanticField(default_factory=now_utc)
    type: CommandType
    params: dict[str, Any] = PydanticField(default_factory=dict)
    idempotency_key: str
    expect_ack: bool = True


class MissionPlanType(StrEnum):
    AREA_GRID = "AREA_GRID"
    ROUTE_WAYPOINTS = "ROUTE_WAYPOINTS"
    POINT_TASK = "POINT_TASK"


class MissionPlan(BaseModel):
    type: MissionPlanType
    payload: dict[str, Any] = PydanticField(default_factory=dict)
    constraints: dict[str, Any] = PydanticField(default_factory=dict)


class ORMReadModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class TenantCreate(BaseModel):
    name: str


class TenantUpdate(BaseModel):
    name: str


class TenantRead(ORMReadModel):
    id: str
    name: str
    created_at: datetime


class UserCreate(BaseModel):
    username: str
    password: str
    is_active: bool = True


class UserUpdate(BaseModel):
    password: str | None = None
    is_active: bool | None = None


class UserRead(ORMReadModel):
    id: str
    tenant_id: str
    username: str
    is_active: bool
    created_at: datetime


class RoleCreate(BaseModel):
    name: str
    description: str | None = None


class RoleUpdate(BaseModel):
    name: str | None = None
    description: str | None = None


class RoleRead(ORMReadModel):
    id: str
    tenant_id: str
    name: str
    description: str | None = None
    created_at: datetime


class PermissionCreate(BaseModel):
    name: str
    description: str | None = None


class PermissionUpdate(BaseModel):
    name: str | None = None
    description: str | None = None


class PermissionRead(ORMReadModel):
    id: str
    name: str
    description: str | None = None
    created_at: datetime


class DevLoginRequest(BaseModel):
    tenant_id: str
    username: str
    password: str


class BootstrapAdminRequest(BaseModel):
    tenant_id: str
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    permissions: list[str]
