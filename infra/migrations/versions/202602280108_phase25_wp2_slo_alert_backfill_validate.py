"""phase25 wp2 slo alert backfill validate

Revision ID: 202602280108
Revises: 202602280107
Create Date: 2026-02-28
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "202602280108"
down_revision = "202602280107"
branch_labels = None
depends_on = None


def _assert_zero(bind: sa.Connection, sql: str, error_message: str) -> None:
    rows = list(bind.execute(sa.text(sql)))
    if rows:
        raise RuntimeError(f"{error_message}. count={len(rows)}")


def upgrade() -> None:
    bind = op.get_bind()
    _assert_zero(
        bind,
        """
        SELECT id FROM observability_slo_policies
        WHERE policy_key = '' OR service_name = '' OR signal_name = ''
        """,
        "Phase25-WP2 validation failed: policy/service/signal names cannot be empty",
    )
    _assert_zero(
        bind,
        """
        SELECT id FROM observability_slo_policies
        WHERE target_ratio < 0 OR target_ratio > 1
        """,
        "Phase25-WP2 validation failed: target_ratio out of range",
    )
    _assert_zero(
        bind,
        """
        SELECT id FROM observability_slo_evaluations
        WHERE total_samples < 0 OR good_samples < 0
        """,
        "Phase25-WP2 validation failed: total/good samples cannot be negative",
    )
    _assert_zero(
        bind,
        """
        SELECT id FROM observability_alert_events
        WHERE source = '' OR title = '' OR message = ''
        """,
        "Phase25-WP2 validation failed: alert source/title/message cannot be empty",
    )


def downgrade() -> None:
    # Validation/backfill step only.
    pass
