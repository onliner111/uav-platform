"""phase18 wp5 storage tier region expand

Revision ID: 202602260080
Revises: 202602260079
Create Date: 2026-02-26
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "202602260080"
down_revision = "202602260079"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("raw_data_catalog_records", sa.Column("storage_region", sa.String(length=50), nullable=True))
    op.add_column(
        "raw_data_catalog_records",
        sa.Column("access_tier", sa.String(length=20), nullable=False, server_default="HOT"),
    )
    op.create_index("ix_raw_data_catalog_records_storage_region", "raw_data_catalog_records", ["storage_region"])
    op.create_index("ix_raw_data_catalog_records_access_tier", "raw_data_catalog_records", ["access_tier"])

    op.add_column(
        "raw_upload_sessions",
        sa.Column("storage_region", sa.String(length=50), nullable=False, server_default="local"),
    )
    op.create_index("ix_raw_upload_sessions_storage_region", "raw_upload_sessions", ["storage_region"])


def downgrade() -> None:
    op.drop_index("ix_raw_upload_sessions_storage_region", table_name="raw_upload_sessions")
    op.drop_column("raw_upload_sessions", "storage_region")

    op.drop_index("ix_raw_data_catalog_records_access_tier", table_name="raw_data_catalog_records")
    op.drop_index("ix_raw_data_catalog_records_storage_region", table_name="raw_data_catalog_records")
    op.drop_column("raw_data_catalog_records", "access_tier")
    op.drop_column("raw_data_catalog_records", "storage_region")
