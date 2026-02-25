from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict
from pydantic import Field as PydanticField
from sqlalchemy import JSON, Column, ForeignKeyConstraint, Index, UniqueConstraint
from sqlmodel import Field, SQLModel

from app.domain.state_machine import MissionState, TaskCenterState


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
    __table_args__ = (
        UniqueConstraint("tenant_id", "username", name="uq_users_tenant_username"),
        UniqueConstraint("tenant_id", "id", name="uq_users_tenant_id_id"),
    )

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    tenant_id: str = Field(foreign_key="tenants.id", index=True)
    username: str = Field(index=True)
    password_hash: str
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=now_utc, index=True)


class Role(SQLModel, table=True):
    __tablename__ = "roles"
    __table_args__ = (
        UniqueConstraint("tenant_id", "name", name="uq_roles_tenant_name"),
        UniqueConstraint("tenant_id", "id", name="uq_roles_tenant_id_id"),
    )

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
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "user_id"],
            ["users.tenant_id", "users.id"],
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "role_id"],
            ["roles.tenant_id", "roles.id"],
            ondelete="CASCADE",
        ),
        Index("ix_user_roles_tenant_user", "tenant_id", "user_id"),
        Index("ix_user_roles_tenant_role", "tenant_id", "role_id"),
    )

    tenant_id: str = Field(primary_key=True)
    user_id: str = Field(primary_key=True)
    role_id: str = Field(primary_key=True)
    created_at: datetime = Field(default_factory=now_utc, index=True)


class RolePermission(SQLModel, table=True):
    __tablename__ = "role_permissions"

    role_id: str = Field(foreign_key="roles.id", primary_key=True)
    permission_id: str = Field(foreign_key="permissions.id", primary_key=True)
    created_at: datetime = Field(default_factory=now_utc, index=True)


class OrgUnit(SQLModel, table=True):
    __tablename__ = "org_units"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_org_units_tenant_id_id"),
        UniqueConstraint("tenant_id", "code", name="uq_org_units_tenant_code"),
        ForeignKeyConstraint(
            ["tenant_id", "parent_id"],
            ["org_units.tenant_id", "org_units.id"],
            ondelete="RESTRICT",
        ),
        Index("ix_org_units_tenant_id_id", "tenant_id", "id"),
        Index("ix_org_units_tenant_parent_id", "tenant_id", "parent_id"),
    )

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    tenant_id: str = Field(foreign_key="tenants.id", index=True)
    name: str = Field(max_length=100, index=True)
    code: str = Field(max_length=100, index=True)
    parent_id: str | None = Field(default=None, index=True)
    level: int = Field(default=0, index=True)
    path: str = Field(default="", max_length=500)
    is_active: bool = Field(default=True, index=True)
    created_at: datetime = Field(default_factory=now_utc, index=True)
    updated_at: datetime = Field(default_factory=now_utc, index=True)


class UserOrgMembership(SQLModel, table=True):
    __tablename__ = "user_org_memberships"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "user_id"],
            ["users.tenant_id", "users.id"],
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "org_unit_id"],
            ["org_units.tenant_id", "org_units.id"],
            ondelete="CASCADE",
        ),
        Index("ix_user_org_memberships_tenant_user", "tenant_id", "user_id"),
        Index("ix_user_org_memberships_tenant_org", "tenant_id", "org_unit_id"),
    )

    tenant_id: str = Field(primary_key=True)
    user_id: str = Field(primary_key=True)
    org_unit_id: str = Field(primary_key=True)
    is_primary: bool = Field(default=False, index=True)
    created_at: datetime = Field(default_factory=now_utc, index=True)


class DataScopeMode(StrEnum):
    ALL = "ALL"
    SCOPED = "SCOPED"


class DataAccessPolicy(SQLModel, table=True):
    __tablename__ = "data_access_policies"
    __table_args__ = (
        UniqueConstraint("tenant_id", "user_id", name="uq_data_access_policies_tenant_user"),
        ForeignKeyConstraint(
            ["tenant_id", "user_id"],
            ["users.tenant_id", "users.id"],
            ondelete="CASCADE",
        ),
        Index("ix_data_access_policies_tenant_user", "tenant_id", "user_id"),
    )

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    tenant_id: str = Field(foreign_key="tenants.id", index=True)
    user_id: str = Field(index=True)
    scope_mode: DataScopeMode = Field(default=DataScopeMode.ALL, index=True)
    org_unit_ids: list[str] = Field(
        default_factory=list,
        sa_column=Column(JSON, nullable=False),
    )
    project_codes: list[str] = Field(
        default_factory=list,
        sa_column=Column(JSON, nullable=False),
    )
    area_codes: list[str] = Field(
        default_factory=list,
        sa_column=Column(JSON, nullable=False),
    )
    task_ids: list[str] = Field(
        default_factory=list,
        sa_column=Column(JSON, nullable=False),
    )
    created_at: datetime = Field(default_factory=now_utc, index=True)
    updated_at: datetime = Field(default_factory=now_utc, index=True)


class DroneVendor(StrEnum):
    DJI = "DJI"
    MAVLINK = "MAVLINK"
    FAKE = "FAKE"


class Drone(SQLModel, table=True):
    __tablename__ = "drones"
    __table_args__ = (
        UniqueConstraint("tenant_id", "name", name="uq_drones_tenant_name"),
        UniqueConstraint("tenant_id", "id", name="uq_drones_tenant_id_id"),
    )

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    tenant_id: str = Field(foreign_key="tenants.id", index=True)
    name: str = Field(index=True)
    vendor: DroneVendor
    capabilities: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False),
    )
    created_at: datetime = Field(default_factory=now_utc, index=True)
    updated_at: datetime = Field(default_factory=now_utc, index=True)


class DroneCredential(SQLModel, table=True):
    __tablename__ = "drone_credentials"

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    tenant_id: str = Field(foreign_key="tenants.id", index=True)
    drone_id: str = Field(foreign_key="drones.id", index=True, unique=True)
    secret: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False),
    )
    created_at: datetime = Field(default_factory=now_utc, index=True)


class AssetType(StrEnum):
    UAV = "UAV"
    PAYLOAD = "PAYLOAD"
    BATTERY = "BATTERY"
    CONTROLLER = "CONTROLLER"
    DOCK = "DOCK"


class AssetLifecycleStatus(StrEnum):
    REGISTERED = "REGISTERED"
    BOUND = "BOUND"
    RETIRED = "RETIRED"


class AssetAvailabilityStatus(StrEnum):
    AVAILABLE = "AVAILABLE"
    RESERVED = "RESERVED"
    IN_USE = "IN_USE"
    MAINTENANCE = "MAINTENANCE"
    UNAVAILABLE = "UNAVAILABLE"


class AssetHealthStatus(StrEnum):
    UNKNOWN = "UNKNOWN"
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    CRITICAL = "CRITICAL"


class MaintenanceWorkOrderStatus(StrEnum):
    OPEN = "OPEN"
    IN_PROGRESS = "IN_PROGRESS"
    CLOSED = "CLOSED"
    CANCELED = "CANCELED"


class Asset(SQLModel, table=True):
    __tablename__ = "assets"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_assets_tenant_id_id"),
        UniqueConstraint("tenant_id", "asset_type", "asset_code", name="uq_assets_tenant_type_code"),
        ForeignKeyConstraint(
            ["tenant_id", "bound_to_drone_id"],
            ["drones.tenant_id", "drones.id"],
            ondelete="SET NULL",
        ),
        Index("ix_assets_tenant_id_id", "tenant_id", "id"),
        Index("ix_assets_tenant_type", "tenant_id", "asset_type"),
        Index("ix_assets_tenant_lifecycle", "tenant_id", "lifecycle_status"),
        Index("ix_assets_tenant_bound_drone", "tenant_id", "bound_to_drone_id"),
        Index("ix_assets_tenant_availability", "tenant_id", "availability_status"),
        Index("ix_assets_tenant_health", "tenant_id", "health_status"),
        Index("ix_assets_tenant_region", "tenant_id", "region_code"),
    )

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    tenant_id: str = Field(foreign_key="tenants.id", index=True)
    asset_type: AssetType = Field(index=True)
    asset_code: str = Field(max_length=100, index=True)
    name: str = Field(max_length=100, index=True)
    serial_number: str | None = Field(default=None, max_length=100, index=True)
    lifecycle_status: AssetLifecycleStatus = Field(default=AssetLifecycleStatus.REGISTERED, index=True)
    availability_status: AssetAvailabilityStatus = Field(
        default=AssetAvailabilityStatus.AVAILABLE,
        index=True,
    )
    health_status: AssetHealthStatus = Field(default=AssetHealthStatus.UNKNOWN, index=True)
    health_score: int | None = Field(default=None, ge=0, le=100, index=True)
    region_code: str | None = Field(default=None, max_length=100, index=True)
    bound_to_drone_id: str | None = Field(default=None, index=True)
    detail: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False),
    )
    bound_at: datetime | None = Field(default=None, index=True)
    last_health_at: datetime | None = Field(default=None, index=True)
    retired_at: datetime | None = Field(default=None, index=True)
    retired_reason: str | None = Field(default=None, max_length=200)
    created_at: datetime = Field(default_factory=now_utc, index=True)
    updated_at: datetime = Field(default_factory=now_utc, index=True)


class AssetMaintenanceWorkOrder(SQLModel, table=True):
    __tablename__ = "asset_maintenance_workorders"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_asset_maintenance_workorders_tenant_id_id"),
        ForeignKeyConstraint(
            ["tenant_id", "asset_id"],
            ["assets.tenant_id", "assets.id"],
            ondelete="RESTRICT",
        ),
        Index("ix_asset_maintenance_workorders_tenant_id_id", "tenant_id", "id"),
        Index("ix_asset_maintenance_workorders_tenant_asset", "tenant_id", "asset_id"),
        Index("ix_asset_maintenance_workorders_tenant_status", "tenant_id", "status"),
    )

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    tenant_id: str = Field(foreign_key="tenants.id", index=True)
    asset_id: str = Field(index=True)
    title: str = Field(max_length=200)
    description: str | None = None
    priority: int = Field(default=5, ge=1, le=10, index=True)
    status: MaintenanceWorkOrderStatus = Field(default=MaintenanceWorkOrderStatus.OPEN, index=True)
    created_by: str = Field(index=True)
    assigned_to: str | None = Field(default=None, index=True)
    close_note: str | None = None
    created_at: datetime = Field(default_factory=now_utc, index=True)
    updated_at: datetime = Field(default_factory=now_utc, index=True)
    closed_at: datetime | None = Field(default=None, index=True)
    closed_by: str | None = Field(default=None, index=True)


class AssetMaintenanceHistory(SQLModel, table=True):
    __tablename__ = "asset_maintenance_histories"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_asset_maintenance_histories_tenant_id_id"),
        ForeignKeyConstraint(
            ["tenant_id", "workorder_id"],
            ["asset_maintenance_workorders.tenant_id", "asset_maintenance_workorders.id"],
            ondelete="CASCADE",
        ),
        Index("ix_asset_maintenance_histories_tenant_id_id", "tenant_id", "id"),
        Index("ix_asset_maintenance_histories_tenant_workorder", "tenant_id", "workorder_id"),
    )

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    tenant_id: str = Field(foreign_key="tenants.id", index=True)
    workorder_id: str = Field(index=True)
    action: str = Field(max_length=50, index=True)
    from_status: MaintenanceWorkOrderStatus | None = Field(default=None, index=True)
    to_status: MaintenanceWorkOrderStatus | None = Field(default=None, index=True)
    note: str | None = None
    actor_id: str | None = Field(default=None, index=True)
    detail: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False),
    )
    created_at: datetime = Field(default_factory=now_utc, index=True)


class ApprovalDecision(StrEnum):
    APPROVE = "APPROVE"
    REJECT = "REJECT"


class MissionPlanType(StrEnum):
    AREA_GRID = "AREA_GRID"
    ROUTE_WAYPOINTS = "ROUTE_WAYPOINTS"
    POINT_TASK = "POINT_TASK"


class Mission(SQLModel, table=True):
    __tablename__ = "missions"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_missions_tenant_id_id"),
        ForeignKeyConstraint(
            ["tenant_id", "drone_id"],
            ["drones.tenant_id", "drones.id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "org_unit_id"],
            ["org_units.tenant_id", "org_units.id"],
            ondelete="RESTRICT",
        ),
        Index("ix_missions_tenant_drone_id", "tenant_id", "drone_id"),
        Index("ix_missions_tenant_state", "tenant_id", "state"),
        Index("ix_missions_tenant_org_unit", "tenant_id", "org_unit_id"),
    )

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    tenant_id: str = Field(foreign_key="tenants.id", index=True)
    name: str = Field(index=True)
    drone_id: str | None = Field(default=None, index=True)
    org_unit_id: str | None = Field(default=None, index=True)
    project_code: str | None = Field(default=None, max_length=100, index=True)
    area_code: str | None = Field(default=None, max_length=100, index=True)
    plan_type: MissionPlanType
    payload: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False),
    )
    constraints: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False),
    )
    state: MissionState = Field(default=MissionState.DRAFT, index=True)
    created_by: str
    created_at: datetime = Field(default_factory=now_utc, index=True)
    updated_at: datetime = Field(default_factory=now_utc, index=True)


class Approval(SQLModel, table=True):
    __tablename__ = "approvals"

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    tenant_id: str = Field(foreign_key="tenants.id", index=True)
    mission_id: str = Field(foreign_key="missions.id", index=True)
    approver_id: str = Field(index=True)
    decision: ApprovalDecision
    comment: str | None = None
    created_at: datetime = Field(default_factory=now_utc, index=True)


class MissionRun(SQLModel, table=True):
    __tablename__ = "mission_runs"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "mission_id"],
            ["missions.tenant_id", "missions.id"],
            ondelete="RESTRICT",
        ),
        Index("ix_mission_runs_tenant_mission_id", "tenant_id", "mission_id"),
    )

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    tenant_id: str = Field(foreign_key="tenants.id", index=True)
    mission_id: str = Field(index=True)
    state: MissionState = Field(index=True)
    started_at: datetime = Field(default_factory=now_utc, index=True)
    ended_at: datetime | None = Field(default=None, index=True)


class TaskCenterDispatchMode(StrEnum):
    MANUAL = "MANUAL"
    AUTO = "AUTO"


class TaskTypeCatalog(SQLModel, table=True):
    __tablename__ = "task_type_catalogs"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_task_type_catalogs_tenant_id_id"),
        UniqueConstraint("tenant_id", "code", name="uq_task_type_catalogs_tenant_code"),
        Index("ix_task_type_catalogs_tenant_id_id", "tenant_id", "id"),
        Index("ix_task_type_catalogs_tenant_code", "tenant_id", "code"),
    )

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    tenant_id: str = Field(foreign_key="tenants.id", index=True)
    code: str = Field(max_length=50, index=True)
    name: str = Field(max_length=100, index=True)
    description: str | None = None
    is_active: bool = Field(default=True, index=True)
    created_by: str = Field(index=True)
    created_at: datetime = Field(default_factory=now_utc, index=True)
    updated_at: datetime = Field(default_factory=now_utc, index=True)


class TaskTemplate(SQLModel, table=True):
    __tablename__ = "task_templates"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_task_templates_tenant_id_id"),
        UniqueConstraint("tenant_id", "template_key", name="uq_task_templates_tenant_template_key"),
        ForeignKeyConstraint(
            ["tenant_id", "task_type_id"],
            ["task_type_catalogs.tenant_id", "task_type_catalogs.id"],
            ondelete="RESTRICT",
        ),
        Index("ix_task_templates_tenant_id_id", "tenant_id", "id"),
        Index("ix_task_templates_tenant_type", "tenant_id", "task_type_id"),
    )

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    tenant_id: str = Field(foreign_key="tenants.id", index=True)
    task_type_id: str = Field(index=True)
    template_key: str = Field(max_length=100, index=True)
    name: str = Field(max_length=100, index=True)
    description: str | None = None
    requires_approval: bool = Field(default=False, index=True)
    default_priority: int = Field(default=5, ge=1, le=10, index=True)
    default_risk_level: int = Field(default=3, ge=1, le=5, index=True)
    default_checklist: list[dict[str, Any]] = Field(
        default_factory=list,
        sa_column=Column(JSON, nullable=False),
    )
    default_payload: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False),
    )
    is_active: bool = Field(default=True, index=True)
    created_by: str = Field(index=True)
    created_at: datetime = Field(default_factory=now_utc, index=True)
    updated_at: datetime = Field(default_factory=now_utc, index=True)


class TaskCenterTask(SQLModel, table=True):
    __tablename__ = "task_center_tasks"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_task_center_tasks_tenant_id_id"),
        ForeignKeyConstraint(
            ["tenant_id", "task_type_id"],
            ["task_type_catalogs.tenant_id", "task_type_catalogs.id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "template_id"],
            ["task_templates.tenant_id", "task_templates.id"],
            ondelete="SET NULL",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "org_unit_id"],
            ["org_units.tenant_id", "org_units.id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "mission_id"],
            ["missions.tenant_id", "missions.id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "assigned_to"],
            ["users.tenant_id", "users.id"],
            ondelete="SET NULL",
        ),
        Index("ix_task_center_tasks_tenant_id_id", "tenant_id", "id"),
        Index("ix_task_center_tasks_tenant_state", "tenant_id", "state"),
        Index("ix_task_center_tasks_tenant_assigned", "tenant_id", "assigned_to"),
        Index("ix_task_center_tasks_tenant_org_unit", "tenant_id", "org_unit_id"),
        Index("ix_task_center_tasks_tenant_task_type", "tenant_id", "task_type_id"),
    )

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    tenant_id: str = Field(foreign_key="tenants.id", index=True)
    task_type_id: str = Field(index=True)
    template_id: str | None = Field(default=None, index=True)
    mission_id: str | None = Field(default=None, index=True)
    name: str = Field(max_length=200, index=True)
    description: str | None = None
    state: TaskCenterState = Field(default=TaskCenterState.DRAFT, index=True)
    requires_approval: bool = Field(default=False, index=True)
    priority: int = Field(default=5, ge=1, le=10, index=True)
    risk_level: int = Field(default=3, ge=1, le=5, index=True)
    org_unit_id: str | None = Field(default=None, index=True)
    project_code: str | None = Field(default=None, max_length=100, index=True)
    area_code: str | None = Field(default=None, max_length=100, index=True)
    area_geom: str = Field(default="")
    checklist: list[dict[str, Any]] = Field(
        default_factory=list,
        sa_column=Column(JSON, nullable=False),
    )
    attachments: list[dict[str, Any]] = Field(
        default_factory=list,
        sa_column=Column(JSON, nullable=False),
    )
    context_data: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False),
    )
    dispatch_mode: TaskCenterDispatchMode | None = Field(default=None, index=True)
    assigned_to: str | None = Field(default=None, index=True)
    dispatched_by: str | None = Field(default=None, index=True)
    dispatched_at: datetime | None = Field(default=None, index=True)
    started_at: datetime | None = Field(default=None, index=True)
    accepted_at: datetime | None = Field(default=None, index=True)
    archived_at: datetime | None = Field(default=None, index=True)
    canceled_at: datetime | None = Field(default=None, index=True)
    created_by: str = Field(index=True)
    created_at: datetime = Field(default_factory=now_utc, index=True)
    updated_at: datetime = Field(default_factory=now_utc, index=True)


class TaskCenterTaskHistory(SQLModel, table=True):
    __tablename__ = "task_center_task_histories"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_task_center_task_histories_tenant_id_id"),
        ForeignKeyConstraint(
            ["tenant_id", "task_id"],
            ["task_center_tasks.tenant_id", "task_center_tasks.id"],
            ondelete="CASCADE",
        ),
        Index("ix_task_center_task_histories_tenant_id_id", "tenant_id", "id"),
        Index("ix_task_center_task_histories_tenant_task", "tenant_id", "task_id"),
    )

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    tenant_id: str = Field(foreign_key="tenants.id", index=True)
    task_id: str = Field(index=True)
    action: str = Field(max_length=50, index=True)
    from_state: TaskCenterState | None = Field(default=None, index=True)
    to_state: TaskCenterState | None = Field(default=None, index=True)
    note: str | None = None
    actor_id: str | None = Field(default=None, index=True)
    detail: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False),
    )
    created_at: datetime = Field(default_factory=now_utc, index=True)


class AirspaceZoneType(StrEnum):
    NO_FLY = "NO_FLY"
    ALT_LIMIT = "ALT_LIMIT"
    SENSITIVE = "SENSITIVE"


class ComplianceReasonCode(StrEnum):
    AIRSPACE_NO_FLY = "AIRSPACE_NO_FLY"
    AIRSPACE_ALT_LIMIT_EXCEEDED = "AIRSPACE_ALT_LIMIT_EXCEEDED"
    AIRSPACE_SENSITIVE_RESTRICTED = "AIRSPACE_SENSITIVE_RESTRICTED"
    PREFLIGHT_CHECKLIST_REQUIRED = "PREFLIGHT_CHECKLIST_REQUIRED"
    PREFLIGHT_CHECKLIST_INCOMPLETE = "PREFLIGHT_CHECKLIST_INCOMPLETE"
    COMMAND_GEOFENCE_BLOCKED = "COMMAND_GEOFENCE_BLOCKED"
    COMMAND_ALTITUDE_BLOCKED = "COMMAND_ALTITUDE_BLOCKED"
    COMMAND_SENSITIVE_RESTRICTED = "COMMAND_SENSITIVE_RESTRICTED"


class PreflightChecklistStatus(StrEnum):
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    WAIVED = "WAIVED"


class AirspaceZone(SQLModel, table=True):
    __tablename__ = "airspace_zones"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_airspace_zones_tenant_id_id"),
        Index("ix_airspace_zones_tenant_id_id", "tenant_id", "id"),
        Index("ix_airspace_zones_tenant_type", "tenant_id", "zone_type"),
    )

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    tenant_id: str = Field(foreign_key="tenants.id", index=True)
    name: str = Field(max_length=100, index=True)
    zone_type: AirspaceZoneType = Field(index=True)
    area_code: str | None = Field(default=None, max_length=100, index=True)
    geom_wkt: str
    max_alt_m: float | None = Field(default=None, ge=0)
    is_active: bool = Field(default=True, index=True)
    detail: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False),
    )
    created_by: str = Field(index=True)
    created_at: datetime = Field(default_factory=now_utc, index=True)
    updated_at: datetime = Field(default_factory=now_utc, index=True)


class PreflightChecklistTemplate(SQLModel, table=True):
    __tablename__ = "preflight_checklist_templates"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_preflight_templates_tenant_id_id"),
        Index("ix_preflight_templates_tenant_id_id", "tenant_id", "id"),
    )

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    tenant_id: str = Field(foreign_key="tenants.id", index=True)
    name: str = Field(max_length=100, index=True)
    description: str | None = None
    items: list[dict[str, Any]] = Field(
        default_factory=list,
        sa_column=Column(JSON, nullable=False),
    )
    require_approval_before_run: bool = Field(default=True, index=True)
    is_active: bool = Field(default=True, index=True)
    created_by: str = Field(index=True)
    created_at: datetime = Field(default_factory=now_utc, index=True)
    updated_at: datetime = Field(default_factory=now_utc, index=True)


class MissionPreflightChecklist(SQLModel, table=True):
    __tablename__ = "mission_preflight_checklists"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_mission_preflight_checklists_tenant_id_id"),
        UniqueConstraint(
            "tenant_id",
            "mission_id",
            name="uq_mission_preflight_checklists_tenant_mission",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "mission_id"],
            ["missions.tenant_id", "missions.id"],
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "template_id"],
            ["preflight_checklist_templates.tenant_id", "preflight_checklist_templates.id"],
            ondelete="SET NULL",
        ),
        Index("ix_mission_preflight_checklists_tenant_id_id", "tenant_id", "id"),
        Index("ix_mission_preflight_checklists_tenant_mission", "tenant_id", "mission_id"),
    )

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    tenant_id: str = Field(foreign_key="tenants.id", index=True)
    mission_id: str = Field(index=True)
    template_id: str | None = Field(default=None, index=True)
    status: PreflightChecklistStatus = Field(default=PreflightChecklistStatus.PENDING, index=True)
    required_items: list[dict[str, Any]] = Field(
        default_factory=list,
        sa_column=Column(JSON, nullable=False),
    )
    completed_items: list[dict[str, Any]] = Field(
        default_factory=list,
        sa_column=Column(JSON, nullable=False),
    )
    evidence: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False),
    )
    updated_by: str | None = Field(default=None, index=True)
    created_at: datetime = Field(default_factory=now_utc, index=True)
    updated_at: datetime = Field(default_factory=now_utc, index=True)
    completed_at: datetime | None = Field(default=None, index=True)


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


class CommandStatus(StrEnum):
    PENDING = "PENDING"
    ACKED = "ACKED"
    FAILED = "FAILED"
    TIMEOUT = "TIMEOUT"


class CommandRequestRecord(SQLModel, table=True):
    __tablename__ = "command_requests"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "id",
            name="uq_command_requests_tenant_id_id",
        ),
        UniqueConstraint(
            "tenant_id",
            "idempotency_key",
            name="uq_command_requests_tenant_idempotency",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "drone_id"],
            ["drones.tenant_id", "drones.id"],
            ondelete="RESTRICT",
        ),
        Index("ix_command_requests_tenant_id_id", "tenant_id", "id"),
        Index("ix_command_requests_tenant_drone_id", "tenant_id", "drone_id"),
        Index("ix_command_requests_tenant_compliance", "tenant_id", "compliance_passed"),
        Index("ix_command_requests_tenant_reason", "tenant_id", "compliance_reason_code"),
    )

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    tenant_id: str = Field(foreign_key="tenants.id", index=True)
    drone_id: str = Field(index=True)
    command_type: CommandType = Field(index=True)
    params: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False),
    )
    idempotency_key: str = Field(index=True)
    expect_ack: bool = Field(default=True)
    status: CommandStatus = Field(default=CommandStatus.PENDING, index=True)
    ack_ok: bool | None = Field(default=None)
    ack_message: str | None = None
    compliance_passed: bool | None = Field(default=None, index=True)
    compliance_reason_code: ComplianceReasonCode | None = Field(default=None, index=True)
    compliance_detail: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False),
    )
    attempts: int = Field(default=0)
    issued_by: str | None = Field(default=None, index=True)
    issued_at: datetime = Field(default_factory=now_utc, index=True)
    updated_at: datetime = Field(default_factory=now_utc, index=True)


class AlertType(StrEnum):
    LOW_BATTERY = "LOW_BATTERY"
    LINK_LOSS = "LINK_LOSS"
    GEOFENCE_BREACH = "GEOFENCE_BREACH"


class AlertSeverity(StrEnum):
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


class AlertPriority(StrEnum):
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"


class AlertRouteStatus(StrEnum):
    UNROUTED = "UNROUTED"
    ROUTED = "ROUTED"


class AlertRouteChannel(StrEnum):
    IN_APP = "IN_APP"
    EMAIL = "EMAIL"
    SMS = "SMS"
    WEBHOOK = "WEBHOOK"


class AlertRouteDeliveryStatus(StrEnum):
    SENT = "SENT"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


class AlertHandlingActionType(StrEnum):
    ACK = "ACK"
    DISPATCH = "DISPATCH"
    VERIFY = "VERIFY"
    REVIEW = "REVIEW"
    CLOSE = "CLOSE"


class RawDataType(StrEnum):
    TELEMETRY = "TELEMETRY"
    IMAGE = "IMAGE"
    VIDEO = "VIDEO"
    DOCUMENT = "DOCUMENT"
    LOG = "LOG"


class OutcomeSourceType(StrEnum):
    INSPECTION_OBSERVATION = "INSPECTION_OBSERVATION"
    ALERT = "ALERT"
    MANUAL = "MANUAL"


class OutcomeType(StrEnum):
    DEFECT = "DEFECT"
    HIDDEN_RISK = "HIDDEN_RISK"
    INCIDENT = "INCIDENT"
    OTHER = "OTHER"


class OutcomeStatus(StrEnum):
    NEW = "NEW"
    IN_REVIEW = "IN_REVIEW"
    VERIFIED = "VERIFIED"
    ARCHIVED = "ARCHIVED"


class AiJobType(StrEnum):
    SUMMARY = "SUMMARY"
    SUGGESTION = "SUGGESTION"


class AiTriggerMode(StrEnum):
    MANUAL = "MANUAL"
    SCHEDULED = "SCHEDULED"
    NEAR_REALTIME = "NEAR_REALTIME"


class AiJobStatus(StrEnum):
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"


class AiRunStatus(StrEnum):
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"


class AiEvidenceType(StrEnum):
    MODEL_CONFIG = "MODEL_CONFIG"
    INPUT_SNAPSHOT = "INPUT_SNAPSHOT"
    OUTPUT_SNAPSHOT = "OUTPUT_SNAPSHOT"
    TRACE = "TRACE"


class AiOutputReviewStatus(StrEnum):
    PENDING_REVIEW = "PENDING_REVIEW"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    OVERRIDDEN = "OVERRIDDEN"


class AiReviewActionType(StrEnum):
    APPROVE = "APPROVE"
    REJECT = "REJECT"
    OVERRIDE = "OVERRIDE"


class KpiWindowType(StrEnum):
    DAILY = "DAILY"
    WEEKLY = "WEEKLY"
    MONTHLY = "MONTHLY"
    QUARTERLY = "QUARTERLY"
    CUSTOM = "CUSTOM"


class KpiHeatmapSource(StrEnum):
    OUTCOME = "OUTCOME"
    ALERT = "ALERT"


class OpenWebhookAuthType(StrEnum):
    HMAC_SHA256 = "HMAC_SHA256"


class OpenWebhookDeliveryStatus(StrEnum):
    SENT = "SENT"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


class OpenAdapterIngressStatus(StrEnum):
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"


class AlertStatus(StrEnum):
    OPEN = "OPEN"
    ACKED = "ACKED"
    CLOSED = "CLOSED"


class AlertRecord(SQLModel, table=True):
    __tablename__ = "alerts"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_alerts_tenant_id_id"),
        Index("ix_alerts_tenant_id_id", "tenant_id", "id"),
    )

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    tenant_id: str = Field(foreign_key="tenants.id", index=True)
    drone_id: str = Field(index=True)
    alert_type: AlertType = Field(index=True)
    severity: AlertSeverity = Field(index=True)
    priority_level: AlertPriority = Field(default=AlertPriority.P3, index=True)
    status: AlertStatus = Field(default=AlertStatus.OPEN, index=True)
    route_status: AlertRouteStatus = Field(default=AlertRouteStatus.UNROUTED, index=True)
    message: str
    detail: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False),
    )
    first_seen_at: datetime = Field(default_factory=now_utc, index=True)
    last_seen_at: datetime = Field(default_factory=now_utc, index=True)
    acked_by: str | None = Field(default=None, index=True)
    acked_at: datetime | None = Field(default=None, index=True)
    closed_by: str | None = Field(default=None, index=True)
    closed_at: datetime | None = Field(default=None, index=True)
    routed_at: datetime | None = Field(default=None, index=True)


class AlertRoutingRule(SQLModel, table=True):
    __tablename__ = "alert_routing_rules"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_alert_routing_rules_tenant_id_id"),
        Index("ix_alert_routing_rules_tenant_id_id", "tenant_id", "id"),
        Index("ix_alert_routing_rules_tenant_priority", "tenant_id", "priority_level"),
        Index("ix_alert_routing_rules_tenant_type", "tenant_id", "alert_type"),
    )

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    tenant_id: str = Field(foreign_key="tenants.id", index=True)
    priority_level: AlertPriority = Field(index=True)
    alert_type: AlertType | None = Field(default=None, index=True)
    channel: AlertRouteChannel = Field(default=AlertRouteChannel.IN_APP, index=True)
    target: str = Field(max_length=200)
    is_active: bool = Field(default=True, index=True)
    detail: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False),
    )
    created_by: str = Field(index=True)
    created_at: datetime = Field(default_factory=now_utc, index=True)
    updated_at: datetime = Field(default_factory=now_utc, index=True)


class AlertRouteLog(SQLModel, table=True):
    __tablename__ = "alert_route_logs"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_alert_route_logs_tenant_id_id"),
        Index("ix_alert_route_logs_tenant_id_id", "tenant_id", "id"),
        Index("ix_alert_route_logs_tenant_alert", "tenant_id", "alert_id"),
        Index("ix_alert_route_logs_tenant_priority", "tenant_id", "priority_level"),
    )

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    tenant_id: str = Field(foreign_key="tenants.id", index=True)
    alert_id: str = Field(foreign_key="alerts.id", index=True)
    rule_id: str | None = Field(default=None, foreign_key="alert_routing_rules.id", index=True)
    priority_level: AlertPriority = Field(index=True)
    channel: AlertRouteChannel = Field(default=AlertRouteChannel.IN_APP, index=True)
    target: str = Field(max_length=200)
    delivery_status: AlertRouteDeliveryStatus = Field(default=AlertRouteDeliveryStatus.SENT, index=True)
    detail: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False),
    )
    created_at: datetime = Field(default_factory=now_utc, index=True)


class AlertHandlingAction(SQLModel, table=True):
    __tablename__ = "alert_handling_actions"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_alert_handling_actions_tenant_id_id"),
        Index("ix_alert_handling_actions_tenant_id_id", "tenant_id", "id"),
        Index("ix_alert_handling_actions_tenant_alert", "tenant_id", "alert_id"),
    )

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    tenant_id: str = Field(foreign_key="tenants.id", index=True)
    alert_id: str = Field(foreign_key="alerts.id", index=True)
    action_type: AlertHandlingActionType = Field(index=True)
    note: str | None = None
    actor_id: str | None = Field(default=None, index=True)
    detail: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False),
    )
    created_at: datetime = Field(default_factory=now_utc, index=True)


class RawDataCatalogRecord(SQLModel, table=True):
    __tablename__ = "raw_data_catalog_records"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_raw_data_catalog_records_tenant_id_id"),
        Index("ix_raw_data_catalog_records_tenant_id_id", "tenant_id", "id"),
        Index("ix_raw_data_catalog_records_tenant_type", "tenant_id", "data_type"),
        Index("ix_raw_data_catalog_records_tenant_task", "tenant_id", "task_id"),
        Index("ix_raw_data_catalog_records_tenant_mission", "tenant_id", "mission_id"),
    )

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    tenant_id: str = Field(foreign_key="tenants.id", index=True)
    task_id: str | None = Field(default=None, foreign_key="inspection_tasks.id", index=True)
    mission_id: str | None = Field(default=None, foreign_key="missions.id", index=True)
    data_type: RawDataType = Field(index=True)
    source_uri: str
    checksum: str | None = Field(default=None, max_length=200, index=True)
    meta: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False),
    )
    captured_at: datetime = Field(default_factory=now_utc, index=True)
    created_by: str = Field(index=True)
    created_at: datetime = Field(default_factory=now_utc, index=True)


class OutcomeCatalogRecord(SQLModel, table=True):
    __tablename__ = "outcome_catalog_records"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_outcome_catalog_records_tenant_id_id"),
        Index("ix_outcome_catalog_records_tenant_id_id", "tenant_id", "id"),
        Index("ix_outcome_catalog_records_tenant_status", "tenant_id", "status"),
        Index("ix_outcome_catalog_records_tenant_type", "tenant_id", "outcome_type"),
        Index("ix_outcome_catalog_records_tenant_task", "tenant_id", "task_id"),
        Index("ix_outcome_catalog_records_tenant_mission", "tenant_id", "mission_id"),
        Index("ix_outcome_catalog_records_tenant_source", "tenant_id", "source_type", "source_id"),
    )

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    tenant_id: str = Field(foreign_key="tenants.id", index=True)
    task_id: str | None = Field(default=None, foreign_key="inspection_tasks.id", index=True)
    mission_id: str | None = Field(default=None, foreign_key="missions.id", index=True)
    source_type: OutcomeSourceType = Field(index=True)
    source_id: str = Field(index=True)
    outcome_type: OutcomeType = Field(index=True)
    status: OutcomeStatus = Field(default=OutcomeStatus.NEW, index=True)
    point_lat: float | None = Field(default=None)
    point_lon: float | None = Field(default=None)
    alt_m: float | None = Field(default=None)
    confidence: float | None = Field(default=None, ge=0, le=1)
    payload: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False),
    )
    reviewed_by: str | None = Field(default=None, index=True)
    reviewed_at: datetime | None = Field(default=None, index=True)
    created_by: str = Field(index=True)
    created_at: datetime = Field(default_factory=now_utc, index=True)
    updated_at: datetime = Field(default_factory=now_utc, index=True)


class AiAnalysisJob(SQLModel, table=True):
    __tablename__ = "ai_analysis_jobs"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_ai_analysis_jobs_tenant_id_id"),
        Index("ix_ai_analysis_jobs_tenant_id_id", "tenant_id", "id"),
        Index("ix_ai_analysis_jobs_tenant_task", "tenant_id", "task_id"),
        Index("ix_ai_analysis_jobs_tenant_mission", "tenant_id", "mission_id"),
        Index("ix_ai_analysis_jobs_tenant_topic", "tenant_id", "topic"),
        Index("ix_ai_analysis_jobs_tenant_type", "tenant_id", "job_type"),
        Index("ix_ai_analysis_jobs_tenant_status", "tenant_id", "status"),
    )

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    tenant_id: str = Field(foreign_key="tenants.id", index=True)
    task_id: str | None = Field(default=None, foreign_key="inspection_tasks.id", index=True)
    mission_id: str | None = Field(default=None, foreign_key="missions.id", index=True)
    topic: str | None = Field(default=None, max_length=120, index=True)
    job_type: AiJobType = Field(default=AiJobType.SUMMARY, index=True)
    trigger_mode: AiTriggerMode = Field(default=AiTriggerMode.MANUAL, index=True)
    status: AiJobStatus = Field(default=AiJobStatus.ACTIVE, index=True)
    model_provider: str = Field(default="builtin", max_length=80)
    model_name: str = Field(default="uav-assistant-lite", max_length=120)
    model_version: str = Field(default="phase14.v1", max_length=120)
    threshold_config: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False),
    )
    input_config: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False),
    )
    created_by: str = Field(index=True)
    created_at: datetime = Field(default_factory=now_utc, index=True)
    updated_at: datetime = Field(default_factory=now_utc, index=True)


class AiAnalysisRun(SQLModel, table=True):
    __tablename__ = "ai_analysis_runs"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_ai_analysis_runs_tenant_id_id"),
        Index("ix_ai_analysis_runs_tenant_id_id", "tenant_id", "id"),
        Index("ix_ai_analysis_runs_tenant_job", "tenant_id", "job_id"),
        Index("ix_ai_analysis_runs_tenant_status", "tenant_id", "status"),
        Index("ix_ai_analysis_runs_tenant_retry_of", "tenant_id", "retry_of_run_id"),
    )

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    tenant_id: str = Field(foreign_key="tenants.id", index=True)
    job_id: str = Field(foreign_key="ai_analysis_jobs.id", index=True)
    retry_of_run_id: str | None = Field(default=None, foreign_key="ai_analysis_runs.id", index=True)
    retry_count: int = Field(default=0, ge=0)
    status: AiRunStatus = Field(default=AiRunStatus.RUNNING, index=True)
    trigger_mode: AiTriggerMode = Field(default=AiTriggerMode.MANUAL, index=True)
    input_hash: str | None = Field(default=None, max_length=200, index=True)
    output_hash: str | None = Field(default=None, max_length=200, index=True)
    metrics: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False),
    )
    error_message: str | None = None
    started_at: datetime = Field(default_factory=now_utc, index=True)
    finished_at: datetime | None = Field(default=None, index=True)
    triggered_by: str = Field(index=True)
    created_at: datetime = Field(default_factory=now_utc, index=True)
    updated_at: datetime = Field(default_factory=now_utc, index=True)


class AiAnalysisOutput(SQLModel, table=True):
    __tablename__ = "ai_analysis_outputs"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_ai_analysis_outputs_tenant_id_id"),
        Index("ix_ai_analysis_outputs_tenant_id_id", "tenant_id", "id"),
        Index("ix_ai_analysis_outputs_tenant_job", "tenant_id", "job_id"),
        Index("ix_ai_analysis_outputs_tenant_run", "tenant_id", "run_id"),
        Index("ix_ai_analysis_outputs_tenant_review", "tenant_id", "review_status"),
    )

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    tenant_id: str = Field(foreign_key="tenants.id", index=True)
    job_id: str = Field(foreign_key="ai_analysis_jobs.id", index=True)
    run_id: str = Field(foreign_key="ai_analysis_runs.id", index=True)
    summary_text: str = Field(default="")
    suggestion_text: str = Field(default="")
    payload: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False),
    )
    control_allowed: bool = Field(default=False, index=True)
    review_status: AiOutputReviewStatus = Field(default=AiOutputReviewStatus.PENDING_REVIEW, index=True)
    reviewed_by: str | None = Field(default=None, index=True)
    reviewed_at: datetime | None = Field(default=None, index=True)
    review_note: str | None = None
    override_payload: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False),
    )
    created_at: datetime = Field(default_factory=now_utc, index=True)
    updated_at: datetime = Field(default_factory=now_utc, index=True)


class AiEvidenceRecord(SQLModel, table=True):
    __tablename__ = "ai_evidence_records"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_ai_evidence_records_tenant_id_id"),
        Index("ix_ai_evidence_records_tenant_id_id", "tenant_id", "id"),
        Index("ix_ai_evidence_records_tenant_run", "tenant_id", "run_id"),
        Index("ix_ai_evidence_records_tenant_output", "tenant_id", "output_id"),
        Index("ix_ai_evidence_records_tenant_type", "tenant_id", "evidence_type"),
    )

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    tenant_id: str = Field(foreign_key="tenants.id", index=True)
    run_id: str = Field(foreign_key="ai_analysis_runs.id", index=True)
    output_id: str | None = Field(default=None, foreign_key="ai_analysis_outputs.id", index=True)
    evidence_type: AiEvidenceType = Field(index=True)
    content_hash: str = Field(max_length=200, index=True)
    payload: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False),
    )
    created_at: datetime = Field(default_factory=now_utc, index=True)


class AiOutputReviewAction(SQLModel, table=True):
    __tablename__ = "ai_output_review_actions"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_ai_output_review_actions_tenant_id_id"),
        Index("ix_ai_output_review_actions_tenant_id_id", "tenant_id", "id"),
        Index("ix_ai_output_review_actions_tenant_output", "tenant_id", "output_id"),
        Index("ix_ai_output_review_actions_tenant_run", "tenant_id", "run_id"),
        Index("ix_ai_output_review_actions_tenant_action", "tenant_id", "action_type"),
    )

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    tenant_id: str = Field(foreign_key="tenants.id", index=True)
    output_id: str = Field(foreign_key="ai_analysis_outputs.id", index=True)
    run_id: str = Field(foreign_key="ai_analysis_runs.id", index=True)
    action_type: AiReviewActionType = Field(index=True)
    note: str | None = None
    actor_id: str = Field(index=True)
    detail: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False),
    )
    created_at: datetime = Field(default_factory=now_utc, index=True)


class KpiSnapshotRecord(SQLModel, table=True):
    __tablename__ = "kpi_snapshot_records"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_kpi_snapshot_records_tenant_id_id"),
        Index("ix_kpi_snapshot_records_tenant_id_id", "tenant_id", "id"),
        Index("ix_kpi_snapshot_records_tenant_window", "tenant_id", "window_type"),
        Index("ix_kpi_snapshot_records_tenant_period", "tenant_id", "from_ts", "to_ts"),
    )

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    tenant_id: str = Field(foreign_key="tenants.id", index=True)
    window_type: KpiWindowType = Field(default=KpiWindowType.CUSTOM, index=True)
    from_ts: datetime = Field(index=True)
    to_ts: datetime = Field(index=True)
    metrics: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False),
    )
    generated_by: str = Field(index=True)
    generated_at: datetime = Field(default_factory=now_utc, index=True)


class KpiHeatmapBinRecord(SQLModel, table=True):
    __tablename__ = "kpi_heatmap_bin_records"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_kpi_heatmap_bin_records_tenant_id_id"),
        Index("ix_kpi_heatmap_bin_records_tenant_id_id", "tenant_id", "id"),
        Index("ix_kpi_heatmap_bin_records_tenant_snapshot", "tenant_id", "snapshot_id"),
        Index("ix_kpi_heatmap_bin_records_tenant_source", "tenant_id", "source"),
    )

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    tenant_id: str = Field(foreign_key="tenants.id", index=True)
    snapshot_id: str = Field(foreign_key="kpi_snapshot_records.id", index=True)
    source: KpiHeatmapSource = Field(index=True)
    grid_lat: float = Field(index=True)
    grid_lon: float = Field(index=True)
    count: int = Field(default=0, ge=0)
    detail: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False),
    )
    created_at: datetime = Field(default_factory=now_utc, index=True)


class OpenPlatformCredential(SQLModel, table=True):
    __tablename__ = "open_platform_credentials"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_open_platform_credentials_tenant_id_id"),
        UniqueConstraint("tenant_id", "key_id", name="uq_open_platform_credentials_tenant_key"),
        Index("ix_open_platform_credentials_tenant_id_id", "tenant_id", "id"),
        Index("ix_open_platform_credentials_tenant_key", "tenant_id", "key_id"),
    )

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    tenant_id: str = Field(foreign_key="tenants.id", index=True)
    key_id: str = Field(max_length=120, index=True)
    api_key: str = Field(max_length=200, index=True)
    signing_secret: str = Field(max_length=200)
    is_active: bool = Field(default=True, index=True)
    created_by: str | None = Field(default=None, index=True)
    created_at: datetime = Field(default_factory=now_utc, index=True)
    updated_at: datetime = Field(default_factory=now_utc, index=True)


class OpenWebhookEndpoint(SQLModel, table=True):
    __tablename__ = "open_webhook_endpoints"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_open_webhook_endpoints_tenant_id_id"),
        Index("ix_open_webhook_endpoints_tenant_id_id", "tenant_id", "id"),
        Index("ix_open_webhook_endpoints_tenant_event", "tenant_id", "event_type"),
    )

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    tenant_id: str = Field(foreign_key="tenants.id", index=True)
    name: str = Field(max_length=120, index=True)
    endpoint_url: str
    event_type: str = Field(max_length=120, index=True)
    credential_id: str | None = Field(default=None, foreign_key="open_platform_credentials.id", index=True)
    auth_type: OpenWebhookAuthType = Field(default=OpenWebhookAuthType.HMAC_SHA256, index=True)
    is_active: bool = Field(default=True, index=True)
    extra_headers: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False),
    )
    created_by: str = Field(index=True)
    created_at: datetime = Field(default_factory=now_utc, index=True)
    updated_at: datetime = Field(default_factory=now_utc, index=True)


class OpenWebhookDelivery(SQLModel, table=True):
    __tablename__ = "open_webhook_deliveries"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_open_webhook_deliveries_tenant_id_id"),
        Index("ix_open_webhook_deliveries_tenant_id_id", "tenant_id", "id"),
        Index("ix_open_webhook_deliveries_tenant_endpoint", "tenant_id", "endpoint_id"),
    )

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    tenant_id: str = Field(foreign_key="tenants.id", index=True)
    endpoint_id: str = Field(foreign_key="open_webhook_endpoints.id", index=True)
    event_type: str = Field(max_length=120, index=True)
    payload: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False),
    )
    signature: str | None = Field(default=None, max_length=200, index=True)
    request_headers: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False),
    )
    status: OpenWebhookDeliveryStatus = Field(default=OpenWebhookDeliveryStatus.SENT, index=True)
    detail: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False),
    )
    created_at: datetime = Field(default_factory=now_utc, index=True)


class OpenAdapterIngressEvent(SQLModel, table=True):
    __tablename__ = "open_adapter_ingress_events"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_open_adapter_ingress_events_tenant_id_id"),
        Index("ix_open_adapter_ingress_events_tenant_id_id", "tenant_id", "id"),
        Index("ix_open_adapter_ingress_events_tenant_key", "tenant_id", "key_id"),
    )

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    tenant_id: str = Field(foreign_key="tenants.id", index=True)
    key_id: str = Field(max_length=120, index=True)
    event_type: str = Field(max_length=120, index=True)
    payload: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False),
    )
    signature_valid: bool = Field(default=False, index=True)
    status: OpenAdapterIngressStatus = Field(default=OpenAdapterIngressStatus.ACCEPTED, index=True)
    detail: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False),
    )
    created_at: datetime = Field(default_factory=now_utc, index=True)


class Command(BaseModel):
    tenant_id: str
    command_id: str = PydanticField(default_factory=lambda: str(uuid4()))
    drone_id: str
    ts: datetime = PydanticField(default_factory=now_utc)
    type: CommandType
    params: dict[str, Any] = PydanticField(default_factory=dict)
    idempotency_key: str
    expect_ack: bool = True


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


class RoleTemplateRead(BaseModel):
    key: str
    name: str
    description: str
    permissions: list[str]


class RoleFromTemplateCreateRequest(BaseModel):
    template_key: str
    name: str | None = None


class UserRoleBatchBindRequest(BaseModel):
    role_ids: list[str] = PydanticField(default_factory=list)


class UserRoleBatchBindItemRead(BaseModel):
    role_id: str
    status: str


class UserRoleBatchBindRead(BaseModel):
    user_id: str
    requested_count: int
    bound_count: int
    already_bound_count: int
    denied_count: int
    missing_count: int
    results: list[UserRoleBatchBindItemRead]


class OrgUnitCreate(BaseModel):
    name: str
    code: str
    parent_id: str | None = None
    is_active: bool = True


class OrgUnitUpdate(BaseModel):
    name: str | None = None
    code: str | None = None
    parent_id: str | None = None
    is_active: bool | None = None


class OrgUnitRead(ORMReadModel):
    id: str
    tenant_id: str
    name: str
    code: str
    parent_id: str | None
    level: int
    path: str
    is_active: bool
    created_at: datetime
    updated_at: datetime


class UserOrgMembershipBindRequest(BaseModel):
    is_primary: bool = False


class UserOrgMembershipLinkRead(ORMReadModel):
    tenant_id: str
    user_id: str
    org_unit_id: str
    is_primary: bool
    created_at: datetime


class DataAccessPolicyUpdate(BaseModel):
    scope_mode: DataScopeMode = DataScopeMode.SCOPED
    org_unit_ids: list[str] = PydanticField(default_factory=list)
    project_codes: list[str] = PydanticField(default_factory=list)
    area_codes: list[str] = PydanticField(default_factory=list)
    task_ids: list[str] = PydanticField(default_factory=list)


class DataAccessPolicyRead(ORMReadModel):
    id: str
    tenant_id: str
    user_id: str
    scope_mode: DataScopeMode
    org_unit_ids: list[str]
    project_codes: list[str]
    area_codes: list[str]
    task_ids: list[str]
    created_at: datetime
    updated_at: datetime


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


class DroneCreate(BaseModel):
    name: str
    vendor: DroneVendor
    capabilities: dict[str, Any] = PydanticField(default_factory=dict)


class DroneUpdate(BaseModel):
    name: str | None = None
    vendor: DroneVendor | None = None
    capabilities: dict[str, Any] | None = None


class DroneRead(ORMReadModel):
    id: str
    tenant_id: str
    name: str
    vendor: DroneVendor
    capabilities: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class AssetCreate(BaseModel):
    asset_type: AssetType
    asset_code: str
    name: str
    serial_number: str | None = None
    detail: dict[str, Any] = PydanticField(default_factory=dict)


class AssetBindRequest(BaseModel):
    bound_to_drone_id: str


class AssetAvailabilityUpdateRequest(BaseModel):
    availability_status: AssetAvailabilityStatus
    region_code: str | None = None


class AssetHealthUpdateRequest(BaseModel):
    health_status: AssetHealthStatus
    health_score: int | None = PydanticField(default=None, ge=0, le=100)
    detail: dict[str, Any] = PydanticField(default_factory=dict)


class MaintenanceWorkOrderCreate(BaseModel):
    asset_id: str
    title: str
    description: str | None = None
    priority: int = PydanticField(default=5, ge=1, le=10)
    assigned_to: str | None = None
    note: str | None = None


class MaintenanceWorkOrderTransitionRequest(BaseModel):
    status: MaintenanceWorkOrderStatus
    assigned_to: str | None = None
    note: str | None = None


class MaintenanceWorkOrderCloseRequest(BaseModel):
    note: str | None = None


class AssetRetireRequest(BaseModel):
    reason: str


class AssetRead(ORMReadModel):
    id: str
    tenant_id: str
    asset_type: AssetType
    asset_code: str
    name: str
    serial_number: str | None
    lifecycle_status: AssetLifecycleStatus
    availability_status: AssetAvailabilityStatus
    health_status: AssetHealthStatus
    health_score: int | None
    region_code: str | None
    bound_to_drone_id: str | None
    detail: dict[str, Any]
    bound_at: datetime | None
    last_health_at: datetime | None
    retired_at: datetime | None
    retired_reason: str | None
    created_at: datetime
    updated_at: datetime


class AssetPoolRegionSummaryRead(BaseModel):
    region_code: str
    total_assets: int
    available_assets: int
    by_type: dict[str, int]
    by_availability: dict[str, int]
    healthy_assets: int
    average_health_score: float | None


class MaintenanceWorkOrderRead(ORMReadModel):
    id: str
    tenant_id: str
    asset_id: str
    title: str
    description: str | None
    priority: int
    status: MaintenanceWorkOrderStatus
    created_by: str
    assigned_to: str | None
    close_note: str | None
    created_at: datetime
    updated_at: datetime
    closed_at: datetime | None
    closed_by: str | None


class MaintenanceWorkOrderHistoryRead(ORMReadModel):
    id: str
    tenant_id: str
    workorder_id: str
    action: str
    from_status: MaintenanceWorkOrderStatus | None
    to_status: MaintenanceWorkOrderStatus | None
    note: str | None
    actor_id: str | None
    detail: dict[str, Any]
    created_at: datetime


class MissionCreate(BaseModel):
    name: str
    drone_id: str | None = None
    org_unit_id: str | None = None
    project_code: str | None = None
    area_code: str | None = None
    type: MissionPlanType
    payload: dict[str, Any] = PydanticField(default_factory=dict)
    constraints: dict[str, Any] = PydanticField(default_factory=dict)


class MissionUpdate(BaseModel):
    name: str | None = None
    drone_id: str | None = None
    org_unit_id: str | None = None
    project_code: str | None = None
    area_code: str | None = None
    payload: dict[str, Any] | None = None
    constraints: dict[str, Any] | None = None


class MissionRead(ORMReadModel):
    id: str
    tenant_id: str
    name: str
    drone_id: str | None
    org_unit_id: str | None
    project_code: str | None
    area_code: str | None
    plan_type: MissionPlanType
    payload: dict[str, Any]
    constraints: dict[str, Any]
    state: MissionState
    created_by: str
    created_at: datetime
    updated_at: datetime


class MissionApprovalRequest(BaseModel):
    decision: ApprovalDecision
    comment: str | None = None


class ApprovalRead(ORMReadModel):
    id: str
    tenant_id: str
    mission_id: str
    approver_id: str
    decision: ApprovalDecision
    comment: str | None = None
    created_at: datetime


class MissionTransitionRequest(BaseModel):
    target_state: MissionState


class AirspaceZoneCreate(BaseModel):
    name: str
    zone_type: AirspaceZoneType
    area_code: str | None = None
    geom_wkt: str
    max_alt_m: float | None = PydanticField(default=None, ge=0)
    is_active: bool = True
    detail: dict[str, Any] = PydanticField(default_factory=dict)


class AirspaceZoneRead(ORMReadModel):
    id: str
    tenant_id: str
    name: str
    zone_type: AirspaceZoneType
    area_code: str | None
    geom_wkt: str
    max_alt_m: float | None
    is_active: bool
    detail: dict[str, Any]
    created_by: str
    created_at: datetime
    updated_at: datetime


class PreflightChecklistTemplateCreate(BaseModel):
    name: str
    description: str | None = None
    items: list[dict[str, Any]] = PydanticField(default_factory=list)
    require_approval_before_run: bool = True
    is_active: bool = True


class PreflightChecklistTemplateRead(ORMReadModel):
    id: str
    tenant_id: str
    name: str
    description: str | None
    items: list[dict[str, Any]]
    require_approval_before_run: bool
    is_active: bool
    created_by: str
    created_at: datetime
    updated_at: datetime


class MissionPreflightChecklistInitRequest(BaseModel):
    template_id: str | None = None
    required_items: list[dict[str, Any]] = PydanticField(default_factory=list)


class MissionPreflightChecklistItemCheckRequest(BaseModel):
    item_code: str
    checked: bool = True
    note: str | None = None


class MissionPreflightChecklistRead(ORMReadModel):
    id: str
    tenant_id: str
    mission_id: str
    template_id: str | None
    status: PreflightChecklistStatus
    required_items: list[dict[str, Any]]
    completed_items: list[dict[str, Any]]
    evidence: dict[str, Any]
    updated_by: str | None
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None


class TaskTypeCatalogCreate(BaseModel):
    code: str
    name: str
    description: str | None = None
    is_active: bool = True


class TaskTypeCatalogRead(ORMReadModel):
    id: str
    tenant_id: str
    code: str
    name: str
    description: str | None
    is_active: bool
    created_by: str
    created_at: datetime
    updated_at: datetime


class TaskTemplateCreate(BaseModel):
    task_type_id: str
    template_key: str
    name: str
    description: str | None = None
    requires_approval: bool = False
    default_priority: int = PydanticField(default=5, ge=1, le=10)
    default_risk_level: int = PydanticField(default=3, ge=1, le=5)
    default_checklist: list[dict[str, Any]] = PydanticField(default_factory=list)
    default_payload: dict[str, Any] = PydanticField(default_factory=dict)
    is_active: bool = True


class TaskTemplateRead(ORMReadModel):
    id: str
    tenant_id: str
    task_type_id: str
    template_key: str
    name: str
    description: str | None
    requires_approval: bool
    default_priority: int
    default_risk_level: int
    default_checklist: list[dict[str, Any]]
    default_payload: dict[str, Any]
    is_active: bool
    created_by: str
    created_at: datetime
    updated_at: datetime


class TaskCenterTaskCreate(BaseModel):
    task_type_id: str
    template_id: str | None = None
    mission_id: str | None = None
    name: str
    description: str | None = None
    requires_approval: bool | None = None
    priority: int | None = PydanticField(default=None, ge=1, le=10)
    risk_level: int | None = PydanticField(default=None, ge=1, le=5)
    org_unit_id: str | None = None
    project_code: str | None = None
    area_code: str | None = None
    area_geom: str = ""
    checklist: list[dict[str, Any]] = PydanticField(default_factory=list)
    attachments: list[dict[str, Any]] = PydanticField(default_factory=list)
    context_data: dict[str, Any] = PydanticField(default_factory=dict)


class TaskCenterTaskRead(ORMReadModel):
    id: str
    tenant_id: str
    task_type_id: str
    template_id: str | None
    mission_id: str | None
    name: str
    description: str | None
    state: TaskCenterState
    requires_approval: bool
    priority: int
    risk_level: int
    org_unit_id: str | None
    project_code: str | None
    area_code: str | None
    area_geom: str
    checklist: list[dict[str, Any]]
    attachments: list[dict[str, Any]]
    context_data: dict[str, Any]
    dispatch_mode: TaskCenterDispatchMode | None
    assigned_to: str | None
    dispatched_by: str | None
    dispatched_at: datetime | None
    started_at: datetime | None
    accepted_at: datetime | None
    archived_at: datetime | None
    canceled_at: datetime | None
    created_by: str
    created_at: datetime
    updated_at: datetime


class TaskCenterTaskSubmitApprovalRequest(BaseModel):
    note: str | None = None


class TaskCenterTaskApproveRequest(BaseModel):
    decision: ApprovalDecision
    note: str | None = None


class TaskCenterTaskDispatchRequest(BaseModel):
    assigned_to: str
    note: str | None = None


class TaskCenterTaskAutoDispatchRequest(BaseModel):
    candidate_user_ids: list[str] = PydanticField(default_factory=list)
    note: str | None = None


class TaskCenterCandidateScoreRead(BaseModel):
    user_id: str
    total_score: float
    breakdown: dict[str, float]
    reasons: list[str]


class TaskCenterTaskAutoDispatchRead(BaseModel):
    task: TaskCenterTaskRead
    selected_user_id: str
    dispatch_mode: TaskCenterDispatchMode
    scores: list[TaskCenterCandidateScoreRead]
    resource_snapshot: dict[str, Any]


class TaskCenterTaskTransitionRequest(BaseModel):
    target_state: TaskCenterState
    note: str | None = None


class TaskCenterRiskChecklistUpdateRequest(BaseModel):
    risk_level: int | None = PydanticField(default=None, ge=1, le=5)
    checklist: list[dict[str, Any]] | None = None
    note: str | None = None


class TaskCenterAttachmentAddRequest(BaseModel):
    name: str
    url: str
    media_type: str | None = None
    size_bytes: int | None = PydanticField(default=None, ge=0)
    note: str | None = None


class TaskCenterCommentCreateRequest(BaseModel):
    content: str


class TaskCenterCommentRead(BaseModel):
    id: str
    content: str
    created_by: str
    created_at: datetime


class TaskCenterTaskHistoryRead(ORMReadModel):
    id: str
    tenant_id: str
    task_id: str
    action: str
    from_state: TaskCenterState | None
    to_state: TaskCenterState | None
    note: str | None
    actor_id: str | None
    detail: dict[str, Any]
    created_at: datetime


class CommandDispatchRequest(BaseModel):
    drone_id: str
    type: CommandType
    params: dict[str, Any] = PydanticField(default_factory=dict)
    idempotency_key: str
    expect_ack: bool = True


class CommandRead(ORMReadModel):
    id: str
    tenant_id: str
    drone_id: str
    command_type: CommandType
    params: dict[str, Any]
    idempotency_key: str
    expect_ack: bool
    status: CommandStatus
    ack_ok: bool | None
    ack_message: str | None
    compliance_passed: bool | None
    compliance_reason_code: ComplianceReasonCode | None
    compliance_detail: dict[str, Any]
    attempts: int
    issued_by: str | None
    issued_at: datetime
    updated_at: datetime


class AlertRead(ORMReadModel):
    id: str
    tenant_id: str
    drone_id: str
    alert_type: AlertType
    severity: AlertSeverity
    priority_level: AlertPriority
    status: AlertStatus
    route_status: AlertRouteStatus
    message: str
    detail: dict[str, Any]
    first_seen_at: datetime
    last_seen_at: datetime
    acked_by: str | None
    acked_at: datetime | None
    closed_by: str | None
    closed_at: datetime | None
    routed_at: datetime | None


class AlertActionRequest(BaseModel):
    comment: str | None = None


class AlertHandlingActionCreate(BaseModel):
    action_type: AlertHandlingActionType
    note: str | None = None
    detail: dict[str, Any] = PydanticField(default_factory=dict)


class AlertHandlingActionRead(ORMReadModel):
    id: str
    tenant_id: str
    alert_id: str
    action_type: AlertHandlingActionType
    note: str | None
    actor_id: str | None
    detail: dict[str, Any]
    created_at: datetime


class AlertReviewRead(BaseModel):
    alert: AlertRead
    routes: list[AlertRouteLogRead]
    actions: list[AlertHandlingActionRead]


class AlertRoutingRuleCreate(BaseModel):
    priority_level: AlertPriority
    alert_type: AlertType | None = None
    channel: AlertRouteChannel = AlertRouteChannel.IN_APP
    target: str
    is_active: bool = True
    detail: dict[str, Any] = PydanticField(default_factory=dict)


class AlertRoutingRuleRead(ORMReadModel):
    id: str
    tenant_id: str
    priority_level: AlertPriority
    alert_type: AlertType | None
    channel: AlertRouteChannel
    target: str
    is_active: bool
    detail: dict[str, Any]
    created_by: str
    created_at: datetime
    updated_at: datetime


class AlertRouteLogRead(ORMReadModel):
    id: str
    tenant_id: str
    alert_id: str
    rule_id: str | None
    priority_level: AlertPriority
    channel: AlertRouteChannel
    target: str
    delivery_status: AlertRouteDeliveryStatus
    detail: dict[str, Any]
    created_at: datetime


class RawDataCatalogCreate(BaseModel):
    task_id: str | None = None
    mission_id: str | None = None
    data_type: RawDataType
    source_uri: str
    checksum: str | None = None
    meta: dict[str, Any] = PydanticField(default_factory=dict)
    captured_at: datetime = PydanticField(default_factory=now_utc)


class RawDataCatalogRead(ORMReadModel):
    id: str
    tenant_id: str
    task_id: str | None
    mission_id: str | None
    data_type: RawDataType
    source_uri: str
    checksum: str | None
    meta: dict[str, Any]
    captured_at: datetime
    created_by: str
    created_at: datetime


class OutcomeCatalogCreate(BaseModel):
    task_id: str | None = None
    mission_id: str | None = None
    source_type: OutcomeSourceType = OutcomeSourceType.MANUAL
    source_id: str
    outcome_type: OutcomeType
    status: OutcomeStatus = OutcomeStatus.NEW
    point_lat: float | None = None
    point_lon: float | None = None
    alt_m: float | None = None
    confidence: float | None = PydanticField(default=None, ge=0, le=1)
    payload: dict[str, Any] = PydanticField(default_factory=dict)


class OutcomeCatalogStatusUpdateRequest(BaseModel):
    status: OutcomeStatus
    note: str | None = None


class OutcomeCatalogRead(ORMReadModel):
    id: str
    tenant_id: str
    task_id: str | None
    mission_id: str | None
    source_type: OutcomeSourceType
    source_id: str
    outcome_type: OutcomeType
    status: OutcomeStatus
    point_lat: float | None
    point_lon: float | None
    alt_m: float | None
    confidence: float | None
    payload: dict[str, Any]
    reviewed_by: str | None
    reviewed_at: datetime | None
    created_by: str
    created_at: datetime
    updated_at: datetime


class AiAnalysisJobCreate(BaseModel):
    task_id: str | None = None
    mission_id: str | None = None
    topic: str | None = None
    job_type: AiJobType = AiJobType.SUMMARY
    trigger_mode: AiTriggerMode = AiTriggerMode.MANUAL
    model_provider: str = "builtin"
    model_name: str = "uav-assistant-lite"
    model_version: str = "phase14.v1"
    threshold_config: dict[str, Any] = PydanticField(default_factory=dict)
    input_config: dict[str, Any] = PydanticField(default_factory=dict)


class AiAnalysisJobRead(ORMReadModel):
    id: str
    tenant_id: str
    task_id: str | None
    mission_id: str | None
    topic: str | None
    job_type: AiJobType
    trigger_mode: AiTriggerMode
    status: AiJobStatus
    model_provider: str
    model_name: str
    model_version: str
    threshold_config: dict[str, Any]
    input_config: dict[str, Any]
    created_by: str
    created_at: datetime
    updated_at: datetime


class AiAnalysisRunTriggerRequest(BaseModel):
    force_fail: bool = False
    trigger_mode: AiTriggerMode | None = None
    context: dict[str, Any] = PydanticField(default_factory=dict)


class AiAnalysisRunRetryRequest(BaseModel):
    force_fail: bool = False
    context: dict[str, Any] = PydanticField(default_factory=dict)


class AiAnalysisRunRead(ORMReadModel):
    id: str
    tenant_id: str
    job_id: str
    retry_of_run_id: str | None
    retry_count: int
    status: AiRunStatus
    trigger_mode: AiTriggerMode
    input_hash: str | None
    output_hash: str | None
    metrics: dict[str, Any]
    error_message: str | None
    started_at: datetime
    finished_at: datetime | None
    triggered_by: str
    created_at: datetime
    updated_at: datetime


class AiAnalysisOutputRead(ORMReadModel):
    id: str
    tenant_id: str
    job_id: str
    run_id: str
    summary_text: str
    suggestion_text: str
    payload: dict[str, Any]
    control_allowed: bool
    review_status: AiOutputReviewStatus
    reviewed_by: str | None
    reviewed_at: datetime | None
    review_note: str | None
    override_payload: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class AiEvidenceRecordRead(ORMReadModel):
    id: str
    tenant_id: str
    run_id: str
    output_id: str | None
    evidence_type: AiEvidenceType
    content_hash: str
    payload: dict[str, Any]
    created_at: datetime


class AiOutputReviewActionCreate(BaseModel):
    action_type: AiReviewActionType
    note: str | None = None
    override_payload: dict[str, Any] = PydanticField(default_factory=dict)
    detail: dict[str, Any] = PydanticField(default_factory=dict)


class AiOutputReviewActionRead(ORMReadModel):
    id: str
    tenant_id: str
    output_id: str
    run_id: str
    action_type: AiReviewActionType
    note: str | None
    actor_id: str
    detail: dict[str, Any]
    created_at: datetime


class AiOutputReviewRead(BaseModel):
    output: AiAnalysisOutputRead
    actions: list[AiOutputReviewActionRead]
    evidences: list[AiEvidenceRecordRead]


class KpiSnapshotRecomputeRequest(BaseModel):
    from_ts: datetime
    to_ts: datetime
    window_type: KpiWindowType = KpiWindowType.CUSTOM


class KpiSnapshotRead(ORMReadModel):
    id: str
    tenant_id: str
    window_type: KpiWindowType
    from_ts: datetime
    to_ts: datetime
    metrics: dict[str, Any]
    generated_by: str
    generated_at: datetime


class KpiHeatmapBinRead(ORMReadModel):
    id: str
    tenant_id: str
    snapshot_id: str
    source: KpiHeatmapSource
    grid_lat: float
    grid_lon: float
    count: int
    detail: dict[str, Any]
    created_at: datetime


class KpiGovernanceExportRequest(BaseModel):
    title: str = "UAV Governance Monthly Report"
    window_type: KpiWindowType = KpiWindowType.MONTHLY
    from_ts: datetime | None = None
    to_ts: datetime | None = None


class KpiGovernanceExportRead(BaseModel):
    file_path: str


class OpenPlatformCredentialCreate(BaseModel):
    key_id: str | None = None
    api_key: str | None = None
    signing_secret: str | None = None
    is_active: bool = True


class OpenPlatformCredentialRead(ORMReadModel):
    id: str
    tenant_id: str
    key_id: str
    api_key: str
    signing_secret: str
    is_active: bool
    created_by: str | None
    created_at: datetime
    updated_at: datetime


class OpenWebhookEndpointCreate(BaseModel):
    name: str
    endpoint_url: str
    event_type: str
    credential_id: str | None = None
    auth_type: OpenWebhookAuthType = OpenWebhookAuthType.HMAC_SHA256
    is_active: bool = True
    extra_headers: dict[str, Any] = PydanticField(default_factory=dict)


class OpenWebhookEndpointRead(ORMReadModel):
    id: str
    tenant_id: str
    name: str
    endpoint_url: str
    event_type: str
    credential_id: str | None
    auth_type: OpenWebhookAuthType
    is_active: bool
    extra_headers: dict[str, Any]
    created_by: str
    created_at: datetime
    updated_at: datetime


class OpenWebhookDispatchRequest(BaseModel):
    payload: dict[str, Any] = PydanticField(default_factory=dict)


class OpenWebhookDeliveryRead(ORMReadModel):
    id: str
    tenant_id: str
    endpoint_id: str
    event_type: str
    payload: dict[str, Any]
    signature: str | None
    request_headers: dict[str, Any]
    status: OpenWebhookDeliveryStatus
    detail: dict[str, Any]
    created_at: datetime


class OpenAdapterIngressRequest(BaseModel):
    event_type: str
    payload: dict[str, Any] = PydanticField(default_factory=dict)


class OpenAdapterIngressRead(ORMReadModel):
    id: str
    tenant_id: str
    key_id: str
    event_type: str
    payload: dict[str, Any]
    signature_valid: bool
    status: OpenAdapterIngressStatus
    detail: dict[str, Any]
    created_at: datetime


class InspectionTaskStatus(StrEnum):
    DRAFT = "DRAFT"
    SCHEDULED = "SCHEDULED"
    RUNNING = "RUNNING"
    DONE = "DONE"


class DefectStatus(StrEnum):
    OPEN = "OPEN"
    ASSIGNED = "ASSIGNED"
    IN_PROGRESS = "IN_PROGRESS"
    FIXED = "FIXED"
    VERIFIED = "VERIFIED"
    CLOSED = "CLOSED"


class IncidentStatus(StrEnum):
    OPEN = "OPEN"
    TASK_CREATED = "TASK_CREATED"
    CLOSED = "CLOSED"


class InspectionTemplate(SQLModel, table=True):
    __tablename__ = "inspection_templates"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_inspection_templates_tenant_id_id"),
        Index("ix_inspection_templates_tenant_id_id", "tenant_id", "id"),
    )

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    tenant_id: str = Field(foreign_key="tenants.id", index=True)
    name: str = Field(max_length=100, index=True)
    category: str = Field(max_length=50, index=True)
    description: str | None = None
    is_active: bool = Field(default=True, index=True)
    created_at: datetime = Field(default_factory=now_utc, index=True)


class InspectionTemplateItem(SQLModel, table=True):
    __tablename__ = "inspection_template_items"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_inspection_template_items_tenant_id_id"),
        ForeignKeyConstraint(
            ["tenant_id", "template_id"],
            ["inspection_templates.tenant_id", "inspection_templates.id"],
            ondelete="RESTRICT",
        ),
        Index("ix_inspection_template_items_tenant_id_id", "tenant_id", "id"),
        Index(
            "ix_inspection_template_items_tenant_template_id",
            "tenant_id",
            "template_id",
        ),
    )

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    tenant_id: str = Field(foreign_key="tenants.id", index=True)
    template_id: str = Field(index=True)
    code: str = Field(max_length=50, index=True)
    title: str = Field(max_length=100)
    severity_default: int = 1
    required: bool = Field(default=True)
    sort_order: int = Field(default=0)
    created_at: datetime = Field(default_factory=now_utc, index=True)


class InspectionTask(SQLModel, table=True):
    __tablename__ = "inspection_tasks"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_inspection_tasks_tenant_id_id"),
        ForeignKeyConstraint(
            ["tenant_id", "template_id"],
            ["inspection_templates.tenant_id", "inspection_templates.id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "org_unit_id"],
            ["org_units.tenant_id", "org_units.id"],
            ondelete="RESTRICT",
        ),
        Index("ix_inspection_tasks_tenant_id_id", "tenant_id", "id"),
        Index("ix_inspection_tasks_tenant_template_id", "tenant_id", "template_id"),
        Index("ix_inspection_tasks_tenant_org_unit", "tenant_id", "org_unit_id"),
    )

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    tenant_id: str = Field(foreign_key="tenants.id", index=True)
    name: str = Field(max_length=100, index=True)
    template_id: str = Field(index=True)
    mission_id: str | None = Field(default=None, foreign_key="missions.id", index=True)
    org_unit_id: str | None = Field(default=None, index=True)
    project_code: str | None = Field(default=None, max_length=100, index=True)
    area_code: str | None = Field(default=None, max_length=100, index=True)
    area_geom: str = Field(default="")
    priority: int = Field(default=5, index=True)
    status: InspectionTaskStatus = Field(default=InspectionTaskStatus.DRAFT, index=True)
    created_at: datetime = Field(default_factory=now_utc, index=True)


class InspectionObservation(SQLModel, table=True):
    __tablename__ = "inspection_observations"

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    tenant_id: str = Field(foreign_key="tenants.id", index=True)
    task_id: str = Field(foreign_key="inspection_tasks.id", index=True)
    drone_id: str | None = Field(default=None, foreign_key="drones.id", index=True)
    ts: datetime = Field(default_factory=now_utc, index=True)
    position_lat: float
    position_lon: float
    alt_m: float
    item_code: str = Field(max_length=50, index=True)
    severity: int = 1
    note: str = ""
    media_url: str | None = None
    confidence: float | None = None
    created_at: datetime = Field(default_factory=now_utc, index=True)


class InspectionExport(SQLModel, table=True):
    __tablename__ = "inspection_exports"

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    tenant_id: str = Field(foreign_key="tenants.id", index=True)
    task_id: str = Field(foreign_key="inspection_tasks.id", index=True)
    format: str = Field(max_length=10, index=True)
    file_path: str
    created_at: datetime = Field(default_factory=now_utc, index=True)


class Defect(SQLModel, table=True):
    __tablename__ = "defects"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_defects_tenant_id_id"),
        ForeignKeyConstraint(
            ["tenant_id", "task_id"],
            ["inspection_tasks.tenant_id", "inspection_tasks.id"],
            ondelete="SET NULL",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "org_unit_id"],
            ["org_units.tenant_id", "org_units.id"],
            ondelete="RESTRICT",
        ),
        Index("ix_defects_tenant_id_id", "tenant_id", "id"),
        Index("ix_defects_tenant_observation_id", "tenant_id", "observation_id"),
        Index("ix_defects_tenant_task_id", "tenant_id", "task_id"),
        Index("ix_defects_tenant_org_unit", "tenant_id", "org_unit_id"),
    )

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    tenant_id: str = Field(foreign_key="tenants.id", index=True)
    observation_id: str = Field(foreign_key="inspection_observations.id", index=True)
    task_id: str | None = Field(default=None, index=True)
    org_unit_id: str | None = Field(default=None, index=True)
    project_code: str | None = Field(default=None, max_length=100, index=True)
    area_code: str | None = Field(default=None, max_length=100, index=True)
    title: str = Field(max_length=200)
    description: str | None = None
    severity: int = 1
    status: DefectStatus = Field(default=DefectStatus.OPEN, index=True)
    assigned_to: str | None = Field(default=None, index=True)
    created_at: datetime = Field(default_factory=now_utc, index=True)


class DefectAction(SQLModel, table=True):
    __tablename__ = "defect_actions"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_defect_actions_tenant_id_id"),
        ForeignKeyConstraint(
            ["tenant_id", "defect_id"],
            ["defects.tenant_id", "defects.id"],
            ondelete="RESTRICT",
        ),
        Index("ix_defect_actions_tenant_id_id", "tenant_id", "id"),
        Index("ix_defect_actions_tenant_defect_id", "tenant_id", "defect_id"),
    )

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    tenant_id: str = Field(foreign_key="tenants.id", index=True)
    defect_id: str = Field(index=True)
    action_type: str = Field(max_length=50, index=True)
    note: str = ""
    created_at: datetime = Field(default_factory=now_utc, index=True)


class Incident(SQLModel, table=True):
    __tablename__ = "incidents"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_incidents_tenant_id_id"),
        ForeignKeyConstraint(
            ["tenant_id", "org_unit_id"],
            ["org_units.tenant_id", "org_units.id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "linked_task_id"],
            ["inspection_tasks.tenant_id", "inspection_tasks.id"],
            ondelete="RESTRICT",
        ),
        Index("ix_incidents_tenant_id_id", "tenant_id", "id"),
        Index("ix_incidents_tenant_linked_task_id", "tenant_id", "linked_task_id"),
        Index("ix_incidents_tenant_org_unit", "tenant_id", "org_unit_id"),
    )

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    tenant_id: str = Field(foreign_key="tenants.id", index=True)
    title: str = Field(max_length=200)
    level: str = Field(max_length=20, index=True)
    org_unit_id: str | None = Field(default=None, index=True)
    project_code: str | None = Field(default=None, max_length=100, index=True)
    area_code: str | None = Field(default=None, max_length=100, index=True)
    location_geom: str
    status: IncidentStatus = Field(default=IncidentStatus.OPEN, index=True)
    linked_task_id: str | None = Field(default=None, index=True)
    created_at: datetime = Field(default_factory=now_utc, index=True)


class ApprovalRecord(SQLModel, table=True):
    __tablename__ = "approval_records"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_approval_records_tenant_id_id"),
        ForeignKeyConstraint(
            ["tenant_id", "approved_by"],
            ["users.tenant_id", "users.id"],
            ondelete="RESTRICT",
        ),
        Index("ix_approval_records_tenant_id_id", "tenant_id", "id"),
        Index("ix_approval_records_tenant_approved_by", "tenant_id", "approved_by"),
    )

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    tenant_id: str = Field(foreign_key="tenants.id", index=True)
    entity_type: str = Field(max_length=50, index=True)
    entity_id: str = Field(index=True)
    status: str = Field(max_length=20, index=True)
    approved_by: str = Field(index=True)
    created_at: datetime = Field(default_factory=now_utc, index=True)


class InspectionTemplateCreate(BaseModel):
    name: str
    category: str
    description: str | None = None
    is_active: bool = True


class InspectionTemplateRead(ORMReadModel):
    id: str
    tenant_id: str
    name: str
    category: str
    description: str | None
    is_active: bool
    created_at: datetime


class InspectionTemplateItemCreate(BaseModel):
    code: str
    title: str
    severity_default: int = 1
    required: bool = True
    sort_order: int = 0


class InspectionTemplateItemRead(ORMReadModel):
    id: str
    tenant_id: str
    template_id: str
    code: str
    title: str
    severity_default: int
    required: bool
    sort_order: int
    created_at: datetime


class InspectionTaskCreate(BaseModel):
    name: str
    template_id: str
    mission_id: str | None = None
    org_unit_id: str | None = None
    project_code: str | None = None
    area_code: str | None = None
    area_geom: str = ""
    priority: int = 5
    status: InspectionTaskStatus = InspectionTaskStatus.SCHEDULED


class InspectionTaskRead(ORMReadModel):
    id: str
    tenant_id: str
    name: str
    template_id: str
    mission_id: str | None
    org_unit_id: str | None
    project_code: str | None
    area_code: str | None
    area_geom: str
    priority: int
    status: InspectionTaskStatus
    created_at: datetime


class InspectionObservationCreate(BaseModel):
    drone_id: str | None = None
    ts: datetime = PydanticField(default_factory=now_utc)
    position_lat: float
    position_lon: float
    alt_m: float
    item_code: str
    severity: int = 1
    note: str = ""
    media_url: str | None = None
    confidence: float | None = None


class InspectionObservationRead(ORMReadModel):
    id: str
    tenant_id: str
    task_id: str
    drone_id: str | None
    ts: datetime
    position_lat: float
    position_lon: float
    alt_m: float
    item_code: str
    severity: int
    note: str
    media_url: str | None
    confidence: float | None
    created_at: datetime


class InspectionExportRead(ORMReadModel):
    id: str
    tenant_id: str
    task_id: str
    format: str
    file_path: str
    created_at: datetime


class DefectCreateFromObservationRead(ORMReadModel):
    id: str
    tenant_id: str
    observation_id: str
    task_id: str | None
    org_unit_id: str | None
    project_code: str | None
    area_code: str | None
    title: str
    description: str | None
    severity: int
    status: DefectStatus
    assigned_to: str | None
    created_at: datetime


class DefectAssignRequest(BaseModel):
    assigned_to: str
    note: str | None = None


class DefectStatusRequest(BaseModel):
    status: DefectStatus
    note: str | None = None


class DefectActionRead(ORMReadModel):
    id: str
    tenant_id: str
    defect_id: str
    action_type: str
    note: str
    created_at: datetime


class DefectDetailRead(BaseModel):
    defect: DefectCreateFromObservationRead
    actions: list[DefectActionRead]


class DefectStatsRead(BaseModel):
    total: int
    closed: int
    by_status: dict[str, int]
    closure_rate: float


class IncidentCreate(BaseModel):
    title: str
    level: str
    org_unit_id: str | None = None
    project_code: str | None = None
    area_code: str | None = None
    location_geom: str


class IncidentRead(ORMReadModel):
    id: str
    tenant_id: str
    title: str
    level: str
    org_unit_id: str | None
    project_code: str | None
    area_code: str | None
    location_geom: str
    status: IncidentStatus
    linked_task_id: str | None
    created_at: datetime


class IncidentCreateTaskRequest(BaseModel):
    template_id: str | None = None
    task_name: str | None = None


class IncidentCreateTaskRead(BaseModel):
    incident_id: str
    mission_id: str
    task_id: str


class DashboardStatsRead(BaseModel):
    online_devices: int
    today_inspections: int
    defects_total: int
    realtime_alerts: int


class MapLayerName(StrEnum):
    RESOURCES = "resources"
    TASKS = "tasks"
    ALERTS = "alerts"
    EVENTS = "events"


class MapPointRead(BaseModel):
    lat: float
    lon: float
    alt_m: float | None = None
    ts: datetime | None = None


class MapLayerItemRead(BaseModel):
    id: str
    category: str
    label: str
    status: str | None = None
    point: MapPointRead | None = None
    detail: dict[str, Any] = PydanticField(default_factory=dict)


class MapLayerRead(BaseModel):
    layer: MapLayerName
    total: int
    items: list[MapLayerItemRead]


class MapOverviewRead(BaseModel):
    generated_at: datetime
    resources_total: int
    tasks_total: int
    alerts_total: int
    events_total: int
    layers: list[MapLayerRead]


class MapTrackPointRead(BaseModel):
    drone_id: str
    ts: datetime
    lat: float
    lon: float
    alt_m: float | None = None
    mode: str | None = None


class MapTrackReplayRead(BaseModel):
    drone_id: str
    from_ts: datetime | None = None
    to_ts: datetime | None = None
    points: list[MapTrackPointRead]


class ApprovalRecordCreate(BaseModel):
    entity_type: str
    entity_id: str
    status: str


class ApprovalRecordRead(ORMReadModel):
    id: str
    tenant_id: str
    entity_type: str
    entity_id: str
    status: str
    approved_by: str
    created_at: datetime


class ReportingOverviewRead(BaseModel):
    missions_total: int
    inspections_total: int
    defects_total: int
    defects_closed: int
    closure_rate: float


class ReportingClosureRateRead(BaseModel):
    total: int
    closed: int
    closure_rate: float


class DeviceUtilizationRead(BaseModel):
    drone_id: str
    drone_name: str
    missions: int
    inspections: int


class ReportingExportRequest(BaseModel):
    title: str = "Quarterly UAV Governance Report"
    task_id: str | None = None
    from_ts: datetime | None = None
    to_ts: datetime | None = None
    topic: str | None = None
