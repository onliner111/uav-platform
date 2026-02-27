"""phase22 wp1 alert oncall expand

Revision ID: 202602270086
Revises: 202602270085
Create Date: 2026-02-27
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "202602270086"
down_revision = "202602270085"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "alert_oncall_shifts",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("shift_name", sa.String(length=100), nullable=False),
        sa.Column("target", sa.String(length=200), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("timezone", sa.String(length=64), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("detail", sa.JSON(), nullable=False),
        sa.Column("created_by", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "id", name="uq_alert_oncall_shifts_tenant_id_id"),
    )
    op.create_index("ix_alert_oncall_shifts_tenant_id", "alert_oncall_shifts", ["tenant_id"])
    op.create_index("ix_alert_oncall_shifts_shift_name", "alert_oncall_shifts", ["shift_name"])
    op.create_index("ix_alert_oncall_shifts_target", "alert_oncall_shifts", ["target"])
    op.create_index("ix_alert_oncall_shifts_starts_at", "alert_oncall_shifts", ["starts_at"])
    op.create_index("ix_alert_oncall_shifts_ends_at", "alert_oncall_shifts", ["ends_at"])
    op.create_index("ix_alert_oncall_shifts_is_active", "alert_oncall_shifts", ["is_active"])
    op.create_index("ix_alert_oncall_shifts_created_by", "alert_oncall_shifts", ["created_by"])
    op.create_index("ix_alert_oncall_shifts_created_at", "alert_oncall_shifts", ["created_at"])
    op.create_index("ix_alert_oncall_shifts_updated_at", "alert_oncall_shifts", ["updated_at"])
    op.create_index("ix_alert_oncall_shifts_tenant_id_id", "alert_oncall_shifts", ["tenant_id", "id"])
    op.create_index(
        "ix_alert_oncall_shifts_tenant_window",
        "alert_oncall_shifts",
        ["tenant_id", "starts_at", "ends_at"],
    )
    op.create_index(
        "ix_alert_oncall_shifts_tenant_active",
        "alert_oncall_shifts",
        ["tenant_id", "is_active"],
    )

    op.create_table(
        "alert_escalation_policies",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("priority_level", sa.String(length=10), nullable=False),
        sa.Column("ack_timeout_seconds", sa.Integer(), nullable=False),
        sa.Column("repeat_threshold", sa.Integer(), nullable=False),
        sa.Column("max_escalation_level", sa.Integer(), nullable=False),
        sa.Column("escalation_channel", sa.String(length=20), nullable=False),
        sa.Column("escalation_target", sa.String(length=200), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("detail", sa.JSON(), nullable=False),
        sa.Column("created_by", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "id", name="uq_alert_escalation_policies_tenant_id_id"),
        sa.UniqueConstraint(
            "tenant_id",
            "priority_level",
            name="uq_alert_escalation_policies_tenant_priority",
        ),
    )
    op.create_index("ix_alert_escalation_policies_tenant_id", "alert_escalation_policies", ["tenant_id"])
    op.create_index(
        "ix_alert_escalation_policies_priority_level",
        "alert_escalation_policies",
        ["priority_level"],
    )
    op.create_index(
        "ix_alert_escalation_policies_escalation_channel",
        "alert_escalation_policies",
        ["escalation_channel"],
    )
    op.create_index("ix_alert_escalation_policies_is_active", "alert_escalation_policies", ["is_active"])
    op.create_index("ix_alert_escalation_policies_created_by", "alert_escalation_policies", ["created_by"])
    op.create_index("ix_alert_escalation_policies_created_at", "alert_escalation_policies", ["created_at"])
    op.create_index("ix_alert_escalation_policies_updated_at", "alert_escalation_policies", ["updated_at"])
    op.create_index(
        "ix_alert_escalation_policies_tenant_id_id",
        "alert_escalation_policies",
        ["tenant_id", "id"],
    )
    op.create_index(
        "ix_alert_escalation_policies_tenant_priority",
        "alert_escalation_policies",
        ["tenant_id", "priority_level"],
    )
    op.create_index(
        "ix_alert_escalation_policies_tenant_active",
        "alert_escalation_policies",
        ["tenant_id", "is_active"],
    )

    op.create_table(
        "alert_escalation_executions",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("alert_id", sa.String(), nullable=False),
        sa.Column("reason", sa.String(length=20), nullable=False),
        sa.Column("escalation_level", sa.Integer(), nullable=False),
        sa.Column("channel", sa.String(length=20), nullable=False),
        sa.Column("from_target", sa.String(length=200), nullable=True),
        sa.Column("to_target", sa.String(length=200), nullable=False),
        sa.Column("detail", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "id", name="uq_alert_escalation_executions_tenant_id_id"),
    )
    op.create_index("ix_alert_escalation_executions_tenant_id", "alert_escalation_executions", ["tenant_id"])
    op.create_index("ix_alert_escalation_executions_alert_id", "alert_escalation_executions", ["alert_id"])
    op.create_index("ix_alert_escalation_executions_reason", "alert_escalation_executions", ["reason"])
    op.create_index("ix_alert_escalation_executions_channel", "alert_escalation_executions", ["channel"])
    op.create_index(
        "ix_alert_escalation_executions_escalation_level",
        "alert_escalation_executions",
        ["escalation_level"],
    )
    op.create_index("ix_alert_escalation_executions_created_at", "alert_escalation_executions", ["created_at"])
    op.create_index(
        "ix_alert_escalation_executions_tenant_id_id",
        "alert_escalation_executions",
        ["tenant_id", "id"],
    )
    op.create_index(
        "ix_alert_escalation_executions_tenant_alert",
        "alert_escalation_executions",
        ["tenant_id", "alert_id"],
    )
    op.create_index(
        "ix_alert_escalation_executions_tenant_reason",
        "alert_escalation_executions",
        ["tenant_id", "reason"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_alert_escalation_executions_tenant_reason",
        table_name="alert_escalation_executions",
    )
    op.drop_index(
        "ix_alert_escalation_executions_tenant_alert",
        table_name="alert_escalation_executions",
    )
    op.drop_index(
        "ix_alert_escalation_executions_tenant_id_id",
        table_name="alert_escalation_executions",
    )
    op.drop_index("ix_alert_escalation_executions_created_at", table_name="alert_escalation_executions")
    op.drop_index(
        "ix_alert_escalation_executions_escalation_level",
        table_name="alert_escalation_executions",
    )
    op.drop_index("ix_alert_escalation_executions_channel", table_name="alert_escalation_executions")
    op.drop_index("ix_alert_escalation_executions_reason", table_name="alert_escalation_executions")
    op.drop_index("ix_alert_escalation_executions_alert_id", table_name="alert_escalation_executions")
    op.drop_index("ix_alert_escalation_executions_tenant_id", table_name="alert_escalation_executions")
    op.drop_table("alert_escalation_executions")

    op.drop_index(
        "ix_alert_escalation_policies_tenant_active",
        table_name="alert_escalation_policies",
    )
    op.drop_index(
        "ix_alert_escalation_policies_tenant_priority",
        table_name="alert_escalation_policies",
    )
    op.drop_index(
        "ix_alert_escalation_policies_tenant_id_id",
        table_name="alert_escalation_policies",
    )
    op.drop_index("ix_alert_escalation_policies_updated_at", table_name="alert_escalation_policies")
    op.drop_index("ix_alert_escalation_policies_created_at", table_name="alert_escalation_policies")
    op.drop_index("ix_alert_escalation_policies_created_by", table_name="alert_escalation_policies")
    op.drop_index("ix_alert_escalation_policies_is_active", table_name="alert_escalation_policies")
    op.drop_index(
        "ix_alert_escalation_policies_escalation_channel",
        table_name="alert_escalation_policies",
    )
    op.drop_index(
        "ix_alert_escalation_policies_priority_level",
        table_name="alert_escalation_policies",
    )
    op.drop_index("ix_alert_escalation_policies_tenant_id", table_name="alert_escalation_policies")
    op.drop_table("alert_escalation_policies")

    op.drop_index(
        "ix_alert_oncall_shifts_tenant_active",
        table_name="alert_oncall_shifts",
    )
    op.drop_index(
        "ix_alert_oncall_shifts_tenant_window",
        table_name="alert_oncall_shifts",
    )
    op.drop_index(
        "ix_alert_oncall_shifts_tenant_id_id",
        table_name="alert_oncall_shifts",
    )
    op.drop_index("ix_alert_oncall_shifts_updated_at", table_name="alert_oncall_shifts")
    op.drop_index("ix_alert_oncall_shifts_created_at", table_name="alert_oncall_shifts")
    op.drop_index("ix_alert_oncall_shifts_created_by", table_name="alert_oncall_shifts")
    op.drop_index("ix_alert_oncall_shifts_is_active", table_name="alert_oncall_shifts")
    op.drop_index("ix_alert_oncall_shifts_ends_at", table_name="alert_oncall_shifts")
    op.drop_index("ix_alert_oncall_shifts_starts_at", table_name="alert_oncall_shifts")
    op.drop_index("ix_alert_oncall_shifts_target", table_name="alert_oncall_shifts")
    op.drop_index("ix_alert_oncall_shifts_shift_name", table_name="alert_oncall_shifts")
    op.drop_index("ix_alert_oncall_shifts_tenant_id", table_name="alert_oncall_shifts")
    op.drop_table("alert_oncall_shifts")
