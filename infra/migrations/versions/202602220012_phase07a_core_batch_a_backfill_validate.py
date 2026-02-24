"""phase07a core batch a backfill validate

Revision ID: 202602220012
Revises: 202602220011
Create Date: 2026-02-22
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "202602220012"
down_revision = "202602220011"
branch_labels = None
depends_on = None


def _format_rows(rows: list[dict[str, object]]) -> str:
    if not rows:
        return ""
    parts: list[str] = []
    for row in rows:
        parts.append(
            "tenant_id="
            f"{row['tenant_id']} "
            f"child_id={row['child_id']} "
            f"parent_id={row['parent_id']} "
            f"parent_tenant_id={row['parent_tenant_id']}"
        )
    return "; ".join(parts)


def _validate_missions_drone_links(bind: sa.Connection) -> None:
    mismatches = [
        dict(row)
        for row in bind.execute(
            sa.text(
                """
                SELECT
                    m.id AS child_id,
                    m.tenant_id AS tenant_id,
                    m.drone_id AS parent_id,
                    d.tenant_id AS parent_tenant_id
                FROM missions m
                LEFT JOIN drones d ON d.id = m.drone_id
                WHERE m.drone_id IS NOT NULL
                  AND (d.id IS NULL OR d.tenant_id <> m.tenant_id)
                """
            )
        ).mappings()
    ]
    if mismatches:
        sample = _format_rows(mismatches[:20])
        raise RuntimeError(
            "Phase07A BatchA validation failed: missions->drones tenant mismatch. "
            f"count={len(mismatches)} sample=[{sample}]"
        )


def _validate_mission_runs_mission_links(bind: sa.Connection) -> None:
    mismatches = [
        dict(row)
        for row in bind.execute(
            sa.text(
                """
                SELECT
                    mr.id AS child_id,
                    mr.tenant_id AS tenant_id,
                    mr.mission_id AS parent_id,
                    m.tenant_id AS parent_tenant_id
                FROM mission_runs mr
                LEFT JOIN missions m ON m.id = mr.mission_id
                WHERE m.id IS NULL OR m.tenant_id <> mr.tenant_id
                """
            )
        ).mappings()
    ]
    if mismatches:
        sample = _format_rows(mismatches[:20])
        raise RuntimeError(
            "Phase07A BatchA validation failed: mission_runs->missions tenant mismatch. "
            f"count={len(mismatches)} sample=[{sample}]"
        )


def upgrade() -> None:
    bind = op.get_bind()
    # Backfill is not required in this batch because tenant_id already exists and is not-null.
    _validate_missions_drone_links(bind)
    _validate_mission_runs_mission_links(bind)


def downgrade() -> None:
    # Validation-only step; no data changes to reverse.
    pass
