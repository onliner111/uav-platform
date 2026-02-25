"""phase11 task center p0 expand

Revision ID: 202602240044
Revises: 202602240043
Create Date: 2026-02-25
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "202602240044"
down_revision = "202602240043"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "task_type_catalogs",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_by", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "id", name="uq_task_type_catalogs_tenant_id_id"),
        sa.UniqueConstraint("tenant_id", "code", name="uq_task_type_catalogs_tenant_code"),
    )
    op.create_index("ix_task_type_catalogs_tenant_id", "task_type_catalogs", ["tenant_id"])
    op.create_index("ix_task_type_catalogs_code", "task_type_catalogs", ["code"])
    op.create_index("ix_task_type_catalogs_name", "task_type_catalogs", ["name"])
    op.create_index("ix_task_type_catalogs_is_active", "task_type_catalogs", ["is_active"])
    op.create_index("ix_task_type_catalogs_created_by", "task_type_catalogs", ["created_by"])
    op.create_index("ix_task_type_catalogs_created_at", "task_type_catalogs", ["created_at"])
    op.create_index("ix_task_type_catalogs_updated_at", "task_type_catalogs", ["updated_at"])
    op.create_index("ix_task_type_catalogs_tenant_id_id", "task_type_catalogs", ["tenant_id", "id"])
    op.create_index("ix_task_type_catalogs_tenant_code", "task_type_catalogs", ["tenant_id", "code"])

    op.create_table(
        "task_templates",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("task_type_id", sa.String(), nullable=False),
        sa.Column("template_key", sa.String(length=100), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("requires_approval", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("default_priority", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("default_risk_level", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("default_checklist", sa.JSON(), nullable=False),
        sa.Column("default_payload", sa.JSON(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_by", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "id", name="uq_task_templates_tenant_id_id"),
        sa.UniqueConstraint("tenant_id", "template_key", name="uq_task_templates_tenant_template_key"),
    )
    op.create_index("ix_task_templates_tenant_id", "task_templates", ["tenant_id"])
    op.create_index("ix_task_templates_task_type_id", "task_templates", ["task_type_id"])
    op.create_index("ix_task_templates_template_key", "task_templates", ["template_key"])
    op.create_index("ix_task_templates_name", "task_templates", ["name"])
    op.create_index("ix_task_templates_requires_approval", "task_templates", ["requires_approval"])
    op.create_index("ix_task_templates_default_priority", "task_templates", ["default_priority"])
    op.create_index("ix_task_templates_default_risk_level", "task_templates", ["default_risk_level"])
    op.create_index("ix_task_templates_is_active", "task_templates", ["is_active"])
    op.create_index("ix_task_templates_created_by", "task_templates", ["created_by"])
    op.create_index("ix_task_templates_created_at", "task_templates", ["created_at"])
    op.create_index("ix_task_templates_updated_at", "task_templates", ["updated_at"])
    op.create_index("ix_task_templates_tenant_id_id", "task_templates", ["tenant_id", "id"])
    op.create_index("ix_task_templates_tenant_type", "task_templates", ["tenant_id", "task_type_id"])

    op.create_table(
        "task_center_tasks",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("task_type_id", sa.String(), nullable=False),
        sa.Column("template_id", sa.String(), nullable=True),
        sa.Column("mission_id", sa.String(), nullable=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("state", sa.String(length=30), nullable=False, server_default="DRAFT"),
        sa.Column("requires_approval", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("risk_level", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("org_unit_id", sa.String(), nullable=True),
        sa.Column("project_code", sa.String(length=100), nullable=True),
        sa.Column("area_code", sa.String(length=100), nullable=True),
        sa.Column("area_geom", sa.Text(), nullable=False, server_default=""),
        sa.Column("checklist", sa.JSON(), nullable=False),
        sa.Column("attachments", sa.JSON(), nullable=False),
        sa.Column("context_data", sa.JSON(), nullable=False),
        sa.Column("dispatch_mode", sa.String(length=20), nullable=True),
        sa.Column("assigned_to", sa.String(), nullable=True),
        sa.Column("dispatched_by", sa.String(), nullable=True),
        sa.Column("dispatched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("canceled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "id", name="uq_task_center_tasks_tenant_id_id"),
    )
    op.create_index("ix_task_center_tasks_tenant_id", "task_center_tasks", ["tenant_id"])
    op.create_index("ix_task_center_tasks_task_type_id", "task_center_tasks", ["task_type_id"])
    op.create_index("ix_task_center_tasks_template_id", "task_center_tasks", ["template_id"])
    op.create_index("ix_task_center_tasks_mission_id", "task_center_tasks", ["mission_id"])
    op.create_index("ix_task_center_tasks_name", "task_center_tasks", ["name"])
    op.create_index("ix_task_center_tasks_state", "task_center_tasks", ["state"])
    op.create_index("ix_task_center_tasks_requires_approval", "task_center_tasks", ["requires_approval"])
    op.create_index("ix_task_center_tasks_priority", "task_center_tasks", ["priority"])
    op.create_index("ix_task_center_tasks_risk_level", "task_center_tasks", ["risk_level"])
    op.create_index("ix_task_center_tasks_org_unit_id", "task_center_tasks", ["org_unit_id"])
    op.create_index("ix_task_center_tasks_project_code", "task_center_tasks", ["project_code"])
    op.create_index("ix_task_center_tasks_area_code", "task_center_tasks", ["area_code"])
    op.create_index("ix_task_center_tasks_dispatch_mode", "task_center_tasks", ["dispatch_mode"])
    op.create_index("ix_task_center_tasks_assigned_to", "task_center_tasks", ["assigned_to"])
    op.create_index("ix_task_center_tasks_dispatched_by", "task_center_tasks", ["dispatched_by"])
    op.create_index("ix_task_center_tasks_dispatched_at", "task_center_tasks", ["dispatched_at"])
    op.create_index("ix_task_center_tasks_started_at", "task_center_tasks", ["started_at"])
    op.create_index("ix_task_center_tasks_accepted_at", "task_center_tasks", ["accepted_at"])
    op.create_index("ix_task_center_tasks_archived_at", "task_center_tasks", ["archived_at"])
    op.create_index("ix_task_center_tasks_canceled_at", "task_center_tasks", ["canceled_at"])
    op.create_index("ix_task_center_tasks_created_by", "task_center_tasks", ["created_by"])
    op.create_index("ix_task_center_tasks_created_at", "task_center_tasks", ["created_at"])
    op.create_index("ix_task_center_tasks_updated_at", "task_center_tasks", ["updated_at"])
    op.create_index("ix_task_center_tasks_tenant_id_id", "task_center_tasks", ["tenant_id", "id"])
    op.create_index("ix_task_center_tasks_tenant_state", "task_center_tasks", ["tenant_id", "state"])
    op.create_index("ix_task_center_tasks_tenant_assigned", "task_center_tasks", ["tenant_id", "assigned_to"])
    op.create_index("ix_task_center_tasks_tenant_org_unit", "task_center_tasks", ["tenant_id", "org_unit_id"])
    op.create_index("ix_task_center_tasks_tenant_task_type", "task_center_tasks", ["tenant_id", "task_type_id"])

    op.create_table(
        "task_center_task_histories",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("task_id", sa.String(), nullable=False),
        sa.Column("action", sa.String(length=50), nullable=False),
        sa.Column("from_state", sa.String(length=30), nullable=True),
        sa.Column("to_state", sa.String(length=30), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("actor_id", sa.String(), nullable=True),
        sa.Column("detail", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "id", name="uq_task_center_task_histories_tenant_id_id"),
    )
    op.create_index("ix_task_center_task_histories_tenant_id", "task_center_task_histories", ["tenant_id"])
    op.create_index("ix_task_center_task_histories_task_id", "task_center_task_histories", ["task_id"])
    op.create_index("ix_task_center_task_histories_action", "task_center_task_histories", ["action"])
    op.create_index("ix_task_center_task_histories_from_state", "task_center_task_histories", ["from_state"])
    op.create_index("ix_task_center_task_histories_to_state", "task_center_task_histories", ["to_state"])
    op.create_index("ix_task_center_task_histories_actor_id", "task_center_task_histories", ["actor_id"])
    op.create_index("ix_task_center_task_histories_created_at", "task_center_task_histories", ["created_at"])
    op.create_index(
        "ix_task_center_task_histories_tenant_id_id",
        "task_center_task_histories",
        ["tenant_id", "id"],
    )
    op.create_index(
        "ix_task_center_task_histories_tenant_task",
        "task_center_task_histories",
        ["tenant_id", "task_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_task_center_task_histories_tenant_task", table_name="task_center_task_histories")
    op.drop_index("ix_task_center_task_histories_tenant_id_id", table_name="task_center_task_histories")
    op.drop_index("ix_task_center_task_histories_created_at", table_name="task_center_task_histories")
    op.drop_index("ix_task_center_task_histories_actor_id", table_name="task_center_task_histories")
    op.drop_index("ix_task_center_task_histories_to_state", table_name="task_center_task_histories")
    op.drop_index("ix_task_center_task_histories_from_state", table_name="task_center_task_histories")
    op.drop_index("ix_task_center_task_histories_action", table_name="task_center_task_histories")
    op.drop_index("ix_task_center_task_histories_task_id", table_name="task_center_task_histories")
    op.drop_index("ix_task_center_task_histories_tenant_id", table_name="task_center_task_histories")
    op.drop_table("task_center_task_histories")

    op.drop_index("ix_task_center_tasks_tenant_task_type", table_name="task_center_tasks")
    op.drop_index("ix_task_center_tasks_tenant_org_unit", table_name="task_center_tasks")
    op.drop_index("ix_task_center_tasks_tenant_assigned", table_name="task_center_tasks")
    op.drop_index("ix_task_center_tasks_tenant_state", table_name="task_center_tasks")
    op.drop_index("ix_task_center_tasks_tenant_id_id", table_name="task_center_tasks")
    op.drop_index("ix_task_center_tasks_updated_at", table_name="task_center_tasks")
    op.drop_index("ix_task_center_tasks_created_at", table_name="task_center_tasks")
    op.drop_index("ix_task_center_tasks_created_by", table_name="task_center_tasks")
    op.drop_index("ix_task_center_tasks_canceled_at", table_name="task_center_tasks")
    op.drop_index("ix_task_center_tasks_archived_at", table_name="task_center_tasks")
    op.drop_index("ix_task_center_tasks_accepted_at", table_name="task_center_tasks")
    op.drop_index("ix_task_center_tasks_started_at", table_name="task_center_tasks")
    op.drop_index("ix_task_center_tasks_dispatched_at", table_name="task_center_tasks")
    op.drop_index("ix_task_center_tasks_dispatched_by", table_name="task_center_tasks")
    op.drop_index("ix_task_center_tasks_assigned_to", table_name="task_center_tasks")
    op.drop_index("ix_task_center_tasks_dispatch_mode", table_name="task_center_tasks")
    op.drop_index("ix_task_center_tasks_area_code", table_name="task_center_tasks")
    op.drop_index("ix_task_center_tasks_project_code", table_name="task_center_tasks")
    op.drop_index("ix_task_center_tasks_org_unit_id", table_name="task_center_tasks")
    op.drop_index("ix_task_center_tasks_risk_level", table_name="task_center_tasks")
    op.drop_index("ix_task_center_tasks_priority", table_name="task_center_tasks")
    op.drop_index("ix_task_center_tasks_requires_approval", table_name="task_center_tasks")
    op.drop_index("ix_task_center_tasks_state", table_name="task_center_tasks")
    op.drop_index("ix_task_center_tasks_name", table_name="task_center_tasks")
    op.drop_index("ix_task_center_tasks_mission_id", table_name="task_center_tasks")
    op.drop_index("ix_task_center_tasks_template_id", table_name="task_center_tasks")
    op.drop_index("ix_task_center_tasks_task_type_id", table_name="task_center_tasks")
    op.drop_index("ix_task_center_tasks_tenant_id", table_name="task_center_tasks")
    op.drop_table("task_center_tasks")

    op.drop_index("ix_task_templates_tenant_type", table_name="task_templates")
    op.drop_index("ix_task_templates_tenant_id_id", table_name="task_templates")
    op.drop_index("ix_task_templates_updated_at", table_name="task_templates")
    op.drop_index("ix_task_templates_created_at", table_name="task_templates")
    op.drop_index("ix_task_templates_created_by", table_name="task_templates")
    op.drop_index("ix_task_templates_is_active", table_name="task_templates")
    op.drop_index("ix_task_templates_default_risk_level", table_name="task_templates")
    op.drop_index("ix_task_templates_default_priority", table_name="task_templates")
    op.drop_index("ix_task_templates_requires_approval", table_name="task_templates")
    op.drop_index("ix_task_templates_name", table_name="task_templates")
    op.drop_index("ix_task_templates_template_key", table_name="task_templates")
    op.drop_index("ix_task_templates_task_type_id", table_name="task_templates")
    op.drop_index("ix_task_templates_tenant_id", table_name="task_templates")
    op.drop_table("task_templates")

    op.drop_index("ix_task_type_catalogs_tenant_code", table_name="task_type_catalogs")
    op.drop_index("ix_task_type_catalogs_tenant_id_id", table_name="task_type_catalogs")
    op.drop_index("ix_task_type_catalogs_updated_at", table_name="task_type_catalogs")
    op.drop_index("ix_task_type_catalogs_created_at", table_name="task_type_catalogs")
    op.drop_index("ix_task_type_catalogs_created_by", table_name="task_type_catalogs")
    op.drop_index("ix_task_type_catalogs_is_active", table_name="task_type_catalogs")
    op.drop_index("ix_task_type_catalogs_name", table_name="task_type_catalogs")
    op.drop_index("ix_task_type_catalogs_code", table_name="task_type_catalogs")
    op.drop_index("ix_task_type_catalogs_tenant_id", table_name="task_type_catalogs")
    op.drop_table("task_type_catalogs")
