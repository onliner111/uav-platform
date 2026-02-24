"""phase07b b2 defect backfill validate

Revision ID: 202602230018
Revises: 202602230017
Create Date: 2026-02-23
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "202602230018"
down_revision = "202602230017"
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
            f"Phase07B B2 validation failed: {table}.tenant_id contains NULL rows. count={null_count}"
        )


def _validate_defect_action_links(bind: sa.Connection) -> None:
    mismatches = [
        dict(row)
        for row in bind.execute(
            sa.text(
                """
                SELECT
                    da.id AS child_id,
                    da.tenant_id AS tenant_id,
                    da.defect_id AS parent_id,
                    d.tenant_id AS parent_tenant_id
                FROM defect_actions da
                LEFT JOIN defects d ON d.id = da.defect_id
                WHERE d.id IS NULL OR d.tenant_id <> da.tenant_id
                """
            )
        ).mappings()
    ]
    if mismatches:
        sample = _format_rows(mismatches[:20])
        raise RuntimeError(
            "Phase07B B2 validation failed: defect_actions->defects tenant mismatch. "
            f"count={len(mismatches)} sample=[{sample}]"
        )


def upgrade() -> None:
    bind = op.get_bind()
    # Backfill is not required in this batch because tenant_id already exists and is populated.
    _validate_tenant_not_null(bind, "defects")
    _validate_tenant_not_null(bind, "defect_actions")
    _validate_defect_action_links(bind)


def downgrade() -> None:
    # Validation-only step; no data changes to reverse.
    pass
