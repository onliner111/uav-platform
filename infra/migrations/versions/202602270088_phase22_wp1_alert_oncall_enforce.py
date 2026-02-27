"""phase22 wp1 alert oncall enforce

Revision ID: 202602270088
Revises: 202602270087
Create Date: 2026-02-27
"""

from __future__ import annotations

from alembic import op

# revision identifiers, used by Alembic.
revision = "202602270088"
down_revision = "202602270087"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_check_constraint(
        "ck_alert_oncall_shifts_window",
        "alert_oncall_shifts",
        "ends_at > starts_at",
    )
    op.create_check_constraint(
        "ck_alert_escalation_policies_priority_level",
        "alert_escalation_policies",
        "priority_level IN ('P1', 'P2', 'P3')",
    )
    op.create_check_constraint(
        "ck_alert_escalation_policies_escalation_channel",
        "alert_escalation_policies",
        "escalation_channel IN ('IN_APP', 'EMAIL', 'SMS', 'WEBHOOK')",
    )
    op.create_check_constraint(
        "ck_alert_escalation_policies_ack_timeout_seconds",
        "alert_escalation_policies",
        "ack_timeout_seconds >= 30",
    )
    op.create_check_constraint(
        "ck_alert_escalation_policies_repeat_threshold",
        "alert_escalation_policies",
        "repeat_threshold >= 2",
    )
    op.create_check_constraint(
        "ck_alert_escalation_policies_max_level",
        "alert_escalation_policies",
        "max_escalation_level >= 1",
    )
    op.create_check_constraint(
        "ck_alert_escalation_policies_target_not_empty",
        "alert_escalation_policies",
        "escalation_target <> ''",
    )
    op.create_check_constraint(
        "ck_alert_escalation_executions_reason",
        "alert_escalation_executions",
        "reason IN ('ACK_TIMEOUT', 'REPEAT_TRIGGER', 'SHIFT_HANDOVER')",
    )
    op.create_check_constraint(
        "ck_alert_escalation_executions_channel",
        "alert_escalation_executions",
        "channel IN ('IN_APP', 'EMAIL', 'SMS', 'WEBHOOK')",
    )
    op.create_check_constraint(
        "ck_alert_escalation_executions_level",
        "alert_escalation_executions",
        "escalation_level >= 1",
    )
    op.create_check_constraint(
        "ck_alert_escalation_executions_target_not_empty",
        "alert_escalation_executions",
        "to_target <> ''",
    )
    op.create_foreign_key(
        "fk_alert_escalation_executions_tenant_alert",
        "alert_escalation_executions",
        "alerts",
        ["tenant_id", "alert_id"],
        ["tenant_id", "id"],
        ondelete="CASCADE",
    )

    op.drop_constraint(
        "ck_alert_handling_actions_action_type",
        "alert_handling_actions",
        type_="check",
    )
    op.create_check_constraint(
        "ck_alert_handling_actions_action_type",
        "alert_handling_actions",
        "action_type IN ('ACK', 'DISPATCH', 'ESCALATE', 'VERIFY', 'REVIEW', 'CLOSE')",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_alert_handling_actions_action_type",
        "alert_handling_actions",
        type_="check",
    )
    op.create_check_constraint(
        "ck_alert_handling_actions_action_type",
        "alert_handling_actions",
        "action_type IN ('ACK', 'DISPATCH', 'VERIFY', 'REVIEW', 'CLOSE')",
    )

    op.drop_constraint(
        "fk_alert_escalation_executions_tenant_alert",
        "alert_escalation_executions",
        type_="foreignkey",
    )
    op.drop_constraint(
        "ck_alert_escalation_executions_target_not_empty",
        "alert_escalation_executions",
        type_="check",
    )
    op.drop_constraint(
        "ck_alert_escalation_executions_level",
        "alert_escalation_executions",
        type_="check",
    )
    op.drop_constraint(
        "ck_alert_escalation_executions_channel",
        "alert_escalation_executions",
        type_="check",
    )
    op.drop_constraint(
        "ck_alert_escalation_executions_reason",
        "alert_escalation_executions",
        type_="check",
    )
    op.drop_constraint(
        "ck_alert_escalation_policies_target_not_empty",
        "alert_escalation_policies",
        type_="check",
    )
    op.drop_constraint(
        "ck_alert_escalation_policies_max_level",
        "alert_escalation_policies",
        type_="check",
    )
    op.drop_constraint(
        "ck_alert_escalation_policies_repeat_threshold",
        "alert_escalation_policies",
        type_="check",
    )
    op.drop_constraint(
        "ck_alert_escalation_policies_ack_timeout_seconds",
        "alert_escalation_policies",
        type_="check",
    )
    op.drop_constraint(
        "ck_alert_escalation_policies_escalation_channel",
        "alert_escalation_policies",
        type_="check",
    )
    op.drop_constraint(
        "ck_alert_escalation_policies_priority_level",
        "alert_escalation_policies",
        type_="check",
    )
    op.drop_constraint(
        "ck_alert_oncall_shifts_window",
        "alert_oncall_shifts",
        type_="check",
    )
