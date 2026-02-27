"""phase18 wp2 outcome version expand

Revision ID: 202602260074
Revises: 202602260073
Create Date: 2026-02-26
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "202602260074"
down_revision = "202602260073"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "outcome_catalog_versions",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("outcome_id", sa.String(), nullable=False),
        sa.Column("version_no", sa.Integer(), nullable=False),
        sa.Column("outcome_type", sa.String(length=30), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("point_lat", sa.Float(), nullable=True),
        sa.Column("point_lon", sa.Float(), nullable=True),
        sa.Column("alt_m", sa.Float(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column(
            "payload",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'{}'::json"),
        ),
        sa.Column(
            "change_type",
            sa.String(length=30),
            nullable=False,
            server_default="INIT_SNAPSHOT",
        ),
        sa.Column("change_note", sa.String(length=500), nullable=True),
        sa.Column("created_by", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["outcome_id"], ["outcome_catalog_records.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "id", name="uq_outcome_catalog_versions_tenant_id_id"),
        sa.UniqueConstraint(
            "tenant_id",
            "outcome_id",
            "version_no",
            name="uq_outcome_catalog_versions_outcome_version",
        ),
    )
    op.create_index("ix_outcome_catalog_versions_tenant_id", "outcome_catalog_versions", ["tenant_id"])
    op.create_index("ix_outcome_catalog_versions_outcome_id", "outcome_catalog_versions", ["outcome_id"])
    op.create_index("ix_outcome_catalog_versions_version_no", "outcome_catalog_versions", ["version_no"])
    op.create_index("ix_outcome_catalog_versions_status", "outcome_catalog_versions", ["status"])
    op.create_index("ix_outcome_catalog_versions_change_type", "outcome_catalog_versions", ["change_type"])
    op.create_index("ix_outcome_catalog_versions_created_by", "outcome_catalog_versions", ["created_by"])
    op.create_index("ix_outcome_catalog_versions_created_at", "outcome_catalog_versions", ["created_at"])
    op.create_index(
        "ix_outcome_catalog_versions_tenant_id_id",
        "outcome_catalog_versions",
        ["tenant_id", "id"],
    )
    op.create_index(
        "ix_outcome_catalog_versions_tenant_outcome",
        "outcome_catalog_versions",
        ["tenant_id", "outcome_id"],
    )
    op.create_index(
        "ix_outcome_catalog_versions_tenant_outcome_version",
        "outcome_catalog_versions",
        ["tenant_id", "outcome_id", "version_no"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_outcome_catalog_versions_tenant_outcome_version",
        table_name="outcome_catalog_versions",
    )
    op.drop_index(
        "ix_outcome_catalog_versions_tenant_outcome",
        table_name="outcome_catalog_versions",
    )
    op.drop_index(
        "ix_outcome_catalog_versions_tenant_id_id",
        table_name="outcome_catalog_versions",
    )
    op.drop_index("ix_outcome_catalog_versions_created_at", table_name="outcome_catalog_versions")
    op.drop_index("ix_outcome_catalog_versions_created_by", table_name="outcome_catalog_versions")
    op.drop_index("ix_outcome_catalog_versions_change_type", table_name="outcome_catalog_versions")
    op.drop_index("ix_outcome_catalog_versions_status", table_name="outcome_catalog_versions")
    op.drop_index("ix_outcome_catalog_versions_version_no", table_name="outcome_catalog_versions")
    op.drop_index("ix_outcome_catalog_versions_outcome_id", table_name="outcome_catalog_versions")
    op.drop_index("ix_outcome_catalog_versions_tenant_id", table_name="outcome_catalog_versions")
    op.drop_table("outcome_catalog_versions")
