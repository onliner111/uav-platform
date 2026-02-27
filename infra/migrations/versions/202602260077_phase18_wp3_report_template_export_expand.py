"""phase18 wp3 report template export expand

Revision ID: 202602260077
Revises: 202602260076
Create Date: 2026-02-26
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "202602260077"
down_revision = "202602260076"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "outcome_report_templates",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column(
            "format_default",
            sa.String(length=10),
            nullable=False,
            server_default="PDF",
        ),
        sa.Column("title_template", sa.Text(), nullable=False),
        sa.Column("body_template", sa.Text(), nullable=False),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column("created_by", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "id", name="uq_outcome_report_templates_tenant_id_id"),
        sa.UniqueConstraint("tenant_id", "name", name="uq_outcome_report_templates_tenant_name"),
    )
    op.create_index("ix_outcome_report_templates_tenant_id", "outcome_report_templates", ["tenant_id"])
    op.create_index("ix_outcome_report_templates_name", "outcome_report_templates", ["name"])
    op.create_index("ix_outcome_report_templates_format_default", "outcome_report_templates", ["format_default"])
    op.create_index("ix_outcome_report_templates_is_active", "outcome_report_templates", ["is_active"])
    op.create_index("ix_outcome_report_templates_created_by", "outcome_report_templates", ["created_by"])
    op.create_index("ix_outcome_report_templates_created_at", "outcome_report_templates", ["created_at"])
    op.create_index("ix_outcome_report_templates_updated_at", "outcome_report_templates", ["updated_at"])
    op.create_index(
        "ix_outcome_report_templates_tenant_id_id",
        "outcome_report_templates",
        ["tenant_id", "id"],
    )
    op.create_index(
        "ix_outcome_report_templates_tenant_active",
        "outcome_report_templates",
        ["tenant_id", "is_active"],
    )

    op.create_table(
        "outcome_report_exports",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("template_id", sa.String(), nullable=False),
        sa.Column(
            "report_format",
            sa.String(length=10),
            nullable=False,
            server_default="PDF",
        ),
        sa.Column(
            "status",
            sa.String(length=20),
            nullable=False,
            server_default="RUNNING",
        ),
        sa.Column("task_id", sa.String(), nullable=True),
        sa.Column("from_ts", sa.DateTime(timezone=True), nullable=True),
        sa.Column("to_ts", sa.DateTime(timezone=True), nullable=True),
        sa.Column("topic", sa.String(length=120), nullable=True),
        sa.Column("file_path", sa.Text(), nullable=True),
        sa.Column(
            "detail",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'{}'::json"),
        ),
        sa.Column("requested_by", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["tenant_id", "task_id"],
            ["inspection_tasks.tenant_id", "inspection_tasks.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(["template_id"], ["outcome_report_templates.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "id", name="uq_outcome_report_exports_tenant_id_id"),
    )
    op.create_index("ix_outcome_report_exports_tenant_id", "outcome_report_exports", ["tenant_id"])
    op.create_index("ix_outcome_report_exports_template_id", "outcome_report_exports", ["template_id"])
    op.create_index("ix_outcome_report_exports_report_format", "outcome_report_exports", ["report_format"])
    op.create_index("ix_outcome_report_exports_status", "outcome_report_exports", ["status"])
    op.create_index("ix_outcome_report_exports_task_id", "outcome_report_exports", ["task_id"])
    op.create_index("ix_outcome_report_exports_topic", "outcome_report_exports", ["topic"])
    op.create_index("ix_outcome_report_exports_requested_by", "outcome_report_exports", ["requested_by"])
    op.create_index("ix_outcome_report_exports_created_at", "outcome_report_exports", ["created_at"])
    op.create_index("ix_outcome_report_exports_updated_at", "outcome_report_exports", ["updated_at"])
    op.create_index("ix_outcome_report_exports_completed_at", "outcome_report_exports", ["completed_at"])
    op.create_index(
        "ix_outcome_report_exports_tenant_id_id",
        "outcome_report_exports",
        ["tenant_id", "id"],
    )
    op.create_index(
        "ix_outcome_report_exports_tenant_template",
        "outcome_report_exports",
        ["tenant_id", "template_id"],
    )
    op.create_index(
        "ix_outcome_report_exports_tenant_status",
        "outcome_report_exports",
        ["tenant_id", "status"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_outcome_report_exports_tenant_status",
        table_name="outcome_report_exports",
    )
    op.drop_index(
        "ix_outcome_report_exports_tenant_template",
        table_name="outcome_report_exports",
    )
    op.drop_index(
        "ix_outcome_report_exports_tenant_id_id",
        table_name="outcome_report_exports",
    )
    op.drop_index("ix_outcome_report_exports_completed_at", table_name="outcome_report_exports")
    op.drop_index("ix_outcome_report_exports_updated_at", table_name="outcome_report_exports")
    op.drop_index("ix_outcome_report_exports_created_at", table_name="outcome_report_exports")
    op.drop_index("ix_outcome_report_exports_requested_by", table_name="outcome_report_exports")
    op.drop_index("ix_outcome_report_exports_topic", table_name="outcome_report_exports")
    op.drop_index("ix_outcome_report_exports_task_id", table_name="outcome_report_exports")
    op.drop_index("ix_outcome_report_exports_status", table_name="outcome_report_exports")
    op.drop_index("ix_outcome_report_exports_report_format", table_name="outcome_report_exports")
    op.drop_index("ix_outcome_report_exports_template_id", table_name="outcome_report_exports")
    op.drop_index("ix_outcome_report_exports_tenant_id", table_name="outcome_report_exports")
    op.drop_table("outcome_report_exports")

    op.drop_index(
        "ix_outcome_report_templates_tenant_active",
        table_name="outcome_report_templates",
    )
    op.drop_index(
        "ix_outcome_report_templates_tenant_id_id",
        table_name="outcome_report_templates",
    )
    op.drop_index("ix_outcome_report_templates_updated_at", table_name="outcome_report_templates")
    op.drop_index("ix_outcome_report_templates_created_at", table_name="outcome_report_templates")
    op.drop_index("ix_outcome_report_templates_created_by", table_name="outcome_report_templates")
    op.drop_index("ix_outcome_report_templates_is_active", table_name="outcome_report_templates")
    op.drop_index("ix_outcome_report_templates_format_default", table_name="outcome_report_templates")
    op.drop_index("ix_outcome_report_templates_name", table_name="outcome_report_templates")
    op.drop_index("ix_outcome_report_templates_tenant_id", table_name="outcome_report_templates")
    op.drop_table("outcome_report_templates")
