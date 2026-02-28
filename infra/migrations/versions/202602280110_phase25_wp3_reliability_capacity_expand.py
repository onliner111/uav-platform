"""phase25 wp3 reliability capacity expand

Revision ID: 202602280110
Revises: 202602280109
Create Date: 2026-02-28
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "202602280110"
down_revision = "202602280109"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "reliability_backup_runs",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("run_type", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("storage_uri", sa.String(length=300), nullable=True),
        sa.Column("checksum", sa.String(length=120), nullable=True),
        sa.Column("is_drill", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("detail", sa.JSON(), nullable=False),
        sa.Column("triggered_by", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "id", name="uq_reliability_backup_runs_tenant_id_id"),
    )
    op.create_index("ix_reliability_backup_runs_tenant_id", "reliability_backup_runs", ["tenant_id"])
    op.create_index("ix_reliability_backup_runs_run_type", "reliability_backup_runs", ["run_type"])
    op.create_index("ix_reliability_backup_runs_status", "reliability_backup_runs", ["status"])
    op.create_index("ix_reliability_backup_runs_is_drill", "reliability_backup_runs", ["is_drill"])
    op.create_index("ix_reliability_backup_runs_triggered_by", "reliability_backup_runs", ["triggered_by"])
    op.create_index("ix_reliability_backup_runs_created_at", "reliability_backup_runs", ["created_at"])
    op.create_index("ix_reliability_backup_runs_completed_at", "reliability_backup_runs", ["completed_at"])
    op.create_index("ix_reliability_backup_runs_tenant_id_id", "reliability_backup_runs", ["tenant_id", "id"])
    op.create_index("ix_reliability_backup_runs_tenant_status", "reliability_backup_runs", ["tenant_id", "status"])
    op.create_index("ix_reliability_backup_runs_tenant_created", "reliability_backup_runs", ["tenant_id", "created_at"])

    op.create_table(
        "reliability_restore_drills",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("backup_run_id", sa.String(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("objective_rto_seconds", sa.Integer(), nullable=False, server_default=sa.text("300")),
        sa.Column("actual_rto_seconds", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("detail", sa.JSON(), nullable=False),
        sa.Column("executed_by", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "id", name="uq_reliability_restore_drills_tenant_id_id"),
    )
    op.create_index("ix_reliability_restore_drills_tenant_id", "reliability_restore_drills", ["tenant_id"])
    op.create_index("ix_reliability_restore_drills_backup_run_id", "reliability_restore_drills", ["backup_run_id"])
    op.create_index("ix_reliability_restore_drills_status", "reliability_restore_drills", ["status"])
    op.create_index("ix_reliability_restore_drills_executed_by", "reliability_restore_drills", ["executed_by"])
    op.create_index("ix_reliability_restore_drills_created_at", "reliability_restore_drills", ["created_at"])
    op.create_index(
        "ix_reliability_restore_drills_tenant_id_id",
        "reliability_restore_drills",
        ["tenant_id", "id"],
    )
    op.create_index(
        "ix_reliability_restore_drills_tenant_backup",
        "reliability_restore_drills",
        ["tenant_id", "backup_run_id"],
    )

    op.create_table(
        "security_inspection_runs",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("baseline_version", sa.String(length=50), nullable=False),
        sa.Column("total_checks", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("passed_checks", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("warned_checks", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("failed_checks", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("score_percent", sa.Float(), nullable=False, server_default=sa.text("100.0")),
        sa.Column("detail", sa.JSON(), nullable=False),
        sa.Column("executed_by", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "id", name="uq_security_inspection_runs_tenant_id_id"),
    )
    op.create_index("ix_security_inspection_runs_tenant_id", "security_inspection_runs", ["tenant_id"])
    op.create_index("ix_security_inspection_runs_baseline_version", "security_inspection_runs", ["baseline_version"])
    op.create_index("ix_security_inspection_runs_score_percent", "security_inspection_runs", ["score_percent"])
    op.create_index("ix_security_inspection_runs_executed_by", "security_inspection_runs", ["executed_by"])
    op.create_index("ix_security_inspection_runs_created_at", "security_inspection_runs", ["created_at"])
    op.create_index("ix_security_inspection_runs_tenant_id_id", "security_inspection_runs", ["tenant_id", "id"])
    op.create_index("ix_security_inspection_runs_tenant_created", "security_inspection_runs", ["tenant_id", "created_at"])

    op.create_table(
        "security_inspection_items",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("run_id", sa.String(), nullable=False),
        sa.Column("check_key", sa.String(length=120), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("message", sa.String(length=500), nullable=False),
        sa.Column("detail", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "id", name="uq_security_inspection_items_tenant_id_id"),
    )
    op.create_index("ix_security_inspection_items_tenant_id", "security_inspection_items", ["tenant_id"])
    op.create_index("ix_security_inspection_items_run_id", "security_inspection_items", ["run_id"])
    op.create_index("ix_security_inspection_items_check_key", "security_inspection_items", ["check_key"])
    op.create_index("ix_security_inspection_items_status", "security_inspection_items", ["status"])
    op.create_index("ix_security_inspection_items_created_at", "security_inspection_items", ["created_at"])
    op.create_index("ix_security_inspection_items_tenant_id_id", "security_inspection_items", ["tenant_id", "id"])
    op.create_index("ix_security_inspection_items_tenant_run", "security_inspection_items", ["tenant_id", "run_id"])
    op.create_index("ix_security_inspection_items_tenant_status", "security_inspection_items", ["tenant_id", "status"])

    op.create_table(
        "capacity_policies",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("meter_key", sa.String(length=120), nullable=False),
        sa.Column("target_utilization_pct", sa.Integer(), nullable=False, server_default=sa.text("75")),
        sa.Column("scale_out_threshold_pct", sa.Integer(), nullable=False, server_default=sa.text("85")),
        sa.Column("scale_in_threshold_pct", sa.Integer(), nullable=False, server_default=sa.text("55")),
        sa.Column("min_replicas", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("max_replicas", sa.Integer(), nullable=False, server_default=sa.text("10")),
        sa.Column("current_replicas", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("detail", sa.JSON(), nullable=False),
        sa.Column("updated_by", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "id", name="uq_capacity_policies_tenant_id_id"),
        sa.UniqueConstraint("tenant_id", "meter_key", name="uq_capacity_policies_tenant_meter_key"),
    )
    op.create_index("ix_capacity_policies_tenant_id", "capacity_policies", ["tenant_id"])
    op.create_index("ix_capacity_policies_meter_key", "capacity_policies", ["meter_key"])
    op.create_index("ix_capacity_policies_is_active", "capacity_policies", ["is_active"])
    op.create_index("ix_capacity_policies_updated_by", "capacity_policies", ["updated_by"])
    op.create_index("ix_capacity_policies_created_at", "capacity_policies", ["created_at"])
    op.create_index("ix_capacity_policies_updated_at", "capacity_policies", ["updated_at"])
    op.create_index("ix_capacity_policies_tenant_id_id", "capacity_policies", ["tenant_id", "id"])
    op.create_index("ix_capacity_policies_tenant_meter", "capacity_policies", ["tenant_id", "meter_key"])
    op.create_index("ix_capacity_policies_tenant_active", "capacity_policies", ["tenant_id", "is_active"])

    op.create_table(
        "capacity_forecasts",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("policy_id", sa.String(), nullable=False),
        sa.Column("meter_key", sa.String(length=120), nullable=False),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("window_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("predicted_usage", sa.Float(), nullable=False, server_default=sa.text("0.0")),
        sa.Column("recommended_replicas", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("decision", sa.String(length=20), nullable=False, server_default="HOLD"),
        sa.Column("detail", sa.JSON(), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "id", name="uq_capacity_forecasts_tenant_id_id"),
    )
    op.create_index("ix_capacity_forecasts_tenant_id", "capacity_forecasts", ["tenant_id"])
    op.create_index("ix_capacity_forecasts_policy_id", "capacity_forecasts", ["policy_id"])
    op.create_index("ix_capacity_forecasts_meter_key", "capacity_forecasts", ["meter_key"])
    op.create_index("ix_capacity_forecasts_window_start", "capacity_forecasts", ["window_start"])
    op.create_index("ix_capacity_forecasts_window_end", "capacity_forecasts", ["window_end"])
    op.create_index("ix_capacity_forecasts_decision", "capacity_forecasts", ["decision"])
    op.create_index("ix_capacity_forecasts_generated_at", "capacity_forecasts", ["generated_at"])
    op.create_index("ix_capacity_forecasts_tenant_id_id", "capacity_forecasts", ["tenant_id", "id"])
    op.create_index("ix_capacity_forecasts_tenant_policy", "capacity_forecasts", ["tenant_id", "policy_id"])
    op.create_index("ix_capacity_forecasts_tenant_meter", "capacity_forecasts", ["tenant_id", "meter_key"])
    op.create_index("ix_capacity_forecasts_tenant_generated", "capacity_forecasts", ["tenant_id", "generated_at"])


def downgrade() -> None:
    op.drop_index("ix_capacity_forecasts_tenant_generated", table_name="capacity_forecasts")
    op.drop_index("ix_capacity_forecasts_tenant_meter", table_name="capacity_forecasts")
    op.drop_index("ix_capacity_forecasts_tenant_policy", table_name="capacity_forecasts")
    op.drop_index("ix_capacity_forecasts_tenant_id_id", table_name="capacity_forecasts")
    op.drop_index("ix_capacity_forecasts_generated_at", table_name="capacity_forecasts")
    op.drop_index("ix_capacity_forecasts_decision", table_name="capacity_forecasts")
    op.drop_index("ix_capacity_forecasts_window_end", table_name="capacity_forecasts")
    op.drop_index("ix_capacity_forecasts_window_start", table_name="capacity_forecasts")
    op.drop_index("ix_capacity_forecasts_meter_key", table_name="capacity_forecasts")
    op.drop_index("ix_capacity_forecasts_policy_id", table_name="capacity_forecasts")
    op.drop_index("ix_capacity_forecasts_tenant_id", table_name="capacity_forecasts")
    op.drop_table("capacity_forecasts")

    op.drop_index("ix_capacity_policies_tenant_active", table_name="capacity_policies")
    op.drop_index("ix_capacity_policies_tenant_meter", table_name="capacity_policies")
    op.drop_index("ix_capacity_policies_tenant_id_id", table_name="capacity_policies")
    op.drop_index("ix_capacity_policies_updated_at", table_name="capacity_policies")
    op.drop_index("ix_capacity_policies_created_at", table_name="capacity_policies")
    op.drop_index("ix_capacity_policies_updated_by", table_name="capacity_policies")
    op.drop_index("ix_capacity_policies_is_active", table_name="capacity_policies")
    op.drop_index("ix_capacity_policies_meter_key", table_name="capacity_policies")
    op.drop_index("ix_capacity_policies_tenant_id", table_name="capacity_policies")
    op.drop_table("capacity_policies")

    op.drop_index("ix_security_inspection_items_tenant_status", table_name="security_inspection_items")
    op.drop_index("ix_security_inspection_items_tenant_run", table_name="security_inspection_items")
    op.drop_index("ix_security_inspection_items_tenant_id_id", table_name="security_inspection_items")
    op.drop_index("ix_security_inspection_items_created_at", table_name="security_inspection_items")
    op.drop_index("ix_security_inspection_items_status", table_name="security_inspection_items")
    op.drop_index("ix_security_inspection_items_check_key", table_name="security_inspection_items")
    op.drop_index("ix_security_inspection_items_run_id", table_name="security_inspection_items")
    op.drop_index("ix_security_inspection_items_tenant_id", table_name="security_inspection_items")
    op.drop_table("security_inspection_items")

    op.drop_index("ix_security_inspection_runs_tenant_created", table_name="security_inspection_runs")
    op.drop_index("ix_security_inspection_runs_tenant_id_id", table_name="security_inspection_runs")
    op.drop_index("ix_security_inspection_runs_created_at", table_name="security_inspection_runs")
    op.drop_index("ix_security_inspection_runs_executed_by", table_name="security_inspection_runs")
    op.drop_index("ix_security_inspection_runs_score_percent", table_name="security_inspection_runs")
    op.drop_index("ix_security_inspection_runs_baseline_version", table_name="security_inspection_runs")
    op.drop_index("ix_security_inspection_runs_tenant_id", table_name="security_inspection_runs")
    op.drop_table("security_inspection_runs")

    op.drop_index("ix_reliability_restore_drills_tenant_backup", table_name="reliability_restore_drills")
    op.drop_index("ix_reliability_restore_drills_tenant_id_id", table_name="reliability_restore_drills")
    op.drop_index("ix_reliability_restore_drills_created_at", table_name="reliability_restore_drills")
    op.drop_index("ix_reliability_restore_drills_executed_by", table_name="reliability_restore_drills")
    op.drop_index("ix_reliability_restore_drills_status", table_name="reliability_restore_drills")
    op.drop_index("ix_reliability_restore_drills_backup_run_id", table_name="reliability_restore_drills")
    op.drop_index("ix_reliability_restore_drills_tenant_id", table_name="reliability_restore_drills")
    op.drop_table("reliability_restore_drills")

    op.drop_index("ix_reliability_backup_runs_tenant_created", table_name="reliability_backup_runs")
    op.drop_index("ix_reliability_backup_runs_tenant_status", table_name="reliability_backup_runs")
    op.drop_index("ix_reliability_backup_runs_tenant_id_id", table_name="reliability_backup_runs")
    op.drop_index("ix_reliability_backup_runs_completed_at", table_name="reliability_backup_runs")
    op.drop_index("ix_reliability_backup_runs_created_at", table_name="reliability_backup_runs")
    op.drop_index("ix_reliability_backup_runs_triggered_by", table_name="reliability_backup_runs")
    op.drop_index("ix_reliability_backup_runs_is_drill", table_name="reliability_backup_runs")
    op.drop_index("ix_reliability_backup_runs_status", table_name="reliability_backup_runs")
    op.drop_index("ix_reliability_backup_runs_run_type", table_name="reliability_backup_runs")
    op.drop_index("ix_reliability_backup_runs_tenant_id", table_name="reliability_backup_runs")
    op.drop_table("reliability_backup_runs")
