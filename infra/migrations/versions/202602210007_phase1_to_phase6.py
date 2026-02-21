"""inspection, defect, emergency, compliance and reporting tables

Revision ID: 202602210007
Revises: 202602190006
Create Date: 2026-02-21
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "202602210007"
down_revision = "202602190006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "inspection_templates",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("category", sa.String(length=50), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_inspection_templates_tenant_id", "inspection_templates", ["tenant_id"])
    op.create_index("ix_inspection_templates_name", "inspection_templates", ["name"])
    op.create_index("ix_inspection_templates_category", "inspection_templates", ["category"])
    op.create_index("ix_inspection_templates_is_active", "inspection_templates", ["is_active"])
    op.create_index("ix_inspection_templates_created_at", "inspection_templates", ["created_at"])

    op.create_table(
        "inspection_template_items",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("template_id", sa.String(), nullable=False),
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("title", sa.String(length=100), nullable=False),
        sa.Column("severity_default", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("required", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["template_id"], ["inspection_templates.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_inspection_template_items_tenant_id", "inspection_template_items", ["tenant_id"])
    op.create_index("ix_inspection_template_items_template_id", "inspection_template_items", ["template_id"])
    op.create_index("ix_inspection_template_items_code", "inspection_template_items", ["code"])
    op.create_index("ix_inspection_template_items_created_at", "inspection_template_items", ["created_at"])

    op.create_table(
        "inspection_tasks",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("template_id", sa.String(), nullable=False),
        sa.Column("mission_id", sa.String(), nullable=True),
        sa.Column("area_geom", sa.Text(), nullable=False, server_default=""),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="DRAFT"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["template_id"], ["inspection_templates.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["mission_id"], ["missions.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_inspection_tasks_tenant_id", "inspection_tasks", ["tenant_id"])
    op.create_index("ix_inspection_tasks_name", "inspection_tasks", ["name"])
    op.create_index("ix_inspection_tasks_template_id", "inspection_tasks", ["template_id"])
    op.create_index("ix_inspection_tasks_mission_id", "inspection_tasks", ["mission_id"])
    op.create_index("ix_inspection_tasks_priority", "inspection_tasks", ["priority"])
    op.create_index("ix_inspection_tasks_status", "inspection_tasks", ["status"])
    op.create_index("ix_inspection_tasks_created_at", "inspection_tasks", ["created_at"])

    op.create_table(
        "inspection_observations",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("task_id", sa.String(), nullable=False),
        sa.Column("drone_id", sa.String(), nullable=True),
        sa.Column("ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("position_lat", sa.Float(), nullable=False),
        sa.Column("position_lon", sa.Float(), nullable=False),
        sa.Column("alt_m", sa.Float(), nullable=False),
        sa.Column("item_code", sa.String(length=50), nullable=False),
        sa.Column("severity", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("note", sa.Text(), nullable=False, server_default=""),
        sa.Column("media_url", sa.Text(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["task_id"], ["inspection_tasks.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["drone_id"], ["drones.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_inspection_observations_tenant_id", "inspection_observations", ["tenant_id"])
    op.create_index("ix_inspection_observations_task_id", "inspection_observations", ["task_id"])
    op.create_index("ix_inspection_observations_drone_id", "inspection_observations", ["drone_id"])
    op.create_index("ix_inspection_observations_ts", "inspection_observations", ["ts"])
    op.create_index("ix_inspection_observations_item_code", "inspection_observations", ["item_code"])
    op.create_index("ix_inspection_observations_created_at", "inspection_observations", ["created_at"])

    op.create_table(
        "inspection_exports",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("task_id", sa.String(), nullable=False),
        sa.Column("format", sa.String(length=10), nullable=False),
        sa.Column("file_path", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["task_id"], ["inspection_tasks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_inspection_exports_tenant_id", "inspection_exports", ["tenant_id"])
    op.create_index("ix_inspection_exports_task_id", "inspection_exports", ["task_id"])
    op.create_index("ix_inspection_exports_format", "inspection_exports", ["format"])
    op.create_index("ix_inspection_exports_created_at", "inspection_exports", ["created_at"])

    op.create_table(
        "defects",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("observation_id", sa.String(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("severity", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="OPEN"),
        sa.Column("assigned_to", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["observation_id"], ["inspection_observations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_defects_tenant_id", "defects", ["tenant_id"])
    op.create_index("ix_defects_observation_id", "defects", ["observation_id"])
    op.create_index("ix_defects_status", "defects", ["status"])
    op.create_index("ix_defects_assigned_to", "defects", ["assigned_to"])
    op.create_index("ix_defects_created_at", "defects", ["created_at"])

    op.create_table(
        "defect_actions",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("defect_id", sa.String(), nullable=False),
        sa.Column("action_type", sa.String(length=50), nullable=False),
        sa.Column("note", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["defect_id"], ["defects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_defect_actions_tenant_id", "defect_actions", ["tenant_id"])
    op.create_index("ix_defect_actions_defect_id", "defect_actions", ["defect_id"])
    op.create_index("ix_defect_actions_action_type", "defect_actions", ["action_type"])
    op.create_index("ix_defect_actions_created_at", "defect_actions", ["created_at"])

    op.create_table(
        "incidents",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("level", sa.String(length=20), nullable=False),
        sa.Column("location_geom", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="OPEN"),
        sa.Column("linked_task_id", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["linked_task_id"], ["inspection_tasks.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_incidents_tenant_id", "incidents", ["tenant_id"])
    op.create_index("ix_incidents_level", "incidents", ["level"])
    op.create_index("ix_incidents_status", "incidents", ["status"])
    op.create_index("ix_incidents_linked_task_id", "incidents", ["linked_task_id"])
    op.create_index("ix_incidents_created_at", "incidents", ["created_at"])

    op.create_table(
        "approval_records",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("entity_type", sa.String(length=50), nullable=False),
        sa.Column("entity_id", sa.String(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("approved_by", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_approval_records_tenant_id", "approval_records", ["tenant_id"])
    op.create_index("ix_approval_records_entity_type", "approval_records", ["entity_type"])
    op.create_index("ix_approval_records_entity_id", "approval_records", ["entity_id"])
    op.create_index("ix_approval_records_status", "approval_records", ["status"])
    op.create_index("ix_approval_records_approved_by", "approval_records", ["approved_by"])
    op.create_index("ix_approval_records_created_at", "approval_records", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_approval_records_created_at", table_name="approval_records")
    op.drop_index("ix_approval_records_approved_by", table_name="approval_records")
    op.drop_index("ix_approval_records_status", table_name="approval_records")
    op.drop_index("ix_approval_records_entity_id", table_name="approval_records")
    op.drop_index("ix_approval_records_entity_type", table_name="approval_records")
    op.drop_index("ix_approval_records_tenant_id", table_name="approval_records")
    op.drop_table("approval_records")

    op.drop_index("ix_incidents_created_at", table_name="incidents")
    op.drop_index("ix_incidents_linked_task_id", table_name="incidents")
    op.drop_index("ix_incidents_status", table_name="incidents")
    op.drop_index("ix_incidents_level", table_name="incidents")
    op.drop_index("ix_incidents_tenant_id", table_name="incidents")
    op.drop_table("incidents")

    op.drop_index("ix_defect_actions_created_at", table_name="defect_actions")
    op.drop_index("ix_defect_actions_action_type", table_name="defect_actions")
    op.drop_index("ix_defect_actions_defect_id", table_name="defect_actions")
    op.drop_index("ix_defect_actions_tenant_id", table_name="defect_actions")
    op.drop_table("defect_actions")

    op.drop_index("ix_defects_created_at", table_name="defects")
    op.drop_index("ix_defects_assigned_to", table_name="defects")
    op.drop_index("ix_defects_status", table_name="defects")
    op.drop_index("ix_defects_observation_id", table_name="defects")
    op.drop_index("ix_defects_tenant_id", table_name="defects")
    op.drop_table("defects")

    op.drop_index("ix_inspection_exports_created_at", table_name="inspection_exports")
    op.drop_index("ix_inspection_exports_format", table_name="inspection_exports")
    op.drop_index("ix_inspection_exports_task_id", table_name="inspection_exports")
    op.drop_index("ix_inspection_exports_tenant_id", table_name="inspection_exports")
    op.drop_table("inspection_exports")

    op.drop_index("ix_inspection_observations_created_at", table_name="inspection_observations")
    op.drop_index("ix_inspection_observations_item_code", table_name="inspection_observations")
    op.drop_index("ix_inspection_observations_ts", table_name="inspection_observations")
    op.drop_index("ix_inspection_observations_drone_id", table_name="inspection_observations")
    op.drop_index("ix_inspection_observations_task_id", table_name="inspection_observations")
    op.drop_index("ix_inspection_observations_tenant_id", table_name="inspection_observations")
    op.drop_table("inspection_observations")

    op.drop_index("ix_inspection_tasks_created_at", table_name="inspection_tasks")
    op.drop_index("ix_inspection_tasks_status", table_name="inspection_tasks")
    op.drop_index("ix_inspection_tasks_priority", table_name="inspection_tasks")
    op.drop_index("ix_inspection_tasks_mission_id", table_name="inspection_tasks")
    op.drop_index("ix_inspection_tasks_template_id", table_name="inspection_tasks")
    op.drop_index("ix_inspection_tasks_name", table_name="inspection_tasks")
    op.drop_index("ix_inspection_tasks_tenant_id", table_name="inspection_tasks")
    op.drop_table("inspection_tasks")

    op.drop_index("ix_inspection_template_items_created_at", table_name="inspection_template_items")
    op.drop_index("ix_inspection_template_items_code", table_name="inspection_template_items")
    op.drop_index("ix_inspection_template_items_template_id", table_name="inspection_template_items")
    op.drop_index("ix_inspection_template_items_tenant_id", table_name="inspection_template_items")
    op.drop_table("inspection_template_items")

    op.drop_index("ix_inspection_templates_created_at", table_name="inspection_templates")
    op.drop_index("ix_inspection_templates_is_active", table_name="inspection_templates")
    op.drop_index("ix_inspection_templates_category", table_name="inspection_templates")
    op.drop_index("ix_inspection_templates_name", table_name="inspection_templates")
    op.drop_index("ix_inspection_templates_tenant_id", table_name="inspection_templates")
    op.drop_table("inspection_templates")
