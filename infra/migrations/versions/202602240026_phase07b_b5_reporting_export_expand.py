"""phase07b b5 reporting export expand

Revision ID: 202602240026
Revises: 202602240025
Create Date: 2026-02-24
"""

from __future__ import annotations

from alembic import op

# revision identifiers, used by Alembic.
revision = "202602240026"
down_revision = "202602240025"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_approval_records_tenant_id_id",
        "approval_records",
        ["tenant_id", "id"],
    )
    op.create_index(
        "ix_approval_records_tenant_id_id",
        "approval_records",
        ["tenant_id", "id"],
    )
    op.create_index(
        "ix_approval_records_tenant_approved_by",
        "approval_records",
        ["tenant_id", "approved_by"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_approval_records_tenant_approved_by",
        table_name="approval_records",
    )
    op.drop_index(
        "ix_approval_records_tenant_id_id",
        table_name="approval_records",
    )
    op.drop_constraint(
        "uq_approval_records_tenant_id_id",
        "approval_records",
        type_="unique",
    )
