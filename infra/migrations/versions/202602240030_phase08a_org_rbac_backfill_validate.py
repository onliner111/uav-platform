"""phase08a org rbac backfill validate

Revision ID: 202602240030
Revises: 202602240029
Create Date: 2026-02-24
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "202602240030"
down_revision = "202602240029"
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


def _validate_org_unit_parent_links(bind: sa.Connection) -> None:
    mismatches = [
        dict(row)
        for row in bind.execute(
            sa.text(
                """
                SELECT
                    c.id AS child_id,
                    c.tenant_id AS tenant_id,
                    c.parent_id AS parent_id,
                    p.tenant_id AS parent_tenant_id
                FROM org_units c
                LEFT JOIN org_units p ON p.id = c.parent_id
                WHERE c.parent_id IS NOT NULL
                  AND (p.id IS NULL OR p.tenant_id <> c.tenant_id)
                """
            )
        ).mappings()
    ]
    if mismatches:
        sample = _format_rows(mismatches[:20])
        raise RuntimeError(
            "Phase08A validation failed: org_units parent tenant mismatch. "
            f"count={len(mismatches)} sample=[{sample}]"
        )


def _validate_membership_user_links(bind: sa.Connection) -> None:
    mismatches = [
        dict(row)
        for row in bind.execute(
            sa.text(
                """
                SELECT
                    m.tenant_id AS tenant_id,
                    m.user_id AS child_id,
                    m.user_id AS parent_id,
                    u.tenant_id AS parent_tenant_id
                FROM user_org_memberships m
                LEFT JOIN users u ON u.id = m.user_id
                WHERE u.id IS NULL OR u.tenant_id <> m.tenant_id
                """
            )
        ).mappings()
    ]
    if mismatches:
        sample = _format_rows(mismatches[:20])
        raise RuntimeError(
            "Phase08A validation failed: user_org_memberships->users tenant mismatch. "
            f"count={len(mismatches)} sample=[{sample}]"
        )


def _validate_membership_org_links(bind: sa.Connection) -> None:
    mismatches = [
        dict(row)
        for row in bind.execute(
            sa.text(
                """
                SELECT
                    m.tenant_id AS tenant_id,
                    m.org_unit_id AS child_id,
                    m.org_unit_id AS parent_id,
                    o.tenant_id AS parent_tenant_id
                FROM user_org_memberships m
                LEFT JOIN org_units o ON o.id = m.org_unit_id
                WHERE o.id IS NULL OR o.tenant_id <> m.tenant_id
                """
            )
        ).mappings()
    ]
    if mismatches:
        sample = _format_rows(mismatches[:20])
        raise RuntimeError(
            "Phase08A validation failed: user_org_memberships->org_units tenant mismatch. "
            f"count={len(mismatches)} sample=[{sample}]"
        )


def upgrade() -> None:
    bind = op.get_bind()
    # Backfill is not required for new tables in this batch.
    _validate_org_unit_parent_links(bind)
    _validate_membership_user_links(bind)
    _validate_membership_org_links(bind)


def downgrade() -> None:
    # Validation-only step; no data changes to reverse.
    pass

