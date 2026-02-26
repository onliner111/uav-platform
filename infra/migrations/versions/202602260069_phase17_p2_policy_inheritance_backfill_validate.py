"""phase17 p2 policy inheritance backfill validate

Revision ID: 202602260069
Revises: 202602260068
Create Date: 2026-02-26
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "202602260069"
down_revision = "202602260068"
branch_labels = None
depends_on = None


def _assert_zero(bind: sa.engine.Connection, sql: str, message: str) -> None:
    rows = list(bind.execute(sa.text(sql)))
    if rows:
        raise RuntimeError(f"{message}. count={len(rows)}")


def upgrade() -> None:
    bind = op.get_bind()
    _assert_zero(
        bind,
        """
        SELECT id FROM data_access_policies
        WHERE json_typeof(denied_org_unit_ids) <> 'array'
        OR json_typeof(denied_project_codes) <> 'array'
        OR json_typeof(denied_area_codes) <> 'array'
        OR json_typeof(denied_task_ids) <> 'array'
        OR json_typeof(denied_resource_ids) <> 'array'
        """,
        "Phase17-P2 validation failed: data_access_policies denied fields are not JSON arrays",
    )
    _assert_zero(
        bind,
        """
        SELECT id FROM role_data_access_policies
        WHERE scope_mode NOT IN ('ALL', 'SCOPED')
        OR json_typeof(org_unit_ids) <> 'array'
        OR json_typeof(project_codes) <> 'array'
        OR json_typeof(area_codes) <> 'array'
        OR json_typeof(task_ids) <> 'array'
        OR json_typeof(resource_ids) <> 'array'
        """,
        "Phase17-P2 validation failed: role_data_access_policies invalid rows",
    )


def downgrade() -> None:
    # Validation-only step.
    pass
