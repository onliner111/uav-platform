"""phase07a identity backfill and validate

Revision ID: 202602220009
Revises: 202602220008
Create Date: 2026-02-22
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "202602220009"
down_revision = "202602220008"
branch_labels = None
depends_on = None


def _format_violation_rows(rows: list[dict[str, object]]) -> str:
    if not rows:
        return ""
    lines = []
    for row in rows:
        lines.append(
            f"user_id={row['user_id']} role_id={row['role_id']} "
            f"user_tenant_id={row['user_tenant_id']} role_tenant_id={row['role_tenant_id']}"
        )
    return "; ".join(lines)


def upgrade() -> None:
    bind = op.get_bind()

    violations = [
        dict(row)
        for row in bind.execute(
            sa.text(
                """
                SELECT
                    ur.user_id AS user_id,
                    ur.role_id AS role_id,
                    u.tenant_id AS user_tenant_id,
                    r.tenant_id AS role_tenant_id
                FROM user_roles ur
                LEFT JOIN users u ON u.id = ur.user_id
                LEFT JOIN roles r ON r.id = ur.role_id
                WHERE
                    u.id IS NULL
                    OR r.id IS NULL
                    OR u.tenant_id <> r.tenant_id
                """
            )
        ).mappings()
    ]
    if violations:
        preview = _format_violation_rows(violations[:20])
        raise RuntimeError(
            "Phase07A identity backfill blocked: found invalid user_roles rows before backfill. "
            f"count={len(violations)} sample=[{preview}]"
        )

    bind.execute(
        sa.text(
            """
            UPDATE user_roles
            SET tenant_id = (
                SELECT u.tenant_id
                FROM users u
                WHERE u.id = user_roles.user_id
            )
            WHERE tenant_id IS NULL
            """
        )
    )

    unresolved_count = bind.execute(
        sa.text("SELECT COUNT(*) FROM user_roles WHERE tenant_id IS NULL")
    ).scalar_one()
    if unresolved_count > 0:
        raise RuntimeError(
            "Phase07A identity backfill failed: user_roles.tenant_id remains NULL "
            f"for {unresolved_count} rows."
        )

    mismatch_count = bind.execute(
        sa.text(
            """
            SELECT COUNT(*)
            FROM user_roles ur
            JOIN users u ON u.id = ur.user_id
            JOIN roles r ON r.id = ur.role_id
            WHERE ur.tenant_id <> u.tenant_id OR ur.tenant_id <> r.tenant_id
            """
        )
    ).scalar_one()
    if mismatch_count > 0:
        raise RuntimeError(
            "Phase07A identity backfill failed: backfilled tenant_id mismatches remain. "
            f"count={mismatch_count}"
        )


def downgrade() -> None:
    # Data-only step; keep data as-is on downgrade.
    pass
