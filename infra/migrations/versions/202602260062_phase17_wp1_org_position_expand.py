"""phase17 wp1 org position expand

Revision ID: 202602260062
Revises: 202602250061
Create Date: 2026-02-26
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "202602260062"
down_revision = "202602250061"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "org_units",
        sa.Column(
            "unit_type",
            sa.String(length=30),
            nullable=False,
            server_default=sa.text("'DEPARTMENT'"),
        ),
    )
    op.create_index("ix_org_units_unit_type", "org_units", ["unit_type"])

    op.add_column(
        "user_org_memberships",
        sa.Column("job_title", sa.String(length=120), nullable=True),
    )
    op.add_column(
        "user_org_memberships",
        sa.Column("job_code", sa.String(length=80), nullable=True),
    )
    op.add_column(
        "user_org_memberships",
        sa.Column("is_manager", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.create_index("ix_user_org_memberships_job_code", "user_org_memberships", ["job_code"])
    op.create_index("ix_user_org_memberships_is_manager", "user_org_memberships", ["is_manager"])


def downgrade() -> None:
    op.drop_index("ix_user_org_memberships_is_manager", table_name="user_org_memberships")
    op.drop_index("ix_user_org_memberships_job_code", table_name="user_org_memberships")
    op.drop_column("user_org_memberships", "is_manager")
    op.drop_column("user_org_memberships", "job_code")
    op.drop_column("user_org_memberships", "job_title")

    op.drop_index("ix_org_units_unit_type", table_name="org_units")
    op.drop_column("org_units", "unit_type")
