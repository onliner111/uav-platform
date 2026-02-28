"""phase25 wp2 slo alert expand

Revision ID: 202602280107
Revises: 202602280106
Create Date: 2026-02-28
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "202602280107"
down_revision = "202602280106"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "observability_slo_policies",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("policy_key", sa.String(length=120), nullable=False),
        sa.Column("service_name", sa.String(length=120), nullable=False),
        sa.Column("signal_name", sa.String(length=120), nullable=False, server_default="request"),
        sa.Column("target_ratio", sa.Float(), nullable=False, server_default=sa.text("0.99")),
        sa.Column("latency_threshold_ms", sa.Integer(), nullable=True),
        sa.Column("window_minutes", sa.Integer(), nullable=False, server_default=sa.text("5")),
        sa.Column("minimum_samples", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("alert_severity", sa.String(length=10), nullable=False, server_default="P2"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("detail", sa.JSON(), nullable=False),
        sa.Column("created_by", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "id", name="uq_observability_slo_policies_tenant_id_id"),
        sa.UniqueConstraint("tenant_id", "policy_key", name="uq_observability_slo_policies_tenant_key"),
    )
    op.create_index("ix_observability_slo_policies_tenant_id", "observability_slo_policies", ["tenant_id"])
    op.create_index("ix_observability_slo_policies_policy_key", "observability_slo_policies", ["policy_key"])
    op.create_index("ix_observability_slo_policies_service_name", "observability_slo_policies", ["service_name"])
    op.create_index("ix_observability_slo_policies_signal_name", "observability_slo_policies", ["signal_name"])
    op.create_index("ix_observability_slo_policies_alert_severity", "observability_slo_policies", ["alert_severity"])
    op.create_index("ix_observability_slo_policies_is_active", "observability_slo_policies", ["is_active"])
    op.create_index("ix_observability_slo_policies_created_by", "observability_slo_policies", ["created_by"])
    op.create_index("ix_observability_slo_policies_created_at", "observability_slo_policies", ["created_at"])
    op.create_index("ix_observability_slo_policies_updated_at", "observability_slo_policies", ["updated_at"])
    op.create_index(
        "ix_observability_slo_policies_tenant_id_id",
        "observability_slo_policies",
        ["tenant_id", "id"],
    )
    op.create_index(
        "ix_observability_slo_policies_tenant_key",
        "observability_slo_policies",
        ["tenant_id", "policy_key"],
    )
    op.create_index(
        "ix_observability_slo_policies_tenant_service",
        "observability_slo_policies",
        ["tenant_id", "service_name"],
    )
    op.create_index(
        "ix_observability_slo_policies_tenant_active",
        "observability_slo_policies",
        ["tenant_id", "is_active"],
    )

    op.create_table(
        "observability_alert_events",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("source", sa.String(length=50), nullable=False),
        sa.Column("severity", sa.String(length=10), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("message", sa.String(length=500), nullable=False),
        sa.Column("policy_id", sa.String(), nullable=True),
        sa.Column("target", sa.String(length=200), nullable=True),
        sa.Column("detail", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("acked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "id", name="uq_observability_alert_events_tenant_id_id"),
    )
    op.create_index("ix_observability_alert_events_tenant_id", "observability_alert_events", ["tenant_id"])
    op.create_index("ix_observability_alert_events_source", "observability_alert_events", ["source"])
    op.create_index("ix_observability_alert_events_severity", "observability_alert_events", ["severity"])
    op.create_index("ix_observability_alert_events_status", "observability_alert_events", ["status"])
    op.create_index("ix_observability_alert_events_policy_id", "observability_alert_events", ["policy_id"])
    op.create_index("ix_observability_alert_events_target", "observability_alert_events", ["target"])
    op.create_index("ix_observability_alert_events_created_at", "observability_alert_events", ["created_at"])
    op.create_index("ix_observability_alert_events_acked_at", "observability_alert_events", ["acked_at"])
    op.create_index("ix_observability_alert_events_closed_at", "observability_alert_events", ["closed_at"])
    op.create_index(
        "ix_observability_alert_events_tenant_id_id",
        "observability_alert_events",
        ["tenant_id", "id"],
    )
    op.create_index(
        "ix_observability_alert_events_tenant_status",
        "observability_alert_events",
        ["tenant_id", "status"],
    )
    op.create_index(
        "ix_observability_alert_events_tenant_source",
        "observability_alert_events",
        ["tenant_id", "source"],
    )
    op.create_index(
        "ix_observability_alert_events_tenant_created",
        "observability_alert_events",
        ["tenant_id", "created_at"],
    )

    op.create_table(
        "observability_slo_evaluations",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("policy_id", sa.String(), nullable=False),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("window_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("total_samples", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("good_samples", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("availability_ratio", sa.Float(), nullable=False, server_default=sa.text("1.0")),
        sa.Column("error_ratio", sa.Float(), nullable=False, server_default=sa.text("0.0")),
        sa.Column("p95_latency_ms", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="HEALTHY"),
        sa.Column("alert_triggered", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("alert_event_id", sa.String(), nullable=True),
        sa.Column("oncall_target", sa.String(length=200), nullable=True),
        sa.Column("detail", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "id", name="uq_observability_slo_evaluations_tenant_id_id"),
    )
    op.create_index("ix_observability_slo_evaluations_tenant_id", "observability_slo_evaluations", ["tenant_id"])
    op.create_index("ix_observability_slo_evaluations_policy_id", "observability_slo_evaluations", ["policy_id"])
    op.create_index("ix_observability_slo_evaluations_window_start", "observability_slo_evaluations", ["window_start"])
    op.create_index("ix_observability_slo_evaluations_window_end", "observability_slo_evaluations", ["window_end"])
    op.create_index("ix_observability_slo_evaluations_status", "observability_slo_evaluations", ["status"])
    op.create_index("ix_observability_slo_evaluations_alert_triggered", "observability_slo_evaluations", ["alert_triggered"])
    op.create_index("ix_observability_slo_evaluations_alert_event_id", "observability_slo_evaluations", ["alert_event_id"])
    op.create_index("ix_observability_slo_evaluations_created_at", "observability_slo_evaluations", ["created_at"])
    op.create_index(
        "ix_observability_slo_evaluations_tenant_id_id",
        "observability_slo_evaluations",
        ["tenant_id", "id"],
    )
    op.create_index(
        "ix_observability_slo_evaluations_tenant_policy",
        "observability_slo_evaluations",
        ["tenant_id", "policy_id"],
    )
    op.create_index(
        "ix_observability_slo_evaluations_tenant_status",
        "observability_slo_evaluations",
        ["tenant_id", "status"],
    )
    op.create_index(
        "ix_observability_slo_evaluations_tenant_window",
        "observability_slo_evaluations",
        ["tenant_id", "window_start", "window_end"],
    )


def downgrade() -> None:
    op.drop_index("ix_observability_slo_evaluations_tenant_window", table_name="observability_slo_evaluations")
    op.drop_index("ix_observability_slo_evaluations_tenant_status", table_name="observability_slo_evaluations")
    op.drop_index("ix_observability_slo_evaluations_tenant_policy", table_name="observability_slo_evaluations")
    op.drop_index("ix_observability_slo_evaluations_tenant_id_id", table_name="observability_slo_evaluations")
    op.drop_index("ix_observability_slo_evaluations_created_at", table_name="observability_slo_evaluations")
    op.drop_index("ix_observability_slo_evaluations_alert_event_id", table_name="observability_slo_evaluations")
    op.drop_index("ix_observability_slo_evaluations_alert_triggered", table_name="observability_slo_evaluations")
    op.drop_index("ix_observability_slo_evaluations_status", table_name="observability_slo_evaluations")
    op.drop_index("ix_observability_slo_evaluations_window_end", table_name="observability_slo_evaluations")
    op.drop_index("ix_observability_slo_evaluations_window_start", table_name="observability_slo_evaluations")
    op.drop_index("ix_observability_slo_evaluations_policy_id", table_name="observability_slo_evaluations")
    op.drop_index("ix_observability_slo_evaluations_tenant_id", table_name="observability_slo_evaluations")
    op.drop_table("observability_slo_evaluations")

    op.drop_index("ix_observability_alert_events_tenant_created", table_name="observability_alert_events")
    op.drop_index("ix_observability_alert_events_tenant_source", table_name="observability_alert_events")
    op.drop_index("ix_observability_alert_events_tenant_status", table_name="observability_alert_events")
    op.drop_index("ix_observability_alert_events_tenant_id_id", table_name="observability_alert_events")
    op.drop_index("ix_observability_alert_events_closed_at", table_name="observability_alert_events")
    op.drop_index("ix_observability_alert_events_acked_at", table_name="observability_alert_events")
    op.drop_index("ix_observability_alert_events_created_at", table_name="observability_alert_events")
    op.drop_index("ix_observability_alert_events_target", table_name="observability_alert_events")
    op.drop_index("ix_observability_alert_events_policy_id", table_name="observability_alert_events")
    op.drop_index("ix_observability_alert_events_status", table_name="observability_alert_events")
    op.drop_index("ix_observability_alert_events_severity", table_name="observability_alert_events")
    op.drop_index("ix_observability_alert_events_source", table_name="observability_alert_events")
    op.drop_index("ix_observability_alert_events_tenant_id", table_name="observability_alert_events")
    op.drop_table("observability_alert_events")

    op.drop_index("ix_observability_slo_policies_tenant_active", table_name="observability_slo_policies")
    op.drop_index("ix_observability_slo_policies_tenant_service", table_name="observability_slo_policies")
    op.drop_index("ix_observability_slo_policies_tenant_key", table_name="observability_slo_policies")
    op.drop_index("ix_observability_slo_policies_tenant_id_id", table_name="observability_slo_policies")
    op.drop_index("ix_observability_slo_policies_updated_at", table_name="observability_slo_policies")
    op.drop_index("ix_observability_slo_policies_created_at", table_name="observability_slo_policies")
    op.drop_index("ix_observability_slo_policies_created_by", table_name="observability_slo_policies")
    op.drop_index("ix_observability_slo_policies_is_active", table_name="observability_slo_policies")
    op.drop_index("ix_observability_slo_policies_alert_severity", table_name="observability_slo_policies")
    op.drop_index("ix_observability_slo_policies_signal_name", table_name="observability_slo_policies")
    op.drop_index("ix_observability_slo_policies_service_name", table_name="observability_slo_policies")
    op.drop_index("ix_observability_slo_policies_policy_key", table_name="observability_slo_policies")
    op.drop_index("ix_observability_slo_policies_tenant_id", table_name="observability_slo_policies")
    op.drop_table("observability_slo_policies")
