"""phase24 wp2 usage quota enforce

Revision ID: 202602270100
Revises: 202602270099
Create Date: 2026-02-27
"""

from __future__ import annotations

from alembic import op

# revision identifiers, used by Alembic.
revision = "202602270100"
down_revision = "202602270099"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_check_constraint(
        "ck_billing_usage_events_meter_not_empty",
        "billing_usage_events",
        "meter_key <> ''",
    )
    op.create_check_constraint(
        "ck_billing_usage_events_source_not_empty",
        "billing_usage_events",
        "source_event_id <> ''",
    )
    op.create_check_constraint(
        "ck_billing_usage_events_quantity_positive",
        "billing_usage_events",
        "quantity > 0",
    )
    op.create_check_constraint(
        "ck_billing_usage_aggregate_daily_meter_not_empty",
        "billing_usage_aggregate_daily",
        "meter_key <> ''",
    )
    op.create_check_constraint(
        "ck_billing_usage_aggregate_daily_total_non_negative",
        "billing_usage_aggregate_daily",
        "total_quantity >= 0",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_billing_usage_aggregate_daily_total_non_negative",
        "billing_usage_aggregate_daily",
        type_="check",
    )
    op.drop_constraint(
        "ck_billing_usage_aggregate_daily_meter_not_empty",
        "billing_usage_aggregate_daily",
        type_="check",
    )
    op.drop_constraint(
        "ck_billing_usage_events_quantity_positive",
        "billing_usage_events",
        type_="check",
    )
    op.drop_constraint(
        "ck_billing_usage_events_source_not_empty",
        "billing_usage_events",
        type_="check",
    )
    op.drop_constraint(
        "ck_billing_usage_events_meter_not_empty",
        "billing_usage_events",
        type_="check",
    )
