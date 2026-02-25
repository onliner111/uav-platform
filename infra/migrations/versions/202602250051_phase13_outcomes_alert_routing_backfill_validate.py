"""phase13 outcomes alert routing backfill validate

Revision ID: 202602250051
Revises: 202602250050
Create Date: 2026-02-25
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "202602250051"
down_revision = "202602250050"
branch_labels = None
depends_on = None


def _validate_in_set(
    bind: sa.Connection,
    *,
    table: str,
    column: str,
    allowed_values: tuple[str, ...],
    allow_null: bool = False,
) -> None:
    null_sql = "" if not allow_null else f"{column} IS NOT NULL AND "
    in_values = ", ".join(f"'{value}'" for value in allowed_values)
    rows = list(
        bind.execute(
            sa.text(
                f"""
                SELECT id
                FROM {table}
                WHERE {null_sql}{column} NOT IN ({in_values})
                """
            )
        )
    )
    if rows:
        raise RuntimeError(
            f"Phase13-P0 validation failed: {table}.{column} out of enum range. count={len(rows)}"
        )


def upgrade() -> None:
    bind = op.get_bind()
    bind.execute(
        sa.text(
            """
            UPDATE alerts
            SET priority_level = CASE
                WHEN alert_type IN ('LINK_LOSS', 'GEOFENCE_BREACH') THEN 'P1'
                WHEN severity = 'CRITICAL' THEN 'P2'
                ELSE 'P3'
            END
            WHERE priority_level IS NULL
            """
        )
    )
    bind.execute(
        sa.text(
            """
            UPDATE alerts
            SET route_status = 'UNROUTED'
            WHERE route_status IS NULL
            """
        )
    )

    _validate_in_set(bind, table="alerts", column="priority_level", allowed_values=("P1", "P2", "P3"))
    _validate_in_set(
        bind,
        table="alerts",
        column="route_status",
        allowed_values=("UNROUTED", "ROUTED"),
    )
    _validate_in_set(
        bind,
        table="alert_routing_rules",
        column="priority_level",
        allowed_values=("P1", "P2", "P3"),
    )
    _validate_in_set(
        bind,
        table="alert_routing_rules",
        column="alert_type",
        allowed_values=("LOW_BATTERY", "LINK_LOSS", "GEOFENCE_BREACH"),
        allow_null=True,
    )
    _validate_in_set(
        bind,
        table="alert_routing_rules",
        column="channel",
        allowed_values=("IN_APP", "EMAIL", "SMS", "WEBHOOK"),
    )
    _validate_in_set(
        bind,
        table="alert_route_logs",
        column="priority_level",
        allowed_values=("P1", "P2", "P3"),
    )
    _validate_in_set(
        bind,
        table="alert_route_logs",
        column="channel",
        allowed_values=("IN_APP", "EMAIL", "SMS", "WEBHOOK"),
    )
    _validate_in_set(
        bind,
        table="alert_route_logs",
        column="delivery_status",
        allowed_values=("SENT", "FAILED", "SKIPPED"),
    )
    _validate_in_set(
        bind,
        table="raw_data_catalog_records",
        column="data_type",
        allowed_values=("TELEMETRY", "IMAGE", "VIDEO", "DOCUMENT", "LOG"),
    )
    _validate_in_set(
        bind,
        table="outcome_catalog_records",
        column="source_type",
        allowed_values=("INSPECTION_OBSERVATION", "ALERT", "MANUAL"),
    )
    _validate_in_set(
        bind,
        table="outcome_catalog_records",
        column="outcome_type",
        allowed_values=("DEFECT", "HIDDEN_RISK", "INCIDENT", "OTHER"),
    )
    _validate_in_set(
        bind,
        table="outcome_catalog_records",
        column="status",
        allowed_values=("NEW", "IN_REVIEW", "VERIFIED", "ARCHIVED"),
    )


def downgrade() -> None:
    # Validation-only step.
    pass
