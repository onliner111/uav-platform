"""phase25 wp1 observability enforce

Revision ID: 202602280106
Revises: 202602280105
Create Date: 2026-02-28
"""

from __future__ import annotations

from alembic import op

# revision identifiers, used by Alembic.
revision = "202602280106"
down_revision = "202602280105"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_check_constraint(
        "ck_observability_signals_type",
        "observability_signals",
        "signal_type IN ('LOG', 'METRIC', 'TRACE')",
    )
    op.create_check_constraint(
        "ck_observability_signals_level",
        "observability_signals",
        "level IN ('DEBUG', 'INFO', 'WARN', 'ERROR')",
    )
    op.create_check_constraint(
        "ck_observability_signals_service_not_empty",
        "observability_signals",
        "service_name <> ''",
    )
    op.create_check_constraint(
        "ck_observability_signals_name_not_empty",
        "observability_signals",
        "signal_name <> ''",
    )
    op.create_check_constraint(
        "ck_observability_signals_duration_non_negative",
        "observability_signals",
        "duration_ms IS NULL OR duration_ms >= 0",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_observability_signals_duration_non_negative",
        "observability_signals",
        type_="check",
    )
    op.drop_constraint(
        "ck_observability_signals_name_not_empty",
        "observability_signals",
        type_="check",
    )
    op.drop_constraint(
        "ck_observability_signals_service_not_empty",
        "observability_signals",
        type_="check",
    )
    op.drop_constraint(
        "ck_observability_signals_level",
        "observability_signals",
        type_="check",
    )
    op.drop_constraint(
        "ck_observability_signals_type",
        "observability_signals",
        type_="check",
    )
