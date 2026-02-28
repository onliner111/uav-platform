"""phase25 wp2 slo alert enforce

Revision ID: 202602280109
Revises: 202602280108
Create Date: 2026-02-28
"""

from __future__ import annotations

from alembic import op

# revision identifiers, used by Alembic.
revision = "202602280109"
down_revision = "202602280108"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_check_constraint(
        "ck_observability_slo_policies_key_not_empty",
        "observability_slo_policies",
        "policy_key <> ''",
    )
    op.create_check_constraint(
        "ck_observability_slo_policies_service_not_empty",
        "observability_slo_policies",
        "service_name <> ''",
    )
    op.create_check_constraint(
        "ck_observability_slo_policies_signal_not_empty",
        "observability_slo_policies",
        "signal_name <> ''",
    )
    op.create_check_constraint(
        "ck_observability_slo_policies_target_ratio",
        "observability_slo_policies",
        "target_ratio >= 0 AND target_ratio <= 1",
    )
    op.create_check_constraint(
        "ck_observability_slo_policies_latency",
        "observability_slo_policies",
        "latency_threshold_ms IS NULL OR latency_threshold_ms >= 1",
    )
    op.create_check_constraint(
        "ck_observability_slo_policies_window",
        "observability_slo_policies",
        "window_minutes >= 1 AND window_minutes <= 1440",
    )
    op.create_check_constraint(
        "ck_observability_slo_policies_min_samples",
        "observability_slo_policies",
        "minimum_samples >= 1",
    )
    op.create_check_constraint(
        "ck_observability_slo_policies_alert_severity",
        "observability_slo_policies",
        "alert_severity IN ('P1', 'P2', 'P3')",
    )

    op.create_check_constraint(
        "ck_observability_alert_events_source_not_empty",
        "observability_alert_events",
        "source <> ''",
    )
    op.create_check_constraint(
        "ck_observability_alert_events_status",
        "observability_alert_events",
        "status IN ('OPEN', 'ACKED', 'CLOSED')",
    )
    op.create_check_constraint(
        "ck_observability_alert_events_severity",
        "observability_alert_events",
        "severity IN ('P1', 'P2', 'P3')",
    )
    op.create_check_constraint(
        "ck_observability_alert_events_title_not_empty",
        "observability_alert_events",
        "title <> ''",
    )
    op.create_check_constraint(
        "ck_observability_alert_events_message_not_empty",
        "observability_alert_events",
        "message <> ''",
    )

    op.create_check_constraint(
        "ck_observability_slo_evaluations_status",
        "observability_slo_evaluations",
        "status IN ('HEALTHY', 'BREACHED')",
    )
    op.create_check_constraint(
        "ck_observability_slo_evaluations_samples_non_negative",
        "observability_slo_evaluations",
        "total_samples >= 0 AND good_samples >= 0",
    )
    op.create_check_constraint(
        "ck_observability_slo_evaluations_ratio",
        "observability_slo_evaluations",
        "availability_ratio >= 0 AND availability_ratio <= 1 AND error_ratio >= 0 AND error_ratio <= 1",
    )
    op.create_check_constraint(
        "ck_observability_slo_evaluations_latency_non_negative",
        "observability_slo_evaluations",
        "p95_latency_ms IS NULL OR p95_latency_ms >= 0",
    )

    op.create_foreign_key(
        "fk_observability_alert_events_tenant_policy",
        "observability_alert_events",
        "observability_slo_policies",
        ["tenant_id", "policy_id"],
        ["tenant_id", "id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_observability_slo_evaluations_tenant_policy",
        "observability_slo_evaluations",
        "observability_slo_policies",
        ["tenant_id", "policy_id"],
        ["tenant_id", "id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_observability_slo_evaluations_tenant_alert_event",
        "observability_slo_evaluations",
        "observability_alert_events",
        ["tenant_id", "alert_event_id"],
        ["tenant_id", "id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_observability_slo_evaluations_tenant_alert_event",
        "observability_slo_evaluations",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_observability_slo_evaluations_tenant_policy",
        "observability_slo_evaluations",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_observability_alert_events_tenant_policy",
        "observability_alert_events",
        type_="foreignkey",
    )

    op.drop_constraint(
        "ck_observability_slo_evaluations_latency_non_negative",
        "observability_slo_evaluations",
        type_="check",
    )
    op.drop_constraint(
        "ck_observability_slo_evaluations_ratio",
        "observability_slo_evaluations",
        type_="check",
    )
    op.drop_constraint(
        "ck_observability_slo_evaluations_samples_non_negative",
        "observability_slo_evaluations",
        type_="check",
    )
    op.drop_constraint(
        "ck_observability_slo_evaluations_status",
        "observability_slo_evaluations",
        type_="check",
    )

    op.drop_constraint(
        "ck_observability_alert_events_message_not_empty",
        "observability_alert_events",
        type_="check",
    )
    op.drop_constraint(
        "ck_observability_alert_events_title_not_empty",
        "observability_alert_events",
        type_="check",
    )
    op.drop_constraint(
        "ck_observability_alert_events_severity",
        "observability_alert_events",
        type_="check",
    )
    op.drop_constraint(
        "ck_observability_alert_events_status",
        "observability_alert_events",
        type_="check",
    )
    op.drop_constraint(
        "ck_observability_alert_events_source_not_empty",
        "observability_alert_events",
        type_="check",
    )

    op.drop_constraint(
        "ck_observability_slo_policies_alert_severity",
        "observability_slo_policies",
        type_="check",
    )
    op.drop_constraint(
        "ck_observability_slo_policies_min_samples",
        "observability_slo_policies",
        type_="check",
    )
    op.drop_constraint(
        "ck_observability_slo_policies_window",
        "observability_slo_policies",
        type_="check",
    )
    op.drop_constraint(
        "ck_observability_slo_policies_latency",
        "observability_slo_policies",
        type_="check",
    )
    op.drop_constraint(
        "ck_observability_slo_policies_target_ratio",
        "observability_slo_policies",
        type_="check",
    )
    op.drop_constraint(
        "ck_observability_slo_policies_signal_not_empty",
        "observability_slo_policies",
        type_="check",
    )
    op.drop_constraint(
        "ck_observability_slo_policies_service_not_empty",
        "observability_slo_policies",
        type_="check",
    )
    op.drop_constraint(
        "ck_observability_slo_policies_key_not_empty",
        "observability_slo_policies",
        type_="check",
    )
