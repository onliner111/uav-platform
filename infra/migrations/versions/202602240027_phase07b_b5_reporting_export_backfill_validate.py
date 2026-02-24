"""phase07b b5 reporting export backfill validate

Revision ID: 202602240027
Revises: 202602240026
Create Date: 2026-02-24
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "202602240027"
down_revision = "202602240026"
branch_labels = None
depends_on = None


def _format_rows(rows: list[dict[str, object]]) -> str:
    if not rows:
        return ""
    return "; ".join(
        (
            "tenant_id="
            f"{row['tenant_id']} "
            f"child_id={row['child_id']} "
            f"parent_id={row['parent_id']} "
            f"parent_tenant_id={row['parent_tenant_id']}"
        )
        for row in rows
    )


def _validate_tenant_not_null(bind: sa.Connection, table: str) -> None:
    null_count = bind.execute(sa.text(f"SELECT COUNT(*) FROM {table} WHERE tenant_id IS NULL")).scalar_one()
    if null_count > 0:
        raise RuntimeError(
            f"Phase07B B5 validation failed: {table}.tenant_id contains NULL rows. count={null_count}"
        )


def _validate_approval_user_links(bind: sa.Connection) -> None:
    mismatches = [
        dict(row)
        for row in bind.execute(
            sa.text(
                """
                SELECT
                    ar.id AS child_id,
                    ar.tenant_id AS tenant_id,
                    ar.approved_by AS parent_id,
                    u.tenant_id AS parent_tenant_id
                FROM approval_records ar
                LEFT JOIN users u ON u.id = ar.approved_by
                WHERE u.id IS NULL OR u.tenant_id <> ar.tenant_id
                """
            )
        ).mappings()
    ]
    if mismatches:
        sample = _format_rows(mismatches[:20])
        raise RuntimeError(
            "Phase07B B5 validation failed: approval_records->users tenant mismatch. "
            f"count={len(mismatches)} sample=[{sample}]"
        )


def upgrade() -> None:
    bind = op.get_bind()
    # Backfill is not required in this batch because tenant_id and approved_by are already populated.
    _validate_tenant_not_null(bind, "approval_records")
    _validate_approval_user_links(bind)


def downgrade() -> None:
    # Validation-only step; no data changes to reverse.
    pass
