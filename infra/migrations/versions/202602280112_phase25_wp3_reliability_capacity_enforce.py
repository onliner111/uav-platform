"""phase25 wp3 reliability capacity enforce

Revision ID: 202602280112
Revises: 202602280111
Create Date: 2026-02-28
"""

from __future__ import annotations

from alembic import op

# revision identifiers, used by Alembic.
revision = "202602280112"
down_revision = "202602280111"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_check_constraint(
        "ck_reliability_backup_runs_run_type",
        "reliability_backup_runs",
        "run_type IN ('FULL', 'INCREMENTAL')",
    )
    op.create_check_constraint(
        "ck_reliability_backup_runs_status",
        "reliability_backup_runs",
        "status IN ('SUCCESS', 'FAILED')",
    )

    op.create_check_constraint(
        "ck_reliability_restore_drills_status",
        "reliability_restore_drills",
        "status IN ('PASSED', 'FAILED')",
    )
    op.create_check_constraint(
        "ck_reliability_restore_drills_objective",
        "reliability_restore_drills",
        "objective_rto_seconds >= 1",
    )
    op.create_check_constraint(
        "ck_reliability_restore_drills_actual",
        "reliability_restore_drills",
        "actual_rto_seconds >= 0",
    )

    op.create_check_constraint(
        "ck_security_inspection_runs_counts",
        "security_inspection_runs",
        "total_checks >= 0 AND passed_checks >= 0 AND warned_checks >= 0 AND failed_checks >= 0",
    )
    op.create_check_constraint(
        "ck_security_inspection_runs_score",
        "security_inspection_runs",
        "score_percent >= 0 AND score_percent <= 100",
    )

    op.create_check_constraint(
        "ck_security_inspection_items_status",
        "security_inspection_items",
        "status IN ('PASS', 'WARN', 'FAIL')",
    )
    op.create_check_constraint(
        "ck_security_inspection_items_check_key",
        "security_inspection_items",
        "check_key <> ''",
    )
    op.create_check_constraint(
        "ck_security_inspection_items_message",
        "security_inspection_items",
        "message <> ''",
    )

    op.create_check_constraint(
        "ck_capacity_policies_meter_not_empty",
        "capacity_policies",
        "meter_key <> ''",
    )
    op.create_check_constraint(
        "ck_capacity_policies_target_range",
        "capacity_policies",
        "target_utilization_pct >= 1 AND target_utilization_pct <= 100",
    )
    op.create_check_constraint(
        "ck_capacity_policies_scale_out_range",
        "capacity_policies",
        "scale_out_threshold_pct >= 1 AND scale_out_threshold_pct <= 100",
    )
    op.create_check_constraint(
        "ck_capacity_policies_scale_in_range",
        "capacity_policies",
        "scale_in_threshold_pct >= 1 AND scale_in_threshold_pct <= 100",
    )
    op.create_check_constraint(
        "ck_capacity_policies_replicas",
        "capacity_policies",
        "min_replicas >= 1 AND max_replicas >= 1 AND current_replicas >= min_replicas AND current_replicas <= max_replicas",
    )
    op.create_check_constraint(
        "ck_capacity_policies_threshold_order",
        "capacity_policies",
        "scale_in_threshold_pct < scale_out_threshold_pct",
    )

    op.create_check_constraint(
        "ck_capacity_forecasts_predicted_usage",
        "capacity_forecasts",
        "predicted_usage >= 0",
    )
    op.create_check_constraint(
        "ck_capacity_forecasts_recommended_replicas",
        "capacity_forecasts",
        "recommended_replicas >= 1",
    )
    op.create_check_constraint(
        "ck_capacity_forecasts_decision",
        "capacity_forecasts",
        "decision IN ('SCALE_OUT', 'SCALE_IN', 'HOLD')",
    )

    op.create_foreign_key(
        "fk_reliability_restore_drills_tenant_backup",
        "reliability_restore_drills",
        "reliability_backup_runs",
        ["tenant_id", "backup_run_id"],
        ["tenant_id", "id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_security_inspection_items_tenant_run",
        "security_inspection_items",
        "security_inspection_runs",
        ["tenant_id", "run_id"],
        ["tenant_id", "id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_capacity_forecasts_tenant_policy",
        "capacity_forecasts",
        "capacity_policies",
        ["tenant_id", "policy_id"],
        ["tenant_id", "id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_capacity_forecasts_tenant_policy",
        "capacity_forecasts",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_security_inspection_items_tenant_run",
        "security_inspection_items",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_reliability_restore_drills_tenant_backup",
        "reliability_restore_drills",
        type_="foreignkey",
    )

    op.drop_constraint(
        "ck_capacity_forecasts_decision",
        "capacity_forecasts",
        type_="check",
    )
    op.drop_constraint(
        "ck_capacity_forecasts_recommended_replicas",
        "capacity_forecasts",
        type_="check",
    )
    op.drop_constraint(
        "ck_capacity_forecasts_predicted_usage",
        "capacity_forecasts",
        type_="check",
    )

    op.drop_constraint(
        "ck_capacity_policies_threshold_order",
        "capacity_policies",
        type_="check",
    )
    op.drop_constraint(
        "ck_capacity_policies_replicas",
        "capacity_policies",
        type_="check",
    )
    op.drop_constraint(
        "ck_capacity_policies_scale_in_range",
        "capacity_policies",
        type_="check",
    )
    op.drop_constraint(
        "ck_capacity_policies_scale_out_range",
        "capacity_policies",
        type_="check",
    )
    op.drop_constraint(
        "ck_capacity_policies_target_range",
        "capacity_policies",
        type_="check",
    )
    op.drop_constraint(
        "ck_capacity_policies_meter_not_empty",
        "capacity_policies",
        type_="check",
    )

    op.drop_constraint(
        "ck_security_inspection_items_message",
        "security_inspection_items",
        type_="check",
    )
    op.drop_constraint(
        "ck_security_inspection_items_check_key",
        "security_inspection_items",
        type_="check",
    )
    op.drop_constraint(
        "ck_security_inspection_items_status",
        "security_inspection_items",
        type_="check",
    )

    op.drop_constraint(
        "ck_security_inspection_runs_score",
        "security_inspection_runs",
        type_="check",
    )
    op.drop_constraint(
        "ck_security_inspection_runs_counts",
        "security_inspection_runs",
        type_="check",
    )

    op.drop_constraint(
        "ck_reliability_restore_drills_actual",
        "reliability_restore_drills",
        type_="check",
    )
    op.drop_constraint(
        "ck_reliability_restore_drills_objective",
        "reliability_restore_drills",
        type_="check",
    )
    op.drop_constraint(
        "ck_reliability_restore_drills_status",
        "reliability_restore_drills",
        type_="check",
    )

    op.drop_constraint(
        "ck_reliability_backup_runs_status",
        "reliability_backup_runs",
        type_="check",
    )
    op.drop_constraint(
        "ck_reliability_backup_runs_run_type",
        "reliability_backup_runs",
        type_="check",
    )
