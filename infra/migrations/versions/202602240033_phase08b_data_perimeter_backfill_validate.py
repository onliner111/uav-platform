"""phase08b data perimeter backfill validate

Revision ID: 202602240033
Revises: 202602240032
Create Date: 2026-02-24
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "202602240033"
down_revision = "202602240032"
branch_labels = None
depends_on = None


def _validate_data_policy_user_tenant(bind: sa.Connection) -> None:
    mismatches = list(
        bind.execute(
            sa.text(
                """
                SELECT p.id
                FROM data_access_policies p
                LEFT JOIN users u ON u.id = p.user_id
                WHERE u.id IS NULL OR u.tenant_id <> p.tenant_id
                """
            )
        )
    )
    if mismatches:
        raise RuntimeError(
            "Phase08B validation failed: data_access_policies->users tenant mismatch. "
            f"count={len(mismatches)}"
        )


def _validate_org_refs(bind: sa.Connection, table_name: str) -> None:
    rows = list(
        bind.execute(
            sa.text(
                f"""
                SELECT t.id
                FROM {table_name} t
                LEFT JOIN org_units o
                  ON o.id = t.org_unit_id
                 AND o.tenant_id = t.tenant_id
                WHERE t.org_unit_id IS NOT NULL
                  AND o.id IS NULL
                """
            )
        )
    )
    if rows:
        raise RuntimeError(
            "Phase08B validation failed: org_unit_id tenant mismatch "
            f"table={table_name} count={len(rows)}"
        )


def _validate_defect_task_refs(bind: sa.Connection) -> None:
    rows = list(
        bind.execute(
            sa.text(
                """
                SELECT d.id
                FROM defects d
                LEFT JOIN inspection_tasks t
                  ON t.id = d.task_id
                 AND t.tenant_id = d.tenant_id
                WHERE d.task_id IS NOT NULL
                  AND t.id IS NULL
                """
            )
        )
    )
    if rows:
        raise RuntimeError(
            "Phase08B validation failed: defects.task_id tenant mismatch "
            f"count={len(rows)}"
        )


def upgrade() -> None:
    bind = op.get_bind()
    bind.execute(
        sa.text(
            """
            UPDATE defects d
            SET
              task_id = src.task_id,
              org_unit_id = COALESCE(d.org_unit_id, src.org_unit_id),
              project_code = COALESCE(d.project_code, src.project_code),
              area_code = COALESCE(d.area_code, src.area_code)
            FROM (
              SELECT
                o.id AS observation_id,
                o.tenant_id AS tenant_id,
                o.task_id AS task_id,
                t.org_unit_id AS org_unit_id,
                t.project_code AS project_code,
                t.area_code AS area_code
              FROM inspection_observations o
              LEFT JOIN inspection_tasks t
                ON t.id = o.task_id
               AND t.tenant_id = o.tenant_id
            ) src
            WHERE d.observation_id = src.observation_id
              AND d.tenant_id = src.tenant_id
            """
        )
    )
    _validate_data_policy_user_tenant(bind)
    _validate_org_refs(bind, "missions")
    _validate_org_refs(bind, "inspection_tasks")
    _validate_org_refs(bind, "defects")
    _validate_org_refs(bind, "incidents")
    _validate_defect_task_refs(bind)


def downgrade() -> None:
    # Validation/backfill step; no reversible schema changes.
    pass
