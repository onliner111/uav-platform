"""phase15 kpi open platform backfill validate

Revision ID: 202602250060
Revises: 202602250059
Create Date: 2026-02-25
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "202602250060"
down_revision = "202602250059"
branch_labels = None
depends_on = None


def _assert_zero(bind: sa.engine.Connection, sql: str, message: str) -> None:
    rows = list(bind.execute(sa.text(sql)))
    if rows:
        raise RuntimeError(f"{message}. count={len(rows)}")


def upgrade() -> None:
    bind = op.get_bind()
    _assert_zero(
        bind,
        """
        SELECT id FROM kpi_snapshot_records
        WHERE window_type NOT IN ('DAILY', 'WEEKLY', 'MONTHLY', 'QUARTERLY', 'CUSTOM')
        """,
        "Phase15 validation failed: kpi_snapshot_records.window_type out of enum range",
    )
    _assert_zero(
        bind,
        """
        SELECT id FROM kpi_snapshot_records
        WHERE to_ts <= from_ts
        """,
        "Phase15 validation failed: kpi_snapshot_records period invalid",
    )
    _assert_zero(
        bind,
        """
        SELECT id FROM kpi_heatmap_bin_records
        WHERE source NOT IN ('OUTCOME', 'ALERT')
        """,
        "Phase15 validation failed: kpi_heatmap_bin_records.source out of enum range",
    )
    _assert_zero(
        bind,
        """
        SELECT id FROM kpi_heatmap_bin_records
        WHERE count < 0
        """,
        "Phase15 validation failed: kpi_heatmap_bin_records.count negative",
    )
    _assert_zero(
        bind,
        """
        SELECT id FROM open_webhook_endpoints
        WHERE auth_type NOT IN ('HMAC_SHA256')
        """,
        "Phase15 validation failed: open_webhook_endpoints.auth_type out of enum range",
    )
    _assert_zero(
        bind,
        """
        SELECT id FROM open_webhook_deliveries
        WHERE status NOT IN ('SENT', 'FAILED', 'SKIPPED')
        """,
        "Phase15 validation failed: open_webhook_deliveries.status out of enum range",
    )
    _assert_zero(
        bind,
        """
        SELECT id FROM open_adapter_ingress_events
        WHERE status NOT IN ('ACCEPTED', 'REJECTED')
        """,
        "Phase15 validation failed: open_adapter_ingress_events.status out of enum range",
    )


def downgrade() -> None:
    # Validation-only step.
    pass
