"""phase12 airspace compliance expand

Revision ID: 202602250047
Revises: 202602240046
Create Date: 2026-02-25
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "202602250047"
down_revision = "202602240046"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "airspace_zones",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("zone_type", sa.String(), nullable=False),
        sa.Column("area_code", sa.String(length=100), nullable=True),
        sa.Column("geom_wkt", sa.Text(), nullable=False),
        sa.Column("max_alt_m", sa.Float(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("detail", sa.JSON(), nullable=False),
        sa.Column("created_by", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "id", name="uq_airspace_zones_tenant_id_id"),
    )
    op.create_index("ix_airspace_zones_tenant_id", "airspace_zones", ["tenant_id"])
    op.create_index("ix_airspace_zones_name", "airspace_zones", ["name"])
    op.create_index("ix_airspace_zones_zone_type", "airspace_zones", ["zone_type"])
    op.create_index("ix_airspace_zones_area_code", "airspace_zones", ["area_code"])
    op.create_index("ix_airspace_zones_is_active", "airspace_zones", ["is_active"])
    op.create_index("ix_airspace_zones_created_by", "airspace_zones", ["created_by"])
    op.create_index("ix_airspace_zones_created_at", "airspace_zones", ["created_at"])
    op.create_index("ix_airspace_zones_updated_at", "airspace_zones", ["updated_at"])
    op.create_index("ix_airspace_zones_tenant_id_id", "airspace_zones", ["tenant_id", "id"])
    op.create_index("ix_airspace_zones_tenant_type", "airspace_zones", ["tenant_id", "zone_type"])

    op.create_table(
        "preflight_checklist_templates",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("items", sa.JSON(), nullable=False),
        sa.Column(
            "require_approval_before_run",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_by", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "id", name="uq_preflight_templates_tenant_id_id"),
    )
    op.create_index("ix_preflight_checklist_templates_tenant_id", "preflight_checklist_templates", ["tenant_id"])
    op.create_index("ix_preflight_checklist_templates_name", "preflight_checklist_templates", ["name"])
    op.create_index("ix_preflight_checklist_templates_require_approval_before_run", "preflight_checklist_templates", ["require_approval_before_run"])
    op.create_index("ix_preflight_checklist_templates_is_active", "preflight_checklist_templates", ["is_active"])
    op.create_index("ix_preflight_checklist_templates_created_by", "preflight_checklist_templates", ["created_by"])
    op.create_index("ix_preflight_checklist_templates_created_at", "preflight_checklist_templates", ["created_at"])
    op.create_index("ix_preflight_checklist_templates_updated_at", "preflight_checklist_templates", ["updated_at"])
    op.create_index("ix_preflight_templates_tenant_id_id", "preflight_checklist_templates", ["tenant_id", "id"])

    op.create_table(
        "mission_preflight_checklists",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("mission_id", sa.String(), nullable=False),
        sa.Column("template_id", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=False, server_default="PENDING"),
        sa.Column("required_items", sa.JSON(), nullable=False),
        sa.Column("completed_items", sa.JSON(), nullable=False),
        sa.Column("evidence", sa.JSON(), nullable=False),
        sa.Column("updated_by", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "id", name="uq_mission_preflight_checklists_tenant_id_id"),
        sa.UniqueConstraint(
            "tenant_id",
            "mission_id",
            name="uq_mission_preflight_checklists_tenant_mission",
        ),
    )
    op.create_index("ix_mission_preflight_checklists_tenant_id", "mission_preflight_checklists", ["tenant_id"])
    op.create_index("ix_mission_preflight_checklists_mission_id", "mission_preflight_checklists", ["mission_id"])
    op.create_index("ix_mission_preflight_checklists_template_id", "mission_preflight_checklists", ["template_id"])
    op.create_index("ix_mission_preflight_checklists_status", "mission_preflight_checklists", ["status"])
    op.create_index("ix_mission_preflight_checklists_updated_by", "mission_preflight_checklists", ["updated_by"])
    op.create_index("ix_mission_preflight_checklists_created_at", "mission_preflight_checklists", ["created_at"])
    op.create_index("ix_mission_preflight_checklists_updated_at", "mission_preflight_checklists", ["updated_at"])
    op.create_index("ix_mission_preflight_checklists_completed_at", "mission_preflight_checklists", ["completed_at"])
    op.create_index("ix_mission_preflight_checklists_tenant_id_id", "mission_preflight_checklists", ["tenant_id", "id"])
    op.create_index(
        "ix_mission_preflight_checklists_tenant_mission",
        "mission_preflight_checklists",
        ["tenant_id", "mission_id"],
    )

    op.add_column("command_requests", sa.Column("compliance_passed", sa.Boolean(), nullable=True))
    op.add_column("command_requests", sa.Column("compliance_reason_code", sa.String(), nullable=True))
    op.add_column("command_requests", sa.Column("compliance_detail", sa.JSON(), nullable=True))
    op.create_index(
        "ix_command_requests_compliance_passed",
        "command_requests",
        ["compliance_passed"],
    )
    op.create_index(
        "ix_command_requests_compliance_reason_code",
        "command_requests",
        ["compliance_reason_code"],
    )
    op.create_index(
        "ix_command_requests_tenant_compliance",
        "command_requests",
        ["tenant_id", "compliance_passed"],
    )
    op.create_index(
        "ix_command_requests_tenant_reason",
        "command_requests",
        ["tenant_id", "compliance_reason_code"],
    )


def downgrade() -> None:
    op.drop_index("ix_command_requests_tenant_reason", table_name="command_requests")
    op.drop_index("ix_command_requests_tenant_compliance", table_name="command_requests")
    op.drop_index("ix_command_requests_compliance_reason_code", table_name="command_requests")
    op.drop_index("ix_command_requests_compliance_passed", table_name="command_requests")
    op.drop_column("command_requests", "compliance_detail")
    op.drop_column("command_requests", "compliance_reason_code")
    op.drop_column("command_requests", "compliance_passed")

    op.drop_index(
        "ix_mission_preflight_checklists_tenant_mission",
        table_name="mission_preflight_checklists",
    )
    op.drop_index(
        "ix_mission_preflight_checklists_tenant_id_id",
        table_name="mission_preflight_checklists",
    )
    op.drop_index("ix_mission_preflight_checklists_completed_at", table_name="mission_preflight_checklists")
    op.drop_index("ix_mission_preflight_checklists_updated_at", table_name="mission_preflight_checklists")
    op.drop_index("ix_mission_preflight_checklists_created_at", table_name="mission_preflight_checklists")
    op.drop_index("ix_mission_preflight_checklists_updated_by", table_name="mission_preflight_checklists")
    op.drop_index("ix_mission_preflight_checklists_status", table_name="mission_preflight_checklists")
    op.drop_index("ix_mission_preflight_checklists_template_id", table_name="mission_preflight_checklists")
    op.drop_index("ix_mission_preflight_checklists_mission_id", table_name="mission_preflight_checklists")
    op.drop_index("ix_mission_preflight_checklists_tenant_id", table_name="mission_preflight_checklists")
    op.drop_table("mission_preflight_checklists")

    op.drop_index("ix_preflight_templates_tenant_id_id", table_name="preflight_checklist_templates")
    op.drop_index("ix_preflight_checklist_templates_updated_at", table_name="preflight_checklist_templates")
    op.drop_index("ix_preflight_checklist_templates_created_at", table_name="preflight_checklist_templates")
    op.drop_index("ix_preflight_checklist_templates_created_by", table_name="preflight_checklist_templates")
    op.drop_index("ix_preflight_checklist_templates_is_active", table_name="preflight_checklist_templates")
    op.drop_index(
        "ix_preflight_checklist_templates_require_approval_before_run",
        table_name="preflight_checklist_templates",
    )
    op.drop_index("ix_preflight_checklist_templates_name", table_name="preflight_checklist_templates")
    op.drop_index("ix_preflight_checklist_templates_tenant_id", table_name="preflight_checklist_templates")
    op.drop_table("preflight_checklist_templates")

    op.drop_index("ix_airspace_zones_tenant_type", table_name="airspace_zones")
    op.drop_index("ix_airspace_zones_tenant_id_id", table_name="airspace_zones")
    op.drop_index("ix_airspace_zones_updated_at", table_name="airspace_zones")
    op.drop_index("ix_airspace_zones_created_at", table_name="airspace_zones")
    op.drop_index("ix_airspace_zones_created_by", table_name="airspace_zones")
    op.drop_index("ix_airspace_zones_is_active", table_name="airspace_zones")
    op.drop_index("ix_airspace_zones_area_code", table_name="airspace_zones")
    op.drop_index("ix_airspace_zones_zone_type", table_name="airspace_zones")
    op.drop_index("ix_airspace_zones_name", table_name="airspace_zones")
    op.drop_index("ix_airspace_zones_tenant_id", table_name="airspace_zones")
    op.drop_table("airspace_zones")
