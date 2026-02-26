"""phase17 wp2 data perimeter resource enforce

Revision ID: 202602260067
Revises: 202602260066
Create Date: 2026-02-26
"""

from __future__ import annotations

from alembic import op

# revision identifiers, used by Alembic.
revision = "202602260067"
down_revision = "202602260066"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_check_constraint(
        "ck_data_access_policies_resource_ids_is_array",
        "data_access_policies",
        "json_typeof(resource_ids) = 'array'",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_data_access_policies_resource_ids_is_array",
        "data_access_policies",
        type_="check",
    )
