from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict
from pydantic import Field as PydanticField
from sqlalchemy import JSON, Column, ForeignKeyConstraint, Index, UniqueConstraint
from sqlmodel import Field, SQLModel

from app.domain.state_machine import MissionState


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
        Index("ix_missions_tenant_drone_id", "tenant_id", "drone_id"),
        Index("ix_missions_tenant_state", "tenant_id", "state"),
    )

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    tenant_id: str = Field(foreign_key="tenants.id", index=True)
    name: str = Field(index=True)
    drone_id: str | None = Field(default=None, index=True)
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


class AlertStatus(StrEnum):
    OPEN = "OPEN"
    ACKED = "ACKED"
    CLOSED = "CLOSED"


class AlertRecord(SQLModel, table=True):
    __tablename__ = "alerts"

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    tenant_id: str = Field(foreign_key="tenants.id", index=True)
    drone_id: str = Field(index=True)
    alert_type: AlertType = Field(index=True)
    severity: AlertSeverity = Field(index=True)
    status: AlertStatus = Field(default=AlertStatus.OPEN, index=True)
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


class MissionCreate(BaseModel):
    name: str
    drone_id: str | None = None
    type: MissionPlanType
    payload: dict[str, Any] = PydanticField(default_factory=dict)
    constraints: dict[str, Any] = PydanticField(default_factory=dict)


class MissionUpdate(BaseModel):
    name: str | None = None
    drone_id: str | None = None
    payload: dict[str, Any] | None = None
    constraints: dict[str, Any] | None = None


class MissionRead(ORMReadModel):
    id: str
    tenant_id: str
    name: str
    drone_id: str | None
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
    status: AlertStatus
    message: str
    detail: dict[str, Any]
    first_seen_at: datetime
    last_seen_at: datetime
    acked_by: str | None
    acked_at: datetime | None
    closed_by: str | None
    closed_at: datetime | None


class AlertActionRequest(BaseModel):
    comment: str | None = None


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
        Index("ix_inspection_tasks_tenant_id_id", "tenant_id", "id"),
        Index("ix_inspection_tasks_tenant_template_id", "tenant_id", "template_id"),
    )

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    tenant_id: str = Field(foreign_key="tenants.id", index=True)
    name: str = Field(max_length=100, index=True)
    template_id: str = Field(index=True)
    mission_id: str | None = Field(default=None, foreign_key="missions.id", index=True)
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
        Index("ix_defects_tenant_id_id", "tenant_id", "id"),
        Index("ix_defects_tenant_observation_id", "tenant_id", "observation_id"),
    )

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    tenant_id: str = Field(foreign_key="tenants.id", index=True)
    observation_id: str = Field(foreign_key="inspection_observations.id", index=True)
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
            ["tenant_id", "linked_task_id"],
            ["inspection_tasks.tenant_id", "inspection_tasks.id"],
            ondelete="RESTRICT",
        ),
        Index("ix_incidents_tenant_id_id", "tenant_id", "id"),
        Index("ix_incidents_tenant_linked_task_id", "tenant_id", "linked_task_id"),
    )

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    tenant_id: str = Field(foreign_key="tenants.id", index=True)
    title: str = Field(max_length=200)
    level: str = Field(max_length=20, index=True)
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
    area_geom: str = ""
    priority: int = 5
    status: InspectionTaskStatus = InspectionTaskStatus.SCHEDULED


class InspectionTaskRead(ORMReadModel):
    id: str
    tenant_id: str
    name: str
    template_id: str
    mission_id: str | None
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
    location_geom: str


class IncidentRead(ORMReadModel):
    id: str
    tenant_id: str
    title: str
    level: str
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
