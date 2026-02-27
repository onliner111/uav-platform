"""phase22 wp3 alert silence sla enforce

Revision ID: 202602270091
Revises: 202602270090
Create Date: 2026-02-27
"""

from __future__ import annotations

from alembic import op

# revision identifiers, used by Alembic.
revision = "202602270091"
down_revision = "202602270090"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_check_constraint(
        "ck_alert_silence_rules_alert_type",
        "alert_silence_rules",
        "alert_type IS NULL OR alert_type IN ('LOW_BATTERY', 'LINK_LOSS', 'GEOFENCE_BREACH')",
    )
    op.create_check_constraint(
        "ck_alert_silence_rules_window",
        "alert_silence_rules",
        "starts_at IS NULL OR ends_at IS NULL OR ends_at > starts_at",
    )
    op.create_check_constraint(
        "ck_alert_aggregation_rules_alert_type",
        "alert_aggregation_rules",
        "alert_type IS NULL OR alert_type IN ('LOW_BATTERY', 'LINK_LOSS', 'GEOFENCE_BREACH')",
    )
    op.create_check_constraint(
        "ck_alert_aggregation_rules_window_seconds",
        "alert_aggregation_rules",
        "window_seconds >= 10",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_alert_aggregation_rules_window_seconds",
        "alert_aggregation_rules",
        type_="check",
    )
    op.drop_constraint(
        "ck_alert_aggregation_rules_alert_type",
        "alert_aggregation_rules",
        type_="check",
    )
    op.drop_constraint(
        "ck_alert_silence_rules_window",
        "alert_silence_rules",
        type_="check",
    )
    op.drop_constraint(
        "ck_alert_silence_rules_alert_type",
        "alert_silence_rules",
        type_="check",
    )
