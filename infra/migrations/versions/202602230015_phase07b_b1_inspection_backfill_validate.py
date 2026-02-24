"""phase07b b1 inspection backfill validate

Revision ID: 202602230015
Revises: 202602230014
Create Date: 2026-02-23
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "202602230015"
down_revision = "202602230014"
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


def _validate_template_item_links(bind: sa.Connection) -> None:
    mismatches = [
        dict(row)
        for row in bind.execute(
            sa.text(
                """
                SELECT
                    i.id AS child_id,
                    i.tenant_id AS tenant_id,
                    i.template_id AS parent_id,
                    t.tenant_id AS parent_tenant_id
                FROM inspection_template_items i
                LEFT JOIN inspection_templates t ON t.id = i.template_id
                WHERE t.id IS NULL OR t.tenant_id <> i.tenant_id
                """
            )
        ).mappings()
    ]
    if mismatches:
        sample = _format_rows(mismatches[:20])
        raise RuntimeError(
            "Phase07B B1 validation failed: inspection_template_items->inspection_templates "
            f"tenant mismatch. count={len(mismatches)} sample=[{sample}]"
        )


def _validate_task_template_links(bind: sa.Connection) -> None:
    mismatches = [
        dict(row)
        for row in bind.execute(
            sa.text(
                """
                SELECT
                    it.id AS child_id,
                    it.tenant_id AS tenant_id,
                    it.template_id AS parent_id,
                    t.tenant_id AS parent_tenant_id
                FROM inspection_tasks it
                LEFT JOIN inspection_templates t ON t.id = it.template_id
                WHERE t.id IS NULL OR t.tenant_id <> it.tenant_id
                """
            )
        ).mappings()
    ]
    if mismatches:
        sample = _format_rows(mismatches[:20])
        raise RuntimeError(
            "Phase07B B1 validation failed: inspection_tasks->inspection_templates "
            f"tenant mismatch. count={len(mismatches)} sample=[{sample}]"
        )


def upgrade() -> None:
    bind = op.get_bind()
    # Backfill is not required in this batch because tenant_id already exists and is populated.
    _validate_template_item_links(bind)
    _validate_task_template_links(bind)


def downgrade() -> None:
    # Validation-only step; no data changes to reverse.
    pass
