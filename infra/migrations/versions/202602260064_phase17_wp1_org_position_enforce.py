"""phase17 wp1 org position enforce

Revision ID: 202602260064
Revises: 202602260063
Create Date: 2026-02-26
"""

from __future__ import annotations

from alembic import op

# revision identifiers, used by Alembic.
revision = "202602260064"
down_revision = "202602260063"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_check_constraint(
        "ck_org_units_unit_type",
        "org_units",
        "unit_type IN ('ORGANIZATION', 'DEPARTMENT')",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_org_units_unit_type",
        "org_units",
        type_="check",
    )
