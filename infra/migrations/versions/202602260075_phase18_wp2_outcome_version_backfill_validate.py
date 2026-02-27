"""phase18 wp2 outcome version backfill validate

Revision ID: 202602260075
Revises: 202602260074
Create Date: 2026-02-26
"""

from __future__ import annotations

from uuid import uuid4

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "202602260075"
down_revision = "202602260074"
branch_labels = None
depends_on = None


def _assert_zero(bind: sa.engine.Connection, sql: str, message: str) -> None:
    rows = list(bind.execute(sa.text(sql)))
    if rows:
        raise RuntimeError(f"{message}. count={len(rows)}")


def _backfill_init_versions(bind: sa.engine.Connection) -> None:
    rows = list(
        bind.execute(
            sa.text(
                """
                SELECT r.id AS outcome_id,
                       r.tenant_id AS tenant_id,
                       r.outcome_type AS outcome_type,
                       r.status AS status,
                       r.point_lat AS point_lat,
                       r.point_lon AS point_lon,
                       r.alt_m AS alt_m,
                       r.confidence AS confidence,
                       r.payload AS payload,
                       r.created_by AS created_by,
                       r.created_at AS created_at
                FROM outcome_catalog_records r
                LEFT JOIN outcome_catalog_versions v
                  ON v.tenant_id = r.tenant_id
                 AND v.outcome_id = r.id
                WHERE v.id IS NULL
                """
            )
        ).mappings()
    )
    for row in rows:
        bind.execute(
            sa.text(
                """
                INSERT INTO outcome_catalog_versions (
                    id,
                    tenant_id,
                    outcome_id,
                    version_no,
                    outcome_type,
                    status,
                    point_lat,
                    point_lon,
                    alt_m,
                    confidence,
                    payload,
                    change_type,
                    change_note,
                    created_by,
                    created_at
                ) VALUES (
                    :id,
                    :tenant_id,
                    :outcome_id,
                    :version_no,
                    :outcome_type,
                    :status,
                    :point_lat,
                    :point_lon,
                    :alt_m,
                    :confidence,
                    :payload,
                    :change_type,
                    :change_note,
                    :created_by,
                    :created_at
                )
                """
            ),
            {
                "id": str(uuid4()),
                "tenant_id": row["tenant_id"],
                "outcome_id": row["outcome_id"],
                "version_no": 1,
                "outcome_type": row["outcome_type"],
                "status": row["status"],
                "point_lat": row["point_lat"],
                "point_lon": row["point_lon"],
                "alt_m": row["alt_m"],
                "confidence": row["confidence"],
                "payload": row["payload"] if row["payload"] is not None else {},
                "change_type": "INIT_SNAPSHOT",
                "change_note": "phase18 wp2 migration backfill",
                "created_by": row["created_by"],
                "created_at": row["created_at"],
            },
        )


def upgrade() -> None:
    bind = op.get_bind()
    _backfill_init_versions(bind)
    _assert_zero(
        bind,
        """
        SELECT id FROM outcome_catalog_versions
        WHERE version_no <= 0
           OR json_typeof(payload) <> 'object'
           OR change_type NOT IN ('INIT_SNAPSHOT', 'AUTO_MATERIALIZE', 'STATUS_UPDATE')
        """,
        "Phase18-WP2 validation failed: outcome_catalog_versions invalid rows",
    )


def downgrade() -> None:
    # Validation-only step.
    pass
