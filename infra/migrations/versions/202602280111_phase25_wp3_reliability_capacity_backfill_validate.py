"""phase25 wp3 reliability capacity backfill validate

Revision ID: 202602280111
Revises: 202602280110
Create Date: 2026-02-28
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "202602280111"
down_revision = "202602280110"
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
        SELECT id FROM reliability_backup_runs
        WHERE run_type NOT IN ('FULL', 'INCREMENTAL') OR status NOT IN ('SUCCESS', 'FAILED')
        """,
        "Phase25-WP3 validation failed: backup run enum invalid",
    )
    _assert_zero(
        bind,
        """
        SELECT id FROM reliability_restore_drills
        WHERE status NOT IN ('PASSED', 'FAILED')
           OR objective_rto_seconds < 1
           OR actual_rto_seconds < 0
        """,
        "Phase25-WP3 validation failed: restore drill values invalid",
    )
    _assert_zero(
        bind,
        """
        SELECT id FROM security_inspection_items
        WHERE status NOT IN ('PASS', 'WARN', 'FAIL') OR check_key = '' OR message = ''
        """,
        "Phase25-WP3 validation failed: security inspection item invalid",
    )
    _assert_zero(
        bind,
        """
        SELECT id FROM capacity_policies
        WHERE meter_key = ''
           OR target_utilization_pct < 1 OR target_utilization_pct > 100
           OR scale_out_threshold_pct < 1 OR scale_out_threshold_pct > 100
           OR scale_in_threshold_pct < 1 OR scale_in_threshold_pct > 100
           OR min_replicas < 1 OR max_replicas < 1
           OR current_replicas < min_replicas OR current_replicas > max_replicas
           OR scale_in_threshold_pct >= scale_out_threshold_pct
        """,
        "Phase25-WP3 validation failed: capacity policy invalid",
    )


def downgrade() -> None:
    # Validation/backfill step only.
    pass
