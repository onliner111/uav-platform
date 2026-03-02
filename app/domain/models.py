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


class OrgUnitType(StrEnum):
    ORGANIZATION = "ORGANIZATION"
    DEPARTMENT = "DEPARTMENT"


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
    unit_type: OrgUnitType = Field(default=OrgUnitType.DEPARTMENT, max_length=30, index=True)
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
    job_title: str | None = Field(default=None, max_length=120)
    job_code: str | None = Field(default=None, max_length=80, index=True)
    is_manager: bool = Field(default=False, index=True)
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
    resource_ids: list[str] = Field(
        default_factory=list,
        sa_column=Column(JSON, nullable=False),
    )
    denied_org_unit_ids: list[str] = Field(
        default_factory=list,
        sa_column=Column(JSON, nullable=False),
    )
    denied_project_codes: list[str] = Field(
        default_factory=list,
        sa_column=Column(JSON, nullable=False),
    )
    denied_area_codes: list[str] = Field(
        default_factory=list,
        sa_column=Column(JSON, nullable=False),
    )
    denied_task_ids: list[str] = Field(
        default_factory=list,
        sa_column=Column(JSON, nullable=False),
    )
    denied_resource_ids: list[str] = Field(
        default_factory=list,
        sa_column=Column(JSON, nullable=False),
    )
    created_at: datetime = Field(default_factory=now_utc, index=True)
    updated_at: datetime = Field(default_factory=now_utc, index=True)


class RoleDataAccessPolicy(SQLModel, table=True):
    __tablename__ = "role_data_access_policies"
    __table_args__ = (
        UniqueConstraint("tenant_id", "role_id", name="uq_role_data_access_policies_tenant_role"),
        ForeignKeyConstraint(
            ["tenant_id", "role_id"],
            ["roles.tenant_id", "roles.id"],
            ondelete="CASCADE",
        ),
        Index("ix_role_data_access_policies_tenant_role", "tenant_id", "role_id"),
    )

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    tenant_id: str = Field(foreign_key="tenants.id", index=True)
    role_id: str = Field(index=True)
    scope_mode: DataScopeMode = Field(default=DataScopeMode.SCOPED, index=True)
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
    resource_ids: list[str] = Field(
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


class AirspacePolicyLayer(StrEnum):
    PLATFORM_DEFAULT = "PLATFORM_DEFAULT"
    TENANT = "TENANT"
    ORG_UNIT = "ORG_UNIT"


class AirspacePolicyEffect(StrEnum):
    ALLOW = "ALLOW"
    DENY = "DENY"


class ComplianceReasonCode(StrEnum):
    AIRSPACE_NO_FLY = "AIRSPACE_NO_FLY"
    AIRSPACE_ALT_LIMIT_EXCEEDED = "AIRSPACE_ALT_LIMIT_EXCEEDED"
    AIRSPACE_SENSITIVE_RESTRICTED = "AIRSPACE_SENSITIVE_RESTRICTED"
    PREFLIGHT_CHECKLIST_REQUIRED = "PREFLIGHT_CHECKLIST_REQUIRED"
    PREFLIGHT_CHECKLIST_INCOMPLETE = "PREFLIGHT_CHECKLIST_INCOMPLETE"
    COMMAND_GEOFENCE_BLOCKED = "COMMAND_GEOFENCE_BLOCKED"
    COMMAND_ALTITUDE_BLOCKED = "COMMAND_ALTITUDE_BLOCKED"
    COMMAND_SENSITIVE_RESTRICTED = "COMMAND_SENSITIVE_RESTRICTED"
    APPROVAL_FLOW_PENDING = "APPROVAL_FLOW_PENDING"


class PreflightChecklistStatus(StrEnum):
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    WAIVED = "WAIVED"


class ApprovalFlowInstanceStatus(StrEnum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class ApprovalFlowAction(StrEnum):
    APPROVE = "APPROVE"
    REJECT = "REJECT"
    ROLLBACK = "ROLLBACK"


class ComplianceDecision(StrEnum):
    ALLOW = "ALLOW"
    DENY = "DENY"
    APPROVE = "APPROVE"
    REJECT = "REJECT"


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
    policy_layer: AirspacePolicyLayer = Field(default=AirspacePolicyLayer.TENANT, index=True)
    policy_effect: AirspacePolicyEffect = Field(default=AirspacePolicyEffect.DENY, index=True)
    org_unit_id: str | None = Field(default=None, index=True)
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
    template_version: str = Field(default="v1", max_length=50)
    evidence_requirements: dict[str, Any] = Field(
        default_factory=dict,
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


class ComplianceApprovalFlowTemplate(SQLModel, table=True):
    __tablename__ = "compliance_approval_flow_templates"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_compliance_approval_flow_templates_tenant_id_id"),
        Index("ix_compliance_approval_flow_templates_tenant_id_id", "tenant_id", "id"),
        Index("ix_compliance_approval_flow_templates_tenant_entity", "tenant_id", "entity_type"),
    )

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    tenant_id: str = Field(foreign_key="tenants.id", index=True)
    name: str = Field(max_length=100, index=True)
    entity_type: str = Field(max_length=50, index=True)
    steps: list[dict[str, Any]] = Field(
        default_factory=list,
        sa_column=Column(JSON, nullable=False),
    )
    is_active: bool = Field(default=True, index=True)
    created_by: str = Field(index=True)
    created_at: datetime = Field(default_factory=now_utc, index=True)
    updated_at: datetime = Field(default_factory=now_utc, index=True)


class ComplianceApprovalFlowInstance(SQLModel, table=True):
    __tablename__ = "compliance_approval_flow_instances"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_compliance_approval_flow_instances_tenant_id_id"),
        ForeignKeyConstraint(
            ["tenant_id", "template_id"],
            ["compliance_approval_flow_templates.tenant_id", "compliance_approval_flow_templates.id"],
            ondelete="RESTRICT",
        ),
        Index("ix_compliance_approval_flow_instances_tenant_id_id", "tenant_id", "id"),
        Index("ix_compliance_approval_flow_instances_tenant_entity", "tenant_id", "entity_type", "entity_id"),
    )

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    tenant_id: str = Field(foreign_key="tenants.id", index=True)
    template_id: str = Field(index=True)
    entity_type: str = Field(max_length=50, index=True)
    entity_id: str = Field(index=True)
    status: ApprovalFlowInstanceStatus = Field(default=ApprovalFlowInstanceStatus.PENDING, index=True)
    current_step_index: int = Field(default=0, ge=0)
    steps_snapshot: list[dict[str, Any]] = Field(
        default_factory=list,
        sa_column=Column(JSON, nullable=False),
    )
    action_history: list[dict[str, Any]] = Field(
        default_factory=list,
        sa_column=Column(JSON, nullable=False),
    )
    created_by: str = Field(index=True)
    created_at: datetime = Field(default_factory=now_utc, index=True)
    updated_at: datetime = Field(default_factory=now_utc, index=True)
    completed_at: datetime | None = Field(default=None, index=True)


class ComplianceDecisionRecord(SQLModel, table=True):
    __tablename__ = "compliance_decision_records"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_compliance_decision_records_tenant_id_id"),
        Index("ix_compliance_decision_records_tenant_id_id", "tenant_id", "id"),
        Index("ix_compliance_decision_records_tenant_entity", "tenant_id", "entity_type", "entity_id"),
        Index("ix_compliance_decision_records_tenant_source", "tenant_id", "source"),
    )

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    tenant_id: str = Field(foreign_key="tenants.id", index=True)
    source: str = Field(max_length=50, index=True)
    entity_type: str = Field(max_length=50, index=True)
    entity_id: str = Field(index=True)
    decision: ComplianceDecision = Field(index=True)
    reason_code: str | None = Field(default=None, max_length=100, index=True)
    actor_id: str | None = Field(default=None, index=True)
    detail: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False),
    )
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


class CommandStatus(StrEnum):
    PENDING = "PENDING"
    ACKED = "ACKED"
    FAILED = "FAILED"
    TIMEOUT = "TIMEOUT"


class DeviceIntegrationSessionStatus(StrEnum):
    RUNNING = "RUNNING"
    STOPPED = "STOPPED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class VideoStreamProtocol(StrEnum):
    RTSP = "RTSP"
    WEBRTC = "WEBRTC"


class VideoStreamStatus(StrEnum):
    LIVE = "LIVE"
    STANDBY = "STANDBY"
    DISABLED = "DISABLED"
    ERROR = "ERROR"


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
    ESCALATE = "ESCALATE"
    VERIFY = "VERIFY"
    REVIEW = "REVIEW"
    CLOSE = "CLOSE"


class AlertEscalationReason(StrEnum):
    ACK_TIMEOUT = "ACK_TIMEOUT"
    REPEAT_TRIGGER = "REPEAT_TRIGGER"
    SHIFT_HANDOVER = "SHIFT_HANDOVER"


class RawDataType(StrEnum):
    TELEMETRY = "TELEMETRY"
    IMAGE = "IMAGE"
    VIDEO = "VIDEO"
    DOCUMENT = "DOCUMENT"
    LOG = "LOG"


class RawUploadSessionStatus(StrEnum):
    INITIATED = "INITIATED"
    UPLOADED = "UPLOADED"
    COMPLETED = "COMPLETED"
    EXPIRED = "EXPIRED"


class RawDataAccessTier(StrEnum):
    HOT = "HOT"
    WARM = "WARM"
    COLD = "COLD"


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


class OutcomeVersionChangeType(StrEnum):
    INIT_SNAPSHOT = "INIT_SNAPSHOT"
    AUTO_MATERIALIZE = "AUTO_MATERIALIZE"
    STATUS_UPDATE = "STATUS_UPDATE"


class ReportFileFormat(StrEnum):
    PDF = "PDF"
    WORD = "WORD"


class ReportExportStatus(StrEnum):
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"


class AiModelVersionStatus(StrEnum):
    DRAFT = "DRAFT"
    CANARY = "CANARY"
    STABLE = "STABLE"
    DEPRECATED = "DEPRECATED"


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


class BillingCycle(StrEnum):
    MONTHLY = "MONTHLY"
    QUARTERLY = "QUARTERLY"
    YEARLY = "YEARLY"


class BillingSubscriptionStatus(StrEnum):
    TRIAL = "TRIAL"
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"
    EXPIRED = "EXPIRED"


class BillingQuotaEnforcementMode(StrEnum):
    HARD_LIMIT = "HARD_LIMIT"
    SOFT_LIMIT = "SOFT_LIMIT"


class BillingInvoiceStatus(StrEnum):
    DRAFT = "DRAFT"
    ISSUED = "ISSUED"
    CLOSED = "CLOSED"
    VOID = "VOID"


class ObservabilitySignalType(StrEnum):
    LOG = "LOG"
    METRIC = "METRIC"
    TRACE = "TRACE"


class ObservabilitySignalLevel(StrEnum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARN = "WARN"
    ERROR = "ERROR"


class ObservabilitySloStatus(StrEnum):
    HEALTHY = "HEALTHY"
    BREACHED = "BREACHED"


class ObservabilityAlertSeverity(StrEnum):
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"


class ObservabilityAlertStatus(StrEnum):
    OPEN = "OPEN"
    ACKED = "ACKED"
    CLOSED = "CLOSED"


class ReliabilityBackupRunType(StrEnum):
    FULL = "FULL"
    INCREMENTAL = "INCREMENTAL"


class ReliabilityBackupRunStatus(StrEnum):
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"


class ReliabilityRestoreDrillStatus(StrEnum):
    PASSED = "PASSED"
    FAILED = "FAILED"


class SecurityInspectionCheckStatus(StrEnum):
    PASS = "PASS"
    WARN = "WARN"
    FAIL = "FAIL"


class CapacityDecision(StrEnum):
    SCALE_OUT = "SCALE_OUT"
    SCALE_IN = "SCALE_IN"
    HOLD = "HOLD"


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


class AlertOncallShift(SQLModel, table=True):
    __tablename__ = "alert_oncall_shifts"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_alert_oncall_shifts_tenant_id_id"),
        Index("ix_alert_oncall_shifts_tenant_id_id", "tenant_id", "id"),
        Index("ix_alert_oncall_shifts_tenant_window", "tenant_id", "starts_at", "ends_at"),
        Index("ix_alert_oncall_shifts_tenant_active", "tenant_id", "is_active"),
    )

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    tenant_id: str = Field(foreign_key="tenants.id", index=True)
    shift_name: str = Field(default="default", max_length=100)
    target: str = Field(max_length=200, index=True)
    starts_at: datetime = Field(index=True)
    ends_at: datetime = Field(index=True)
    timezone: str = Field(default="UTC", max_length=64)
    is_active: bool = Field(default=True, index=True)
    detail: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False),
    )
    created_by: str = Field(index=True)
    created_at: datetime = Field(default_factory=now_utc, index=True)
    updated_at: datetime = Field(default_factory=now_utc, index=True)


class AlertEscalationPolicy(SQLModel, table=True):
    __tablename__ = "alert_escalation_policies"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_alert_escalation_policies_tenant_id_id"),
        UniqueConstraint("tenant_id", "priority_level", name="uq_alert_escalation_policies_tenant_priority"),
        Index("ix_alert_escalation_policies_tenant_id_id", "tenant_id", "id"),
        Index("ix_alert_escalation_policies_tenant_priority", "tenant_id", "priority_level"),
        Index("ix_alert_escalation_policies_tenant_active", "tenant_id", "is_active"),
    )

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    tenant_id: str = Field(foreign_key="tenants.id", index=True)
    priority_level: AlertPriority = Field(index=True)
    ack_timeout_seconds: int = Field(default=1800, ge=30)
    repeat_threshold: int = Field(default=3, ge=2)
    max_escalation_level: int = Field(default=1, ge=1)
    escalation_channel: AlertRouteChannel = Field(default=AlertRouteChannel.IN_APP, index=True)
    escalation_target: str = Field(default="oncall://active", max_length=200)
    is_active: bool = Field(default=True, index=True)
    detail: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False),
    )
    created_by: str = Field(index=True)
    created_at: datetime = Field(default_factory=now_utc, index=True)
    updated_at: datetime = Field(default_factory=now_utc, index=True)


class AlertEscalationExecution(SQLModel, table=True):
    __tablename__ = "alert_escalation_executions"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_alert_escalation_executions_tenant_id_id"),
        Index("ix_alert_escalation_executions_tenant_id_id", "tenant_id", "id"),
        Index("ix_alert_escalation_executions_tenant_alert", "tenant_id", "alert_id"),
        Index("ix_alert_escalation_executions_tenant_reason", "tenant_id", "reason"),
    )

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    tenant_id: str = Field(foreign_key="tenants.id", index=True)
    alert_id: str = Field(foreign_key="alerts.id", index=True)
    reason: AlertEscalationReason = Field(index=True)
    escalation_level: int = Field(ge=1)
    channel: AlertRouteChannel = Field(default=AlertRouteChannel.IN_APP, index=True)
    from_target: str | None = Field(default=None, max_length=200)
    to_target: str = Field(max_length=200)
    detail: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False),
    )
    created_at: datetime = Field(default_factory=now_utc, index=True)


class AlertSilenceRule(SQLModel, table=True):
    __tablename__ = "alert_silence_rules"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_alert_silence_rules_tenant_id_id"),
        Index("ix_alert_silence_rules_tenant_id_id", "tenant_id", "id"),
        Index("ix_alert_silence_rules_tenant_active", "tenant_id", "is_active"),
    )

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    tenant_id: str = Field(foreign_key="tenants.id", index=True)
    name: str = Field(max_length=120)
    alert_type: AlertType | None = Field(default=None, index=True)
    drone_id: str | None = Field(default=None, index=True)
    starts_at: datetime | None = Field(default=None, index=True)
    ends_at: datetime | None = Field(default=None, index=True)
    is_active: bool = Field(default=True, index=True)
    detail: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False),
    )
    created_by: str = Field(index=True)
    created_at: datetime = Field(default_factory=now_utc, index=True)
    updated_at: datetime = Field(default_factory=now_utc, index=True)


class AlertAggregationRule(SQLModel, table=True):
    __tablename__ = "alert_aggregation_rules"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_alert_aggregation_rules_tenant_id_id"),
        UniqueConstraint(
            "tenant_id",
            "name",
            name="uq_alert_aggregation_rules_tenant_name",
        ),
        Index("ix_alert_aggregation_rules_tenant_id_id", "tenant_id", "id"),
        Index("ix_alert_aggregation_rules_tenant_active", "tenant_id", "is_active"),
    )

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    tenant_id: str = Field(foreign_key="tenants.id", index=True)
    name: str = Field(max_length=120, index=True)
    alert_type: AlertType | None = Field(default=None, index=True)
    window_seconds: int = Field(default=300, ge=10)
    is_active: bool = Field(default=True, index=True)
    detail: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False),
    )
    created_by: str = Field(index=True)
    created_at: datetime = Field(default_factory=now_utc, index=True)
    updated_at: datetime = Field(default_factory=now_utc, index=True)


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
    bucket: str | None = Field(default=None, max_length=120, index=True)
    object_key: str | None = Field(default=None, max_length=500)
    object_version: str | None = Field(default=None, max_length=120)
    size_bytes: int | None = Field(default=None, ge=0)
    content_type: str | None = Field(default=None, max_length=120)
    storage_class: str | None = Field(default=None, max_length=50)
    storage_region: str | None = Field(default=None, max_length=50, index=True)
    access_tier: RawDataAccessTier = Field(default=RawDataAccessTier.HOT, index=True)
    etag: str | None = Field(default=None, max_length=200, index=True)
    checksum: str | None = Field(default=None, max_length=200, index=True)
    meta: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False),
    )
    captured_at: datetime = Field(default_factory=now_utc, index=True)
    created_by: str = Field(index=True)
    created_at: datetime = Field(default_factory=now_utc, index=True)


class RawUploadSession(SQLModel, table=True):
    __tablename__ = "raw_upload_sessions"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_raw_upload_sessions_tenant_id_id"),
        UniqueConstraint("upload_token", name="uq_raw_upload_sessions_upload_token"),
        Index("ix_raw_upload_sessions_tenant_id_id", "tenant_id", "id"),
        Index("ix_raw_upload_sessions_tenant_status", "tenant_id", "status"),
        Index("ix_raw_upload_sessions_tenant_created_at", "tenant_id", "created_at"),
        ForeignKeyConstraint(
            ["tenant_id", "task_id"],
            ["inspection_tasks.tenant_id", "inspection_tasks.id"],
            ondelete="SET NULL",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "mission_id"],
            ["missions.tenant_id", "missions.id"],
            ondelete="SET NULL",
        ),
    )

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    tenant_id: str = Field(foreign_key="tenants.id", index=True)
    task_id: str | None = Field(default=None, index=True)
    mission_id: str | None = Field(default=None, index=True)
    data_type: RawDataType = Field(index=True)
    file_name: str = Field(max_length=200)
    content_type: str = Field(max_length=120)
    size_bytes: int = Field(ge=1)
    checksum: str | None = Field(default=None, max_length=200, index=True)
    meta: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False),
    )
    bucket: str = Field(max_length=120, index=True)
    object_key: str = Field(max_length=500)
    storage_class: str = Field(default="STANDARD", max_length=50)
    storage_region: str = Field(default="local", max_length=50)
    status: RawUploadSessionStatus = Field(default=RawUploadSessionStatus.INITIATED, index=True)
    upload_token: str = Field(max_length=120, index=True)
    etag: str | None = Field(default=None, max_length=200)
    completed_raw_id: str | None = Field(default=None, foreign_key="raw_data_catalog_records.id", index=True)
    expires_at: datetime = Field(default_factory=now_utc, index=True)
    created_by: str = Field(index=True)
    created_at: datetime = Field(default_factory=now_utc, index=True)
    updated_at: datetime = Field(default_factory=now_utc, index=True)


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


class OutcomeCatalogVersion(SQLModel, table=True):
    __tablename__ = "outcome_catalog_versions"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_outcome_catalog_versions_tenant_id_id"),
        UniqueConstraint("tenant_id", "outcome_id", "version_no", name="uq_outcome_catalog_versions_outcome_version"),
        Index("ix_outcome_catalog_versions_tenant_id_id", "tenant_id", "id"),
        Index("ix_outcome_catalog_versions_tenant_outcome", "tenant_id", "outcome_id"),
        Index("ix_outcome_catalog_versions_tenant_outcome_version", "tenant_id", "outcome_id", "version_no"),
    )

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    tenant_id: str = Field(foreign_key="tenants.id", index=True)
    outcome_id: str = Field(foreign_key="outcome_catalog_records.id", index=True)
    version_no: int = Field(default=1, ge=1)
    outcome_type: OutcomeType = Field(index=True)
    status: OutcomeStatus = Field(index=True)
    point_lat: float | None = Field(default=None)
    point_lon: float | None = Field(default=None)
    alt_m: float | None = Field(default=None)
    confidence: float | None = Field(default=None, ge=0, le=1)
    payload: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False),
    )
    change_type: OutcomeVersionChangeType = Field(index=True)
    change_note: str | None = Field(default=None, max_length=500)
    created_by: str = Field(index=True)
    created_at: datetime = Field(default_factory=now_utc, index=True)


class AiModelCatalog(SQLModel, table=True):
    __tablename__ = "ai_model_catalogs"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_ai_model_catalogs_tenant_id_id"),
        UniqueConstraint("tenant_id", "model_key", name="uq_ai_model_catalogs_tenant_model_key"),
        Index("ix_ai_model_catalogs_tenant_id_id", "tenant_id", "id"),
        Index("ix_ai_model_catalogs_tenant_model_key", "tenant_id", "model_key"),
        Index("ix_ai_model_catalogs_tenant_provider", "tenant_id", "provider"),
        Index("ix_ai_model_catalogs_tenant_active", "tenant_id", "is_active"),
    )

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    tenant_id: str = Field(foreign_key="tenants.id", index=True)
    model_key: str = Field(max_length=200, index=True)
    provider: str = Field(max_length=80, index=True)
    display_name: str = Field(max_length=120, index=True)
    description: str | None = Field(default=None, max_length=500)
    is_active: bool = Field(default=True, index=True)
    created_by: str = Field(index=True)
    created_at: datetime = Field(default_factory=now_utc, index=True)
    updated_at: datetime = Field(default_factory=now_utc, index=True)


class AiModelVersion(SQLModel, table=True):
    __tablename__ = "ai_model_versions"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_ai_model_versions_tenant_id_id"),
        UniqueConstraint(
            "tenant_id",
            "model_id",
            "version",
            name="uq_ai_model_versions_tenant_model_version",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "model_id"],
            ["ai_model_catalogs.tenant_id", "ai_model_catalogs.id"],
            ondelete="CASCADE",
        ),
        Index("ix_ai_model_versions_tenant_id_id", "tenant_id", "id"),
        Index("ix_ai_model_versions_tenant_model", "tenant_id", "model_id"),
        Index("ix_ai_model_versions_tenant_status", "tenant_id", "status"),
    )

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    tenant_id: str = Field(foreign_key="tenants.id", index=True)
    model_id: str = Field(index=True)
    version: str = Field(max_length=120, index=True)
    status: AiModelVersionStatus = Field(default=AiModelVersionStatus.DRAFT, index=True)
    artifact_ref: str | None = Field(default=None, max_length=500)
    threshold_defaults: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False),
    )
    detail: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False),
    )
    created_by: str = Field(index=True)
    promoted_at: datetime | None = Field(default=None, index=True)
    created_at: datetime = Field(default_factory=now_utc, index=True)
    updated_at: datetime = Field(default_factory=now_utc, index=True)


class AiModelRolloutPolicy(SQLModel, table=True):
    __tablename__ = "ai_model_rollout_policies"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_ai_model_rollout_policies_tenant_id_id"),
        UniqueConstraint("tenant_id", "model_id", name="uq_ai_model_rollout_policies_tenant_model"),
        ForeignKeyConstraint(
            ["tenant_id", "model_id"],
            ["ai_model_catalogs.tenant_id", "ai_model_catalogs.id"],
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "default_version_id"],
            ["ai_model_versions.tenant_id", "ai_model_versions.id"],
            ondelete="SET NULL",
        ),
        Index("ix_ai_model_rollout_policies_tenant_id_id", "tenant_id", "id"),
        Index("ix_ai_model_rollout_policies_tenant_model", "tenant_id", "model_id"),
        Index("ix_ai_model_rollout_policies_tenant_active", "tenant_id", "is_active"),
    )

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    tenant_id: str = Field(foreign_key="tenants.id", index=True)
    model_id: str = Field(index=True)
    default_version_id: str | None = Field(default=None, index=True)
    traffic_allocation: list[dict[str, Any]] = Field(
        default_factory=list,
        sa_column=Column(JSON, nullable=False),
    )
    threshold_overrides: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False),
    )
    detail: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False),
    )
    is_active: bool = Field(default=True, index=True)
    updated_by: str = Field(index=True)
    created_at: datetime = Field(default_factory=now_utc, index=True)
    updated_at: datetime = Field(default_factory=now_utc, index=True)


class AiAnalysisJob(SQLModel, table=True):
    __tablename__ = "ai_analysis_jobs"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_ai_analysis_jobs_tenant_id_id"),
        ForeignKeyConstraint(
            ["tenant_id", "model_version_id"],
            ["ai_model_versions.tenant_id", "ai_model_versions.id"],
            ondelete="RESTRICT",
        ),
        Index("ix_ai_analysis_jobs_tenant_id_id", "tenant_id", "id"),
        Index("ix_ai_analysis_jobs_tenant_task", "tenant_id", "task_id"),
        Index("ix_ai_analysis_jobs_tenant_mission", "tenant_id", "mission_id"),
        Index("ix_ai_analysis_jobs_tenant_topic", "tenant_id", "topic"),
        Index("ix_ai_analysis_jobs_tenant_type", "tenant_id", "job_type"),
        Index("ix_ai_analysis_jobs_tenant_status", "tenant_id", "status"),
        Index("ix_ai_analysis_jobs_tenant_model_version", "tenant_id", "model_version_id"),
    )

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    tenant_id: str = Field(foreign_key="tenants.id", index=True)
    task_id: str | None = Field(default=None, foreign_key="inspection_tasks.id", index=True)
    mission_id: str | None = Field(default=None, foreign_key="missions.id", index=True)
    topic: str | None = Field(default=None, max_length=120, index=True)
    job_type: AiJobType = Field(default=AiJobType.SUMMARY, index=True)
    trigger_mode: AiTriggerMode = Field(default=AiTriggerMode.MANUAL, index=True)
    status: AiJobStatus = Field(default=AiJobStatus.ACTIVE, index=True)
    model_version_id: str | None = Field(default=None, index=True)
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


class BillingPlanCatalog(SQLModel, table=True):
    __tablename__ = "billing_plan_catalogs"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_billing_plan_catalogs_tenant_id_id"),
        UniqueConstraint("tenant_id", "plan_code", name="uq_billing_plan_catalogs_tenant_plan_code"),
        Index("ix_billing_plan_catalogs_tenant_id_id", "tenant_id", "id"),
        Index("ix_billing_plan_catalogs_tenant_plan_code", "tenant_id", "plan_code"),
        Index("ix_billing_plan_catalogs_tenant_cycle", "tenant_id", "billing_cycle"),
        Index("ix_billing_plan_catalogs_tenant_active", "tenant_id", "is_active"),
    )

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    tenant_id: str = Field(foreign_key="tenants.id", index=True)
    plan_code: str = Field(max_length=80, index=True)
    display_name: str = Field(max_length=120, index=True)
    description: str | None = Field(default=None, max_length=500)
    billing_cycle: BillingCycle = Field(default=BillingCycle.MONTHLY, index=True)
    price_cents: int = Field(default=0, ge=0)
    currency: str = Field(default="CNY", max_length=20, index=True)
    is_active: bool = Field(default=True, index=True)
    created_by: str = Field(index=True)
    created_at: datetime = Field(default_factory=now_utc, index=True)
    updated_at: datetime = Field(default_factory=now_utc, index=True)


class BillingPlanQuota(SQLModel, table=True):
    __tablename__ = "billing_plan_quotas"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_billing_plan_quotas_tenant_id_id"),
        UniqueConstraint(
            "tenant_id",
            "plan_id",
            "quota_key",
            name="uq_billing_plan_quotas_tenant_plan_key",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "plan_id"],
            ["billing_plan_catalogs.tenant_id", "billing_plan_catalogs.id"],
            ondelete="CASCADE",
        ),
        Index("ix_billing_plan_quotas_tenant_id_id", "tenant_id", "id"),
        Index("ix_billing_plan_quotas_tenant_plan", "tenant_id", "plan_id"),
        Index("ix_billing_plan_quotas_tenant_key", "tenant_id", "quota_key"),
    )

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    tenant_id: str = Field(foreign_key="tenants.id", index=True)
    plan_id: str = Field(index=True)
    quota_key: str = Field(max_length=120, index=True)
    quota_limit: int = Field(default=0, ge=0)
    enforcement_mode: BillingQuotaEnforcementMode = Field(
        default=BillingQuotaEnforcementMode.HARD_LIMIT,
        index=True,
    )
    detail: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False),
    )
    created_at: datetime = Field(default_factory=now_utc, index=True)
    updated_at: datetime = Field(default_factory=now_utc, index=True)


class TenantSubscription(SQLModel, table=True):
    __tablename__ = "tenant_subscriptions"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_tenant_subscriptions_tenant_id_id"),
        ForeignKeyConstraint(
            ["tenant_id", "plan_id"],
            ["billing_plan_catalogs.tenant_id", "billing_plan_catalogs.id"],
            ondelete="RESTRICT",
        ),
        Index("ix_tenant_subscriptions_tenant_id_id", "tenant_id", "id"),
        Index("ix_tenant_subscriptions_tenant_plan", "tenant_id", "plan_id"),
        Index("ix_tenant_subscriptions_tenant_status", "tenant_id", "status"),
        Index("ix_tenant_subscriptions_tenant_start", "tenant_id", "start_at"),
    )

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    tenant_id: str = Field(foreign_key="tenants.id", index=True)
    plan_id: str = Field(index=True)
    status: BillingSubscriptionStatus = Field(default=BillingSubscriptionStatus.ACTIVE, index=True)
    start_at: datetime = Field(default_factory=now_utc, index=True)
    end_at: datetime | None = Field(default=None, index=True)
    auto_renew: bool = Field(default=True, index=True)
    detail: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False),
    )
    created_by: str = Field(index=True)
    created_at: datetime = Field(default_factory=now_utc, index=True)
    updated_at: datetime = Field(default_factory=now_utc, index=True)


class TenantQuotaOverride(SQLModel, table=True):
    __tablename__ = "tenant_quota_overrides"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_tenant_quota_overrides_tenant_id_id"),
        UniqueConstraint(
            "tenant_id",
            "quota_key",
            name="uq_tenant_quota_overrides_tenant_quota_key",
        ),
        Index("ix_tenant_quota_overrides_tenant_id_id", "tenant_id", "id"),
        Index("ix_tenant_quota_overrides_tenant_key", "tenant_id", "quota_key"),
        Index("ix_tenant_quota_overrides_tenant_active", "tenant_id", "is_active"),
    )

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    tenant_id: str = Field(foreign_key="tenants.id", index=True)
    quota_key: str = Field(max_length=120, index=True)
    override_limit: int = Field(default=0, ge=0)
    enforcement_mode: BillingQuotaEnforcementMode = Field(
        default=BillingQuotaEnforcementMode.HARD_LIMIT,
        index=True,
    )
    reason: str | None = Field(default=None, max_length=500)
    is_active: bool = Field(default=True, index=True)
    detail: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False),
    )
    updated_by: str = Field(index=True)
    created_at: datetime = Field(default_factory=now_utc, index=True)
    updated_at: datetime = Field(default_factory=now_utc, index=True)


class BillingUsageEvent(SQLModel, table=True):
    __tablename__ = "billing_usage_events"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_billing_usage_events_tenant_id_id"),
        UniqueConstraint(
            "tenant_id",
            "meter_key",
            "source_event_id",
            name="uq_billing_usage_events_tenant_meter_source",
        ),
        Index("ix_billing_usage_events_tenant_id_id", "tenant_id", "id"),
        Index("ix_billing_usage_events_tenant_meter", "tenant_id", "meter_key"),
        Index("ix_billing_usage_events_tenant_occurred", "tenant_id", "occurred_at"),
    )

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    tenant_id: str = Field(foreign_key="tenants.id", index=True)
    meter_key: str = Field(max_length=120, index=True)
    quantity: int = Field(default=1, ge=1)
    occurred_at: datetime = Field(default_factory=now_utc, index=True)
    source_event_id: str = Field(max_length=200, index=True)
    detail: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False),
    )
    created_by: str = Field(index=True)
    created_at: datetime = Field(default_factory=now_utc, index=True)


class BillingUsageAggregateDaily(SQLModel, table=True):
    __tablename__ = "billing_usage_aggregate_daily"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_billing_usage_aggregate_daily_tenant_id_id"),
        UniqueConstraint(
            "tenant_id",
            "meter_key",
            "usage_date",
            name="uq_billing_usage_aggregate_daily_tenant_meter_date",
        ),
        Index("ix_billing_usage_aggregate_daily_tenant_id_id", "tenant_id", "id"),
        Index("ix_billing_usage_aggregate_daily_tenant_meter", "tenant_id", "meter_key"),
        Index("ix_billing_usage_aggregate_daily_tenant_date", "tenant_id", "usage_date"),
    )

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    tenant_id: str = Field(foreign_key="tenants.id", index=True)
    meter_key: str = Field(max_length=120, index=True)
    usage_date: datetime = Field(index=True)
    total_quantity: int = Field(default=0, ge=0)
    updated_at: datetime = Field(default_factory=now_utc, index=True)


class BillingInvoice(SQLModel, table=True):
    __tablename__ = "billing_invoices"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_billing_invoices_tenant_id_id"),
        Index("ix_billing_invoices_tenant_id_id", "tenant_id", "id"),
        Index("ix_billing_invoices_tenant_period", "tenant_id", "period_start", "period_end"),
        Index("ix_billing_invoices_tenant_status", "tenant_id", "status"),
    )

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    tenant_id: str = Field(foreign_key="tenants.id", index=True)
    subscription_id: str = Field(index=True)
    plan_id: str = Field(index=True)
    period_start: datetime = Field(index=True)
    period_end: datetime = Field(index=True)
    status: BillingInvoiceStatus = Field(default=BillingInvoiceStatus.DRAFT, index=True)
    currency: str = Field(default="CNY", max_length=20, index=True)
    subtotal_cents: int = Field(default=0)
    adjustments_cents: int = Field(default=0)
    total_amount_cents: int = Field(default=0)
    issued_at: datetime | None = Field(default=None, index=True)
    closed_at: datetime | None = Field(default=None, index=True)
    voided_at: datetime | None = Field(default=None, index=True)
    detail: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False),
    )
    created_by: str = Field(index=True)
    created_at: datetime = Field(default_factory=now_utc, index=True)
    updated_at: datetime = Field(default_factory=now_utc, index=True)


class BillingInvoiceLine(SQLModel, table=True):
    __tablename__ = "billing_invoice_lines"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_billing_invoice_lines_tenant_id_id"),
        ForeignKeyConstraint(
            ["tenant_id", "invoice_id"],
            ["billing_invoices.tenant_id", "billing_invoices.id"],
            ondelete="CASCADE",
        ),
        Index("ix_billing_invoice_lines_tenant_id_id", "tenant_id", "id"),
        Index("ix_billing_invoice_lines_tenant_invoice", "tenant_id", "invoice_id"),
        Index("ix_billing_invoice_lines_tenant_type", "tenant_id", "line_type"),
    )

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    tenant_id: str = Field(foreign_key="tenants.id", index=True)
    invoice_id: str = Field(index=True)
    line_type: str = Field(max_length=50, index=True)
    meter_key: str | None = Field(default=None, max_length=120, index=True)
    description: str = Field(max_length=500)
    quantity: int = Field(default=1, ge=0)
    unit_price_cents: int = Field(default=0)
    amount_cents: int = Field(default=0)
    detail: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False),
    )
    created_at: datetime = Field(default_factory=now_utc, index=True)


class ObservabilitySignal(SQLModel, table=True):
    __tablename__ = "observability_signals"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_observability_signals_tenant_id_id"),
        Index("ix_observability_signals_tenant_id_id", "tenant_id", "id"),
        Index("ix_observability_signals_tenant_type", "tenant_id", "signal_type"),
        Index("ix_observability_signals_tenant_service_ts", "tenant_id", "service_name", "created_at"),
        Index("ix_observability_signals_tenant_trace", "tenant_id", "trace_id"),
    )

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    tenant_id: str = Field(foreign_key="tenants.id", index=True)
    signal_type: ObservabilitySignalType = Field(index=True)
    level: ObservabilitySignalLevel = Field(default=ObservabilitySignalLevel.INFO, index=True)
    service_name: str = Field(max_length=120, index=True)
    signal_name: str = Field(max_length=120, index=True)
    trace_id: str | None = Field(default=None, max_length=120, index=True)
    span_id: str | None = Field(default=None, max_length=120, index=True)
    status_code: int | None = Field(default=None, index=True)
    duration_ms: int | None = Field(default=None, ge=0, index=True)
    numeric_value: float | None = Field(default=None, index=True)
    unit: str | None = Field(default=None, max_length=40)
    message: str | None = Field(default=None, max_length=500)
    detail: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False),
    )
    created_by: str = Field(index=True)
    created_at: datetime = Field(default_factory=now_utc, index=True)


class ObservabilitySloPolicy(SQLModel, table=True):
    __tablename__ = "observability_slo_policies"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_observability_slo_policies_tenant_id_id"),
        UniqueConstraint(
            "tenant_id",
            "policy_key",
            name="uq_observability_slo_policies_tenant_key",
        ),
        Index("ix_observability_slo_policies_tenant_id_id", "tenant_id", "id"),
        Index("ix_observability_slo_policies_tenant_key", "tenant_id", "policy_key"),
        Index("ix_observability_slo_policies_tenant_service", "tenant_id", "service_name"),
        Index("ix_observability_slo_policies_tenant_active", "tenant_id", "is_active"),
    )

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    tenant_id: str = Field(foreign_key="tenants.id", index=True)
    policy_key: str = Field(max_length=120, index=True)
    service_name: str = Field(max_length=120, index=True)
    signal_name: str = Field(default="request", max_length=120, index=True)
    target_ratio: float = Field(default=0.99, ge=0.0, le=1.0)
    latency_threshold_ms: int | None = Field(default=None, ge=1)
    window_minutes: int = Field(default=5, ge=1, le=1440)
    minimum_samples: int = Field(default=1, ge=1)
    alert_severity: ObservabilityAlertSeverity = Field(
        default=ObservabilityAlertSeverity.P2,
        index=True,
    )
    is_active: bool = Field(default=True, index=True)
    detail: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False),
    )
    created_by: str = Field(index=True)
    created_at: datetime = Field(default_factory=now_utc, index=True)
    updated_at: datetime = Field(default_factory=now_utc, index=True)


class ObservabilityAlertEvent(SQLModel, table=True):
    __tablename__ = "observability_alert_events"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_observability_alert_events_tenant_id_id"),
        Index("ix_observability_alert_events_tenant_id_id", "tenant_id", "id"),
        Index("ix_observability_alert_events_tenant_status", "tenant_id", "status"),
        Index("ix_observability_alert_events_tenant_source", "tenant_id", "source"),
        Index("ix_observability_alert_events_tenant_created", "tenant_id", "created_at"),
    )

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    tenant_id: str = Field(foreign_key="tenants.id", index=True)
    source: str = Field(max_length=50, index=True)
    severity: ObservabilityAlertSeverity = Field(default=ObservabilityAlertSeverity.P2, index=True)
    status: ObservabilityAlertStatus = Field(default=ObservabilityAlertStatus.OPEN, index=True)
    title: str = Field(max_length=200)
    message: str = Field(max_length=500)
    policy_id: str | None = Field(default=None, index=True)
    target: str | None = Field(default=None, max_length=200, index=True)
    detail: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False),
    )
    created_at: datetime = Field(default_factory=now_utc, index=True)
    acked_at: datetime | None = Field(default=None, index=True)
    closed_at: datetime | None = Field(default=None, index=True)


class ObservabilitySloEvaluation(SQLModel, table=True):
    __tablename__ = "observability_slo_evaluations"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_observability_slo_evaluations_tenant_id_id"),
        ForeignKeyConstraint(
            ["tenant_id", "policy_id"],
            ["observability_slo_policies.tenant_id", "observability_slo_policies.id"],
            ondelete="CASCADE",
        ),
        Index("ix_observability_slo_evaluations_tenant_id_id", "tenant_id", "id"),
        Index("ix_observability_slo_evaluations_tenant_policy", "tenant_id", "policy_id"),
        Index("ix_observability_slo_evaluations_tenant_status", "tenant_id", "status"),
        Index("ix_observability_slo_evaluations_tenant_window", "tenant_id", "window_start", "window_end"),
    )

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    tenant_id: str = Field(foreign_key="tenants.id", index=True)
    policy_id: str = Field(index=True)
    window_start: datetime = Field(index=True)
    window_end: datetime = Field(index=True)
    total_samples: int = Field(default=0, ge=0)
    good_samples: int = Field(default=0, ge=0)
    availability_ratio: float = Field(default=1.0, ge=0.0, le=1.0)
    error_ratio: float = Field(default=0.0, ge=0.0, le=1.0)
    p95_latency_ms: int | None = Field(default=None, ge=0)
    status: ObservabilitySloStatus = Field(default=ObservabilitySloStatus.HEALTHY, index=True)
    alert_triggered: bool = Field(default=False, index=True)
    alert_event_id: str | None = Field(default=None, index=True)
    oncall_target: str | None = Field(default=None, max_length=200)
    detail: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False),
    )
    created_at: datetime = Field(default_factory=now_utc, index=True)


class ReliabilityBackupRun(SQLModel, table=True):
    __tablename__ = "reliability_backup_runs"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_reliability_backup_runs_tenant_id_id"),
        Index("ix_reliability_backup_runs_tenant_id_id", "tenant_id", "id"),
        Index("ix_reliability_backup_runs_tenant_status", "tenant_id", "status"),
        Index("ix_reliability_backup_runs_tenant_created", "tenant_id", "created_at"),
    )

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    tenant_id: str = Field(foreign_key="tenants.id", index=True)
    run_type: ReliabilityBackupRunType = Field(default=ReliabilityBackupRunType.FULL, index=True)
    status: ReliabilityBackupRunStatus = Field(default=ReliabilityBackupRunStatus.SUCCESS, index=True)
    storage_uri: str | None = Field(default=None, max_length=300)
    checksum: str | None = Field(default=None, max_length=120)
    is_drill: bool = Field(default=False, index=True)
    detail: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False),
    )
    triggered_by: str = Field(index=True)
    created_at: datetime = Field(default_factory=now_utc, index=True)
    completed_at: datetime | None = Field(default=None, index=True)


class ReliabilityRestoreDrill(SQLModel, table=True):
    __tablename__ = "reliability_restore_drills"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_reliability_restore_drills_tenant_id_id"),
        ForeignKeyConstraint(
            ["tenant_id", "backup_run_id"],
            ["reliability_backup_runs.tenant_id", "reliability_backup_runs.id"],
            ondelete="CASCADE",
        ),
        Index("ix_reliability_restore_drills_tenant_id_id", "tenant_id", "id"),
        Index("ix_reliability_restore_drills_tenant_backup", "tenant_id", "backup_run_id"),
    )

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    tenant_id: str = Field(foreign_key="tenants.id", index=True)
    backup_run_id: str = Field(index=True)
    status: ReliabilityRestoreDrillStatus = Field(default=ReliabilityRestoreDrillStatus.PASSED, index=True)
    objective_rto_seconds: int = Field(default=300, ge=1)
    actual_rto_seconds: int = Field(default=0, ge=0)
    detail: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False),
    )
    executed_by: str = Field(index=True)
    created_at: datetime = Field(default_factory=now_utc, index=True)


class SecurityInspectionRun(SQLModel, table=True):
    __tablename__ = "security_inspection_runs"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_security_inspection_runs_tenant_id_id"),
        Index("ix_security_inspection_runs_tenant_id_id", "tenant_id", "id"),
        Index("ix_security_inspection_runs_tenant_created", "tenant_id", "created_at"),
    )

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    tenant_id: str = Field(foreign_key="tenants.id", index=True)
    baseline_version: str = Field(default="phase25-v1", max_length=50)
    total_checks: int = Field(default=0, ge=0)
    passed_checks: int = Field(default=0, ge=0)
    warned_checks: int = Field(default=0, ge=0)
    failed_checks: int = Field(default=0, ge=0)
    score_percent: float = Field(default=100.0, ge=0.0, le=100.0)
    detail: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False),
    )
    executed_by: str = Field(index=True)
    created_at: datetime = Field(default_factory=now_utc, index=True)


class SecurityInspectionItem(SQLModel, table=True):
    __tablename__ = "security_inspection_items"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_security_inspection_items_tenant_id_id"),
        ForeignKeyConstraint(
            ["tenant_id", "run_id"],
            ["security_inspection_runs.tenant_id", "security_inspection_runs.id"],
            ondelete="CASCADE",
        ),
        Index("ix_security_inspection_items_tenant_id_id", "tenant_id", "id"),
        Index("ix_security_inspection_items_tenant_run", "tenant_id", "run_id"),
        Index("ix_security_inspection_items_tenant_status", "tenant_id", "status"),
    )

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    tenant_id: str = Field(foreign_key="tenants.id", index=True)
    run_id: str = Field(index=True)
    check_key: str = Field(max_length=120, index=True)
    status: SecurityInspectionCheckStatus = Field(default=SecurityInspectionCheckStatus.PASS, index=True)
    message: str = Field(max_length=500)
    detail: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False),
    )
    created_at: datetime = Field(default_factory=now_utc, index=True)


class CapacityPolicy(SQLModel, table=True):
    __tablename__ = "capacity_policies"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_capacity_policies_tenant_id_id"),
        UniqueConstraint("tenant_id", "meter_key", name="uq_capacity_policies_tenant_meter_key"),
        Index("ix_capacity_policies_tenant_id_id", "tenant_id", "id"),
        Index("ix_capacity_policies_tenant_meter", "tenant_id", "meter_key"),
        Index("ix_capacity_policies_tenant_active", "tenant_id", "is_active"),
    )

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    tenant_id: str = Field(foreign_key="tenants.id", index=True)
    meter_key: str = Field(max_length=120, index=True)
    target_utilization_pct: int = Field(default=75, ge=1, le=100)
    scale_out_threshold_pct: int = Field(default=85, ge=1, le=100)
    scale_in_threshold_pct: int = Field(default=55, ge=1, le=100)
    min_replicas: int = Field(default=1, ge=1)
    max_replicas: int = Field(default=10, ge=1)
    current_replicas: int = Field(default=1, ge=1)
    is_active: bool = Field(default=True, index=True)
    detail: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False),
    )
    updated_by: str = Field(index=True)
    created_at: datetime = Field(default_factory=now_utc, index=True)
    updated_at: datetime = Field(default_factory=now_utc, index=True)


class CapacityForecast(SQLModel, table=True):
    __tablename__ = "capacity_forecasts"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_capacity_forecasts_tenant_id_id"),
        ForeignKeyConstraint(
            ["tenant_id", "policy_id"],
            ["capacity_policies.tenant_id", "capacity_policies.id"],
            ondelete="CASCADE",
        ),
        Index("ix_capacity_forecasts_tenant_id_id", "tenant_id", "id"),
        Index("ix_capacity_forecasts_tenant_policy", "tenant_id", "policy_id"),
        Index("ix_capacity_forecasts_tenant_meter", "tenant_id", "meter_key"),
        Index("ix_capacity_forecasts_tenant_generated", "tenant_id", "generated_at"),
    )

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    tenant_id: str = Field(foreign_key="tenants.id", index=True)
    policy_id: str = Field(index=True)
    meter_key: str = Field(max_length=120, index=True)
    window_start: datetime = Field(index=True)
    window_end: datetime = Field(index=True)
    predicted_usage: float = Field(default=0.0, ge=0.0)
    recommended_replicas: int = Field(default=1, ge=1)
    decision: CapacityDecision = Field(default=CapacityDecision.HOLD, index=True)
    detail: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False),
    )
    generated_at: datetime = Field(default_factory=now_utc, index=True)


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
    unit_type: OrgUnitType = OrgUnitType.DEPARTMENT
    parent_id: str | None = None
    is_active: bool = True


class OrgUnitUpdate(BaseModel):
    name: str | None = None
    code: str | None = None
    unit_type: OrgUnitType | None = None
    parent_id: str | None = None
    is_active: bool | None = None


class OrgUnitRead(ORMReadModel):
    id: str
    tenant_id: str
    name: str
    code: str
    unit_type: OrgUnitType
    parent_id: str | None
    level: int
    path: str
    is_active: bool
    created_at: datetime
    updated_at: datetime


class UserOrgMembershipBindRequest(BaseModel):
    is_primary: bool = False
    job_title: str | None = None
    job_code: str | None = None
    is_manager: bool | None = None


class UserOrgMembershipLinkRead(ORMReadModel):
    tenant_id: str
    user_id: str
    org_unit_id: str
    is_primary: bool
    job_title: str | None
    job_code: str | None
    is_manager: bool
    created_at: datetime


class DataAccessPolicyUpdate(BaseModel):
    scope_mode: DataScopeMode = DataScopeMode.SCOPED
    org_unit_ids: list[str] = PydanticField(default_factory=list)
    project_codes: list[str] = PydanticField(default_factory=list)
    area_codes: list[str] = PydanticField(default_factory=list)
    task_ids: list[str] = PydanticField(default_factory=list)
    resource_ids: list[str] = PydanticField(default_factory=list)
    denied_org_unit_ids: list[str] = PydanticField(default_factory=list)
    denied_project_codes: list[str] = PydanticField(default_factory=list)
    denied_area_codes: list[str] = PydanticField(default_factory=list)
    denied_task_ids: list[str] = PydanticField(default_factory=list)
    denied_resource_ids: list[str] = PydanticField(default_factory=list)


class RoleDataAccessPolicyUpdate(BaseModel):
    scope_mode: DataScopeMode = DataScopeMode.SCOPED
    org_unit_ids: list[str] = PydanticField(default_factory=list)
    project_codes: list[str] = PydanticField(default_factory=list)
    area_codes: list[str] = PydanticField(default_factory=list)
    task_ids: list[str] = PydanticField(default_factory=list)
    resource_ids: list[str] = PydanticField(default_factory=list)


class DataAccessPolicyRead(ORMReadModel):
    id: str
    tenant_id: str
    user_id: str
    scope_mode: DataScopeMode
    org_unit_ids: list[str]
    project_codes: list[str]
    area_codes: list[str]
    task_ids: list[str]
    resource_ids: list[str]
    denied_org_unit_ids: list[str]
    denied_project_codes: list[str]
    denied_area_codes: list[str]
    denied_task_ids: list[str]
    denied_resource_ids: list[str]
    created_at: datetime
    updated_at: datetime


class RoleDataAccessPolicyRead(ORMReadModel):
    id: str
    tenant_id: str
    role_id: str
    scope_mode: DataScopeMode
    org_unit_ids: list[str]
    project_codes: list[str]
    area_codes: list[str]
    task_ids: list[str]
    resource_ids: list[str]
    created_at: datetime
    updated_at: datetime


class DataAccessPolicyEffectiveRead(BaseModel):
    scope_mode: DataScopeMode
    explicit_allow_org_unit_ids: list[str] = PydanticField(default_factory=list)
    explicit_allow_project_codes: list[str] = PydanticField(default_factory=list)
    explicit_allow_area_codes: list[str] = PydanticField(default_factory=list)
    explicit_allow_task_ids: list[str] = PydanticField(default_factory=list)
    explicit_allow_resource_ids: list[str] = PydanticField(default_factory=list)
    explicit_deny_org_unit_ids: list[str] = PydanticField(default_factory=list)
    explicit_deny_project_codes: list[str] = PydanticField(default_factory=list)
    explicit_deny_area_codes: list[str] = PydanticField(default_factory=list)
    explicit_deny_task_ids: list[str] = PydanticField(default_factory=list)
    explicit_deny_resource_ids: list[str] = PydanticField(default_factory=list)
    inherited_allow_org_unit_ids: list[str] = PydanticField(default_factory=list)
    inherited_allow_project_codes: list[str] = PydanticField(default_factory=list)
    inherited_allow_area_codes: list[str] = PydanticField(default_factory=list)
    inherited_allow_task_ids: list[str] = PydanticField(default_factory=list)
    inherited_allow_resource_ids: list[str] = PydanticField(default_factory=list)
    inherited_allow_all: bool = False
    resolution_order: list[str] = PydanticField(
        default_factory=lambda: [
            "explicit_deny",
            "explicit_allow",
            "inherited_allow",
            "default_deny",
        ]
    )


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
    policy_layer: AirspacePolicyLayer = AirspacePolicyLayer.TENANT
    policy_effect: AirspacePolicyEffect = AirspacePolicyEffect.DENY
    org_unit_id: str | None = None
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
    policy_layer: AirspacePolicyLayer
    policy_effect: AirspacePolicyEffect
    org_unit_id: str | None
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
    template_version: str = "v1"
    evidence_requirements: dict[str, Any] = PydanticField(default_factory=dict)
    require_approval_before_run: bool = True
    is_active: bool = True


class PreflightChecklistTemplateRead(ORMReadModel):
    id: str
    tenant_id: str
    name: str
    description: str | None
    items: list[dict[str, Any]]
    template_version: str
    evidence_requirements: dict[str, Any]
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
    evidence: dict[str, Any] = PydanticField(default_factory=dict)


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
    template_version: str = "v2"
    requires_approval: bool = False
    default_priority: int = PydanticField(default=5, ge=1, le=10)
    default_risk_level: int = PydanticField(default=3, ge=1, le=5)
    default_checklist: list[dict[str, Any]] = PydanticField(default_factory=list)
    route_template: dict[str, Any] = PydanticField(default_factory=dict)
    payload_template: dict[str, Any] = PydanticField(default_factory=dict)
    default_payload: dict[str, Any] = PydanticField(default_factory=dict)
    is_active: bool = True


class TaskTemplateCloneRequest(BaseModel):
    template_key: str
    name: str
    description: str | None = None
    is_active: bool = True


class TaskTemplateRead(ORMReadModel):
    id: str
    tenant_id: str
    task_type_id: str
    template_key: str
    name: str
    description: str | None
    template_version: str = "v2"
    requires_approval: bool
    default_priority: int
    default_risk_level: int
    default_checklist: list[dict[str, Any]]
    route_template: dict[str, Any] = PydanticField(default_factory=dict)
    payload_template: dict[str, Any] = PydanticField(default_factory=dict)
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
    route_template: dict[str, Any] = PydanticField(default_factory=dict)
    payload_template: dict[str, Any] = PydanticField(default_factory=dict)
    planned_start_at: datetime | None = None
    planned_end_at: datetime | None = None
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


class TaskCenterTaskBatchCreateRequest(BaseModel):
    tasks: list[TaskCenterTaskCreate] = PydanticField(default_factory=list, min_length=1)


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


class TaskCenterTaskBatchCreateRead(BaseModel):
    total: int
    tasks: list[TaskCenterTaskRead]


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


class DeviceIntegrationStartRequest(BaseModel):
    drone_id: str
    adapter_vendor: DroneVendor | None = None
    simulation_mode: bool = True
    telemetry_interval_seconds: float = PydanticField(default=1.0, ge=0.0, le=30.0)
    max_samples: int | None = PydanticField(default=None, ge=1, le=100000)


class DeviceIntegrationSessionRead(BaseModel):
    session_id: str
    tenant_id: str
    drone_id: str
    adapter_vendor: DroneVendor
    simulation_mode: bool
    telemetry_interval_seconds: float
    max_samples: int | None
    status: DeviceIntegrationSessionStatus
    samples_ingested: int
    started_at: datetime
    stopped_at: datetime | None = None
    last_error: str | None = None


class VideoStreamCreateRequest(BaseModel):
    stream_key: str = PydanticField(min_length=1, max_length=128)
    protocol: VideoStreamProtocol = VideoStreamProtocol.RTSP
    endpoint: str = PydanticField(min_length=1, max_length=1024)
    label: str | None = PydanticField(default=None, max_length=128)
    drone_id: str | None = None
    enabled: bool = True


class VideoStreamUpdateRequest(BaseModel):
    protocol: VideoStreamProtocol | None = None
    endpoint: str | None = PydanticField(default=None, min_length=1, max_length=1024)
    label: str | None = PydanticField(default=None, max_length=128)
    drone_id: str | None = None
    enabled: bool | None = None


class VideoStreamRead(BaseModel):
    stream_id: str
    stream_key: str
    protocol: VideoStreamProtocol
    endpoint: str
    label: str | None = None
    drone_id: str | None = None
    enabled: bool
    status: VideoStreamStatus
    linked_telemetry: MapPointRead | None = None
    detail: dict[str, Any] = PydanticField(default_factory=dict)
    created_at: datetime
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


class AlertRouteReceiptRequest(BaseModel):
    delivery_status: AlertRouteDeliveryStatus
    receipt_id: str | None = None
    detail: dict[str, Any] = PydanticField(default_factory=dict)


class AlertOncallShiftCreate(BaseModel):
    shift_name: str = "default"
    target: str
    starts_at: datetime
    ends_at: datetime
    timezone: str = "UTC"
    is_active: bool = True
    detail: dict[str, Any] = PydanticField(default_factory=dict)


class AlertOncallShiftRead(ORMReadModel):
    id: str
    tenant_id: str
    shift_name: str
    target: str
    starts_at: datetime
    ends_at: datetime
    timezone: str
    is_active: bool
    detail: dict[str, Any]
    created_by: str
    created_at: datetime
    updated_at: datetime


class AlertEscalationPolicyCreate(BaseModel):
    priority_level: AlertPriority
    ack_timeout_seconds: int = PydanticField(default=1800, ge=30)
    repeat_threshold: int = PydanticField(default=3, ge=2)
    max_escalation_level: int = PydanticField(default=1, ge=1)
    escalation_channel: AlertRouteChannel = AlertRouteChannel.IN_APP
    escalation_target: str = "oncall://active"
    is_active: bool = True
    detail: dict[str, Any] = PydanticField(default_factory=dict)


class AlertEscalationPolicyRead(ORMReadModel):
    id: str
    tenant_id: str
    priority_level: AlertPriority
    ack_timeout_seconds: int
    repeat_threshold: int
    max_escalation_level: int
    escalation_channel: AlertRouteChannel
    escalation_target: str
    is_active: bool
    detail: dict[str, Any]
    created_by: str
    created_at: datetime
    updated_at: datetime


class AlertEscalationRunRequest(BaseModel):
    dry_run: bool = False
    limit: int = PydanticField(default=200, ge=1, le=1000)


class AlertEscalationRunItemRead(BaseModel):
    alert_id: str
    reason: AlertEscalationReason
    channel: AlertRouteChannel
    from_target: str | None
    to_target: str
    escalation_level: int


class AlertEscalationRunRead(BaseModel):
    scanned_count: int
    escalated_count: int
    dry_run: bool
    items: list[AlertEscalationRunItemRead]


class AlertSilenceRuleCreate(BaseModel):
    name: str
    alert_type: AlertType | None = None
    drone_id: str | None = None
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    is_active: bool = True
    detail: dict[str, Any] = PydanticField(default_factory=dict)


class AlertSilenceRuleRead(ORMReadModel):
    id: str
    tenant_id: str
    name: str
    alert_type: AlertType | None
    drone_id: str | None
    starts_at: datetime | None
    ends_at: datetime | None
    is_active: bool
    detail: dict[str, Any]
    created_by: str
    created_at: datetime
    updated_at: datetime


class AlertAggregationRuleCreate(BaseModel):
    name: str
    alert_type: AlertType | None = None
    window_seconds: int = PydanticField(default=300, ge=10)
    is_active: bool = True
    detail: dict[str, Any] = PydanticField(default_factory=dict)


class AlertAggregationRuleRead(ORMReadModel):
    id: str
    tenant_id: str
    name: str
    alert_type: AlertType | None
    window_seconds: int
    is_active: bool
    detail: dict[str, Any]
    created_by: str
    created_at: datetime
    updated_at: datetime


class AlertSlaOverviewRead(BaseModel):
    from_ts: datetime | None
    to_ts: datetime | None
    total_alerts: int
    acked_alerts: int
    closed_alerts: int
    timeout_escalated_alerts: int
    mtta_seconds_avg: float
    mttr_seconds_avg: float
    timeout_escalation_rate: float


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
    bucket: str | None
    object_key: str | None
    object_version: str | None
    size_bytes: int | None
    content_type: str | None
    storage_class: str | None
    storage_region: str | None
    access_tier: RawDataAccessTier
    etag: str | None
    checksum: str | None
    meta: dict[str, Any]
    captured_at: datetime
    created_by: str
    created_at: datetime


class RawUploadInitRequest(BaseModel):
    task_id: str | None = None
    mission_id: str | None = None
    data_type: RawDataType
    file_name: str
    content_type: str = "application/octet-stream"
    size_bytes: int = PydanticField(ge=1)
    checksum: str | None = None
    storage_class: str = "STANDARD"
    storage_region: str = "local"
    meta: dict[str, Any] = PydanticField(default_factory=dict)


class RawUploadInitRead(BaseModel):
    session_id: str
    upload_token: str
    upload_url: str
    bucket: str
    object_key: str
    expires_at: datetime


class RawUploadCompleteRequest(BaseModel):
    upload_token: str


class RawDataStorageTransitionRequest(BaseModel):
    access_tier: RawDataAccessTier
    storage_region: str | None = None


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


class OutcomeCatalogVersionRead(ORMReadModel):
    id: str
    tenant_id: str
    outcome_id: str
    version_no: int
    outcome_type: OutcomeType
    status: OutcomeStatus
    point_lat: float | None
    point_lon: float | None
    alt_m: float | None
    confidence: float | None
    payload: dict[str, Any]
    change_type: OutcomeVersionChangeType
    change_note: str | None
    created_by: str
    created_at: datetime


class AiModelCatalogCreate(BaseModel):
    model_key: str
    provider: str = "builtin"
    display_name: str
    description: str | None = None
    is_active: bool = True


class AiModelCatalogRead(ORMReadModel):
    id: str
    tenant_id: str
    model_key: str
    provider: str
    display_name: str
    description: str | None
    is_active: bool
    created_by: str
    created_at: datetime
    updated_at: datetime


class AiModelVersionCreate(BaseModel):
    version: str
    status: AiModelVersionStatus = AiModelVersionStatus.DRAFT
    artifact_ref: str | None = None
    threshold_defaults: dict[str, Any] = PydanticField(default_factory=dict)
    detail: dict[str, Any] = PydanticField(default_factory=dict)


class AiModelVersionRead(ORMReadModel):
    id: str
    tenant_id: str
    model_id: str
    version: str
    status: AiModelVersionStatus
    artifact_ref: str | None
    threshold_defaults: dict[str, Any]
    detail: dict[str, Any]
    created_by: str
    promoted_at: datetime | None
    created_at: datetime
    updated_at: datetime


class AiModelVersionPromoteRequest(BaseModel):
    target_status: AiModelVersionStatus = AiModelVersionStatus.STABLE
    note: str | None = None


class AiModelRolloutPolicyUpsertRequest(BaseModel):
    default_version_id: str | None = None
    traffic_allocation: list[dict[str, Any]] = PydanticField(default_factory=list)
    threshold_overrides: dict[str, Any] = PydanticField(default_factory=dict)
    detail: dict[str, Any] = PydanticField(default_factory=dict)
    is_active: bool = True


class AiModelRolloutPolicyRead(ORMReadModel):
    id: str
    tenant_id: str
    model_id: str
    default_version_id: str | None
    traffic_allocation: list[dict[str, Any]]
    threshold_overrides: dict[str, Any]
    detail: dict[str, Any]
    is_active: bool
    updated_by: str
    created_at: datetime
    updated_at: datetime


class AiAnalysisJobCreate(BaseModel):
    task_id: str | None = None
    mission_id: str | None = None
    topic: str | None = None
    job_type: AiJobType = AiJobType.SUMMARY
    trigger_mode: AiTriggerMode = AiTriggerMode.MANUAL
    model_version_id: str | None = None
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
    model_version_id: str | None
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
    force_model_version_id: str | None = None
    force_threshold_config: dict[str, Any] = PydanticField(default_factory=dict)
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


class AiAnalysisJobBindModelVersionRequest(BaseModel):
    model_version_id: str


class AiEvaluationRecomputeRequest(BaseModel):
    model_id: str | None = None
    job_id: str | None = None
    from_ts: datetime | None = None
    to_ts: datetime | None = None


class AiEvaluationSummaryRead(BaseModel):
    model_version_id: str
    total_runs: int
    succeeded_runs: int
    success_rate: float
    review_override_rate: float
    p95_latency_ms: int | None


class AiEvaluationCompareRead(BaseModel):
    left: AiEvaluationSummaryRead
    right: AiEvaluationSummaryRead
    delta_success_rate: float
    delta_review_override_rate: float
    delta_p95_latency_ms: int | None


class AiModelRolloutRollbackRequest(BaseModel):
    target_version_id: str
    reason: str | None = None


class AiScheduleTickRequest(BaseModel):
    window_key: str
    job_ids: list[str] = PydanticField(default_factory=list)
    max_jobs: int = PydanticField(default=100, ge=1, le=1000)
    context: dict[str, Any] = PydanticField(default_factory=dict)


class AiScheduleTickRead(BaseModel):
    window_key: str
    scanned_jobs: int
    triggered_jobs: int
    skipped_jobs: int
    run_ids: list[str]


class BillingPlanQuotaInput(BaseModel):
    quota_key: str
    quota_limit: int = PydanticField(default=0, ge=0)
    enforcement_mode: BillingQuotaEnforcementMode = BillingQuotaEnforcementMode.HARD_LIMIT
    detail: dict[str, Any] = PydanticField(default_factory=dict)


class BillingPlanCreate(BaseModel):
    plan_code: str
    display_name: str
    description: str | None = None
    billing_cycle: BillingCycle = BillingCycle.MONTHLY
    price_cents: int = PydanticField(default=0, ge=0)
    currency: str = "CNY"
    is_active: bool = True
    quotas: list[BillingPlanQuotaInput] = PydanticField(default_factory=list)


class BillingPlanQuotaRead(ORMReadModel):
    id: str
    tenant_id: str
    plan_id: str
    quota_key: str
    quota_limit: int
    enforcement_mode: BillingQuotaEnforcementMode
    detail: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class BillingPlanRead(BaseModel):
    id: str
    tenant_id: str
    plan_code: str
    display_name: str
    description: str | None
    billing_cycle: BillingCycle
    price_cents: int
    currency: str
    is_active: bool
    created_by: str
    created_at: datetime
    updated_at: datetime
    quotas: list[BillingPlanQuotaRead] = PydanticField(default_factory=list)


class BillingSubscriptionCreate(BaseModel):
    plan_id: str
    status: BillingSubscriptionStatus = BillingSubscriptionStatus.ACTIVE
    start_at: datetime = PydanticField(default_factory=now_utc)
    end_at: datetime | None = None
    auto_renew: bool = True
    detail: dict[str, Any] = PydanticField(default_factory=dict)


class BillingSubscriptionRead(ORMReadModel):
    id: str
    tenant_id: str
    plan_id: str
    status: BillingSubscriptionStatus
    start_at: datetime
    end_at: datetime | None
    auto_renew: bool
    detail: dict[str, Any]
    created_by: str
    created_at: datetime
    updated_at: datetime


class BillingQuotaOverrideInput(BaseModel):
    quota_key: str
    override_limit: int = PydanticField(default=0, ge=0)
    enforcement_mode: BillingQuotaEnforcementMode = BillingQuotaEnforcementMode.HARD_LIMIT
    reason: str | None = None
    is_active: bool = True
    detail: dict[str, Any] = PydanticField(default_factory=dict)


class BillingQuotaOverrideUpsertRequest(BaseModel):
    overrides: list[BillingQuotaOverrideInput] = PydanticField(default_factory=list, min_length=1)


class BillingQuotaOverrideRead(ORMReadModel):
    id: str
    tenant_id: str
    quota_key: str
    override_limit: int
    enforcement_mode: BillingQuotaEnforcementMode
    reason: str | None
    is_active: bool
    detail: dict[str, Any]
    updated_by: str
    created_at: datetime
    updated_at: datetime


class BillingEffectiveQuotaRead(BaseModel):
    quota_key: str
    quota_limit: int
    enforcement_mode: BillingQuotaEnforcementMode
    source: str


class BillingTenantQuotaSnapshotRead(BaseModel):
    tenant_id: str
    subscription_id: str | None
    plan_id: str | None
    plan_code: str | None
    quotas: list[BillingEffectiveQuotaRead] = PydanticField(default_factory=list)
    computed_at: datetime = PydanticField(default_factory=now_utc)


class BillingUsageIngestRequest(BaseModel):
    meter_key: str
    quantity: int = PydanticField(default=1, ge=1)
    occurred_at: datetime = PydanticField(default_factory=now_utc)
    source_event_id: str
    detail: dict[str, Any] = PydanticField(default_factory=dict)


class BillingUsageEventRead(ORMReadModel):
    id: str
    tenant_id: str
    meter_key: str
    quantity: int
    occurred_at: datetime
    source_event_id: str
    detail: dict[str, Any]
    created_by: str
    created_at: datetime


class BillingUsageIngestRead(BaseModel):
    event: BillingUsageEventRead
    deduplicated: bool


class BillingUsageSummaryRead(BaseModel):
    meter_key: str
    total_quantity: int
    from_date: datetime | None
    to_date: datetime | None


class BillingQuotaCheckRequest(BaseModel):
    meter_key: str
    quantity: int = PydanticField(default=1, ge=1)
    as_of: datetime = PydanticField(default_factory=now_utc)


class BillingQuotaCheckRead(BaseModel):
    meter_key: str
    quota_limit: int | None
    enforcement_mode: BillingQuotaEnforcementMode | None
    used_quantity: int
    request_quantity: int
    projected_quantity: int
    allowed: bool
    source: str
    reason: str


class BillingInvoiceGenerateRequest(BaseModel):
    tenant_id: str
    period_start: datetime
    period_end: datetime
    adjustments_cents: int = 0
    force_recompute: bool = True
    detail: dict[str, Any] = PydanticField(default_factory=dict)


class BillingInvoiceLineRead(ORMReadModel):
    id: str
    tenant_id: str
    invoice_id: str
    line_type: str
    meter_key: str | None
    description: str
    quantity: int
    unit_price_cents: int
    amount_cents: int
    detail: dict[str, Any]
    created_at: datetime


class BillingInvoiceRead(ORMReadModel):
    id: str
    tenant_id: str
    subscription_id: str
    plan_id: str
    period_start: datetime
    period_end: datetime
    status: BillingInvoiceStatus
    currency: str
    subtotal_cents: int
    adjustments_cents: int
    total_amount_cents: int
    issued_at: datetime | None
    closed_at: datetime | None
    voided_at: datetime | None
    detail: dict[str, Any]
    created_by: str
    created_at: datetime
    updated_at: datetime


class BillingInvoiceDetailRead(BaseModel):
    invoice: BillingInvoiceRead
    lines: list[BillingInvoiceLineRead]


class BillingInvoiceCloseRequest(BaseModel):
    note: str | None = None


class BillingInvoiceVoidRequest(BaseModel):
    reason: str | None = None


class ObservabilitySignalIngestItem(BaseModel):
    signal_type: ObservabilitySignalType
    level: ObservabilitySignalLevel = ObservabilitySignalLevel.INFO
    service_name: str
    signal_name: str
    trace_id: str | None = None
    span_id: str | None = None
    status_code: int | None = None
    duration_ms: int | None = PydanticField(default=None, ge=0)
    numeric_value: float | None = None
    unit: str | None = None
    message: str | None = None
    detail: dict[str, Any] = PydanticField(default_factory=dict)
    occurred_at: datetime = PydanticField(default_factory=now_utc)


class ObservabilitySignalIngestRequest(BaseModel):
    items: list[ObservabilitySignalIngestItem] = PydanticField(default_factory=list, min_length=1)


class ObservabilitySignalRead(ORMReadModel):
    id: str
    tenant_id: str
    signal_type: ObservabilitySignalType
    level: ObservabilitySignalLevel
    service_name: str
    signal_name: str
    trace_id: str | None
    span_id: str | None
    status_code: int | None
    duration_ms: int | None
    numeric_value: float | None
    unit: str | None
    message: str | None
    detail: dict[str, Any]
    created_by: str
    created_at: datetime


class ObservabilitySignalIngestRead(BaseModel):
    accepted_count: int
    signals: list[ObservabilitySignalRead]


class ObservabilityOverviewRead(BaseModel):
    window_minutes: int
    total_signals: int
    error_signals: int
    p95_latency_ms: int | None
    by_type: dict[str, int]
    by_level: dict[str, int]
    computed_at: datetime = PydanticField(default_factory=now_utc)


class ObservabilitySloPolicyCreate(BaseModel):
    policy_key: str
    service_name: str
    signal_name: str = "request"
    target_ratio: float = PydanticField(default=0.99, ge=0.0, le=1.0)
    latency_threshold_ms: int | None = PydanticField(default=None, ge=1)
    window_minutes: int = PydanticField(default=5, ge=1, le=1440)
    minimum_samples: int = PydanticField(default=1, ge=1)
    alert_severity: ObservabilityAlertSeverity = ObservabilityAlertSeverity.P2
    is_active: bool = True
    detail: dict[str, Any] = PydanticField(default_factory=dict)


class ObservabilitySloPolicyRead(ORMReadModel):
    id: str
    tenant_id: str
    policy_key: str
    service_name: str
    signal_name: str
    target_ratio: float
    latency_threshold_ms: int | None
    window_minutes: int
    minimum_samples: int
    alert_severity: ObservabilityAlertSeverity
    is_active: bool
    detail: dict[str, Any]
    created_by: str
    created_at: datetime
    updated_at: datetime


class ObservabilitySloEvaluateRequest(BaseModel):
    policy_ids: list[str] = PydanticField(default_factory=list)
    window_minutes: int | None = PydanticField(default=None, ge=1, le=1440)
    dry_run: bool = False


class ObservabilityAlertEventRead(ORMReadModel):
    id: str
    tenant_id: str
    source: str
    severity: ObservabilityAlertSeverity
    status: ObservabilityAlertStatus
    title: str
    message: str
    policy_id: str | None
    target: str | None
    detail: dict[str, Any]
    created_at: datetime
    acked_at: datetime | None
    closed_at: datetime | None


class ObservabilitySloEvaluationRead(ORMReadModel):
    id: str
    tenant_id: str
    policy_id: str
    window_start: datetime
    window_end: datetime
    total_samples: int
    good_samples: int
    availability_ratio: float
    error_ratio: float
    p95_latency_ms: int | None
    status: ObservabilitySloStatus
    alert_triggered: bool
    alert_event_id: str | None
    oncall_target: str | None
    detail: dict[str, Any]
    created_at: datetime


class ObservabilitySloEvaluateResultRead(BaseModel):
    evaluated_count: int
    breached_count: int
    alerts_created: int
    items: list[ObservabilitySloEvaluationRead]


class ObservabilitySloOverviewRead(BaseModel):
    policy_count: int
    healthy_count: int
    breached_count: int
    latest_evaluated_at: datetime | None
    items: list[ObservabilitySloEvaluationRead]


class ReliabilityBackupRunRequest(BaseModel):
    run_type: ReliabilityBackupRunType = ReliabilityBackupRunType.FULL
    storage_uri: str | None = None
    is_drill: bool = False
    detail: dict[str, Any] = PydanticField(default_factory=dict)


class ReliabilityBackupRunRead(ORMReadModel):
    id: str
    tenant_id: str
    run_type: ReliabilityBackupRunType
    status: ReliabilityBackupRunStatus
    storage_uri: str | None
    checksum: str | None
    is_drill: bool
    detail: dict[str, Any]
    triggered_by: str
    created_at: datetime
    completed_at: datetime | None


class ReliabilityRestoreDrillRequest(BaseModel):
    objective_rto_seconds: int = PydanticField(default=300, ge=1)
    simulated_restore_seconds: int = PydanticField(default=120, ge=0)
    detail: dict[str, Any] = PydanticField(default_factory=dict)


class ReliabilityRestoreDrillRead(ORMReadModel):
    id: str
    tenant_id: str
    backup_run_id: str
    status: ReliabilityRestoreDrillStatus
    objective_rto_seconds: int
    actual_rto_seconds: int
    detail: dict[str, Any]
    executed_by: str
    created_at: datetime


class SecurityInspectionRunRequest(BaseModel):
    baseline_version: str = "phase25-v1"
    detail: dict[str, Any] = PydanticField(default_factory=dict)


class SecurityInspectionItemRead(ORMReadModel):
    id: str
    tenant_id: str
    run_id: str
    check_key: str
    status: SecurityInspectionCheckStatus
    message: str
    detail: dict[str, Any]
    created_at: datetime


class SecurityInspectionRunRead(ORMReadModel):
    id: str
    tenant_id: str
    baseline_version: str
    total_checks: int
    passed_checks: int
    warned_checks: int
    failed_checks: int
    score_percent: float
    detail: dict[str, Any]
    executed_by: str
    created_at: datetime
    items: list[SecurityInspectionItemRead] = PydanticField(default_factory=list)


class CapacityPolicyUpsertRequest(BaseModel):
    target_utilization_pct: int = PydanticField(default=75, ge=1, le=100)
    scale_out_threshold_pct: int = PydanticField(default=85, ge=1, le=100)
    scale_in_threshold_pct: int = PydanticField(default=55, ge=1, le=100)
    min_replicas: int = PydanticField(default=1, ge=1)
    max_replicas: int = PydanticField(default=10, ge=1)
    current_replicas: int = PydanticField(default=1, ge=1)
    is_active: bool = True
    detail: dict[str, Any] = PydanticField(default_factory=dict)


class CapacityPolicyRead(ORMReadModel):
    id: str
    tenant_id: str
    meter_key: str
    target_utilization_pct: int
    scale_out_threshold_pct: int
    scale_in_threshold_pct: int
    min_replicas: int
    max_replicas: int
    current_replicas: int
    is_active: bool
    detail: dict[str, Any]
    updated_by: str
    created_at: datetime
    updated_at: datetime


class CapacityForecastRequest(BaseModel):
    meter_key: str
    window_minutes: int = PydanticField(default=60, ge=5, le=1440)
    sample_minutes: int = PydanticField(default=180, ge=5, le=10080)


class CapacityForecastRead(ORMReadModel):
    id: str
    tenant_id: str
    policy_id: str
    meter_key: str
    window_start: datetime
    window_end: datetime
    predicted_usage: float
    recommended_replicas: int
    decision: CapacityDecision
    detail: dict[str, Any]
    generated_at: datetime


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


class OutcomeReportTemplate(SQLModel, table=True):
    __tablename__ = "outcome_report_templates"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_outcome_report_templates_tenant_id_id"),
        UniqueConstraint("tenant_id", "name", name="uq_outcome_report_templates_tenant_name"),
        Index("ix_outcome_report_templates_tenant_id_id", "tenant_id", "id"),
        Index("ix_outcome_report_templates_tenant_active", "tenant_id", "is_active"),
    )

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    tenant_id: str = Field(foreign_key="tenants.id", index=True)
    name: str = Field(max_length=120, index=True)
    format_default: ReportFileFormat = Field(default=ReportFileFormat.PDF, index=True)
    title_template: str = Field(default="Outcome Report")
    body_template: str = Field(default="")
    is_active: bool = Field(default=True, index=True)
    created_by: str = Field(index=True)
    created_at: datetime = Field(default_factory=now_utc, index=True)
    updated_at: datetime = Field(default_factory=now_utc, index=True)


class OutcomeReportExport(SQLModel, table=True):
    __tablename__ = "outcome_report_exports"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_outcome_report_exports_tenant_id_id"),
        Index("ix_outcome_report_exports_tenant_id_id", "tenant_id", "id"),
        Index("ix_outcome_report_exports_tenant_template", "tenant_id", "template_id"),
        Index("ix_outcome_report_exports_tenant_status", "tenant_id", "status"),
    )

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    tenant_id: str = Field(foreign_key="tenants.id", index=True)
    template_id: str = Field(foreign_key="outcome_report_templates.id", index=True)
    report_format: ReportFileFormat = Field(default=ReportFileFormat.PDF, index=True)
    status: ReportExportStatus = Field(default=ReportExportStatus.RUNNING, index=True)
    task_id: str | None = Field(default=None, foreign_key="inspection_tasks.id", index=True)
    from_ts: datetime | None = Field(default=None, index=True)
    to_ts: datetime | None = Field(default=None, index=True)
    topic: str | None = Field(default=None, max_length=120, index=True)
    file_path: str | None = Field(default=None)
    detail: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False),
    )
    requested_by: str = Field(index=True)
    created_at: datetime = Field(default_factory=now_utc, index=True)
    updated_at: datetime = Field(default_factory=now_utc, index=True)
    completed_at: datetime | None = Field(default=None, index=True)


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
    AIRSPACE = "airspace"
    ALERTS = "alerts"
    EVENTS = "events"
    OUTCOMES = "outcomes"


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
    airspace_total: int
    alerts_total: int
    events_total: int
    outcomes_total: int
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


class ComplianceApprovalFlowTemplateCreate(BaseModel):
    name: str
    entity_type: str
    steps: list[dict[str, Any]] = PydanticField(default_factory=list, min_length=1)
    is_active: bool = True


class ComplianceApprovalFlowTemplateRead(ORMReadModel):
    id: str
    tenant_id: str
    name: str
    entity_type: str
    steps: list[dict[str, Any]]
    is_active: bool
    created_by: str
    created_at: datetime
    updated_at: datetime


class ComplianceApprovalFlowInstanceCreate(BaseModel):
    template_id: str
    entity_type: str
    entity_id: str


class ComplianceApprovalFlowInstanceActionRequest(BaseModel):
    action: ApprovalFlowAction
    note: str | None = None


class ComplianceApprovalFlowInstanceRead(ORMReadModel):
    id: str
    tenant_id: str
    template_id: str
    entity_type: str
    entity_id: str
    status: ApprovalFlowInstanceStatus
    current_step_index: int
    steps_snapshot: list[dict[str, Any]]
    action_history: list[dict[str, Any]]
    created_by: str
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None


class ComplianceDecisionRecordRead(ORMReadModel):
    id: str
    tenant_id: str
    source: str
    entity_type: str
    entity_id: str
    decision: ComplianceDecision
    reason_code: str | None
    actor_id: str | None
    detail: dict[str, Any]
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


class OutcomeReportTemplateCreate(BaseModel):
    name: str
    format_default: ReportFileFormat = ReportFileFormat.PDF
    title_template: str = "Outcome Report"
    body_template: str = ""
    is_active: bool = True


class OutcomeReportTemplateRead(ORMReadModel):
    id: str
    tenant_id: str
    name: str
    format_default: ReportFileFormat
    title_template: str
    body_template: str
    is_active: bool
    created_by: str
    created_at: datetime
    updated_at: datetime


class OutcomeReportExportCreateRequest(BaseModel):
    template_id: str
    report_format: ReportFileFormat | None = None
    task_id: str | None = None
    from_ts: datetime | None = None
    to_ts: datetime | None = None
    topic: str | None = None


class OutcomeReportExportRead(ORMReadModel):
    id: str
    tenant_id: str
    template_id: str
    report_format: ReportFileFormat
    status: ReportExportStatus
    task_id: str | None
    from_ts: datetime | None
    to_ts: datetime | None
    topic: str | None
    file_path: str | None
    detail: dict[str, Any]
    requested_by: str
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None


class OutcomeReportRetentionRunRequest(BaseModel):
    retention_days: int = PydanticField(default=30, ge=1)
    dry_run: bool = True


class OutcomeReportRetentionRunRead(BaseModel):
    scanned_count: int
    expired_count: int
    deleted_files: int
    skipped_files: int
