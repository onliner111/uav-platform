"""phase24 wp2 usage quota backfill validate

Revision ID: 202602270099
Revises: 202602270098
Create Date: 2026-02-27
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "202602270099"
down_revision = "202602270098"
branch_labels = None
depends_on = None


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _day_bucket(value: datetime) -> datetime:
    normalized = _as_utc(value)
    return datetime(normalized.year, normalized.month, normalized.day, tzinfo=UTC)


def _assert_zero(bind: sa.Connection, sql: str, error_message: str) -> None:
    rows = list(bind.execute(sa.text(sql)))
    if rows:
        raise RuntimeError(f"{error_message}. count={len(rows)}")


def upgrade() -> None:
    bind = op.get_bind()
    now = datetime.now(UTC)

    event_rows = list(
        bind.execute(
            sa.text(
                """
                SELECT tenant_id, meter_key, occurred_at, quantity
                FROM billing_usage_events
                """
            )
        ).mappings()
    )
    aggregated: dict[tuple[str, str, datetime], int] = {}
    for row in event_rows:
        occurred_at_raw = row["occurred_at"]
        if not isinstance(occurred_at_raw, datetime):
            continue
        key = (
            str(row["tenant_id"]),
            str(row["meter_key"]),
            _day_bucket(occurred_at_raw),
        )
        aggregated[key] = aggregated.get(key, 0) + int(row["quantity"])

    existing_rows = list(
        bind.execute(
            sa.text(
                """
                SELECT id, tenant_id, meter_key, usage_date
                FROM billing_usage_aggregate_daily
                """
            )
        ).mappings()
    )
    existing_by_key: dict[tuple[str, str, datetime], str] = {}
    for row in existing_rows:
        usage_date_raw = row["usage_date"]
        if not isinstance(usage_date_raw, datetime):
            continue
        existing_by_key[(
            str(row["tenant_id"]),
            str(row["meter_key"]),
            _day_bucket(usage_date_raw),
        )] = str(row["id"])

    for key, total_quantity in aggregated.items():
        tenant_id, meter_key, usage_date = key
        existing_id = existing_by_key.get(key)
        if existing_id is None:
            bind.execute(
                sa.text(
                    """
                    INSERT INTO billing_usage_aggregate_daily
                    (id, tenant_id, meter_key, usage_date, total_quantity, updated_at)
                    VALUES
                    (:id, :tenant_id, :meter_key, :usage_date, :total_quantity, :updated_at)
                    """
                ),
                {
                    "id": str(uuid4()),
                    "tenant_id": tenant_id,
                    "meter_key": meter_key,
                    "usage_date": usage_date,
                    "total_quantity": total_quantity,
                    "updated_at": now,
                },
            )
            continue

        bind.execute(
            sa.text(
                """
                UPDATE billing_usage_aggregate_daily
                SET total_quantity = :total_quantity,
                    updated_at = :updated_at
                WHERE id = :id
                """
            ),
            {
                "id": existing_id,
                "total_quantity": total_quantity,
                "updated_at": now,
            },
        )

    _assert_zero(
        bind,
        """
        SELECT id FROM billing_usage_events WHERE quantity <= 0
        """,
        "Phase24-WP2 validation failed: billing_usage_events.quantity must be > 0",
    )
    _assert_zero(
        bind,
        """
        SELECT id FROM billing_usage_events WHERE meter_key = '' OR source_event_id = ''
        """,
        "Phase24-WP2 validation failed: billing_usage_events meter/source cannot be empty",
    )
    _assert_zero(
        bind,
        """
        SELECT tenant_id, meter_key, source_event_id
        FROM billing_usage_events
        GROUP BY tenant_id, meter_key, source_event_id
        HAVING COUNT(*) > 1
        """,
        "Phase24-WP2 validation failed: usage event idempotency key duplicated",
    )
    _assert_zero(
        bind,
        """
        SELECT id FROM billing_usage_aggregate_daily WHERE total_quantity < 0
        """,
        "Phase24-WP2 validation failed: billing_usage_aggregate_daily.total_quantity must be >= 0",
    )


def downgrade() -> None:
    # Validation/backfill step only.
    pass
