"""phase07b b3 incident alert backfill validate

Revision ID: 202602230021
Revises: 202602230020
Create Date: 2026-02-23
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "202602230021"
down_revision = "202602230020"
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
            f"Phase07B B3 validation failed: {table}.tenant_id contains NULL rows. count={null_count}"
        )


def _validate_incident_task_links(bind: sa.Connection) -> None:
    mismatches = [
        dict(row)
        for row in bind.execute(
            sa.text(
                """
                SELECT
                    i.id AS child_id,
                    i.tenant_id AS tenant_id,
                    i.linked_task_id AS parent_id,
                    t.tenant_id AS parent_tenant_id
                FROM incidents i
                LEFT JOIN inspection_tasks t ON t.id = i.linked_task_id
                WHERE i.linked_task_id IS NOT NULL
                  AND (t.id IS NULL OR t.tenant_id <> i.tenant_id)
                """
            )
        ).mappings()
    ]
    if mismatches:
        sample = _format_rows(mismatches[:20])
        raise RuntimeError(
            "Phase07B B3 validation failed: incidents->inspection_tasks tenant mismatch. "
            f"count={len(mismatches)} sample=[{sample}]"
        )


def upgrade() -> None:
    bind = op.get_bind()
    # Backfill is not required in this batch because tenant_id already exists and is populated.
    _validate_tenant_not_null(bind, "incidents")
    _validate_incident_task_links(bind)


def downgrade() -> None:
    # Validation-only step; no data changes to reverse.
    pass
