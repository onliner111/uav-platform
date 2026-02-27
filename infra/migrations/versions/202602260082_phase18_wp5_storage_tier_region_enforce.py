"""phase18 wp5 storage tier region enforce

Revision ID: 202602260082
Revises: 202602260081
Create Date: 2026-02-26
"""

from __future__ import annotations

from alembic import op

# revision identifiers, used by Alembic.
revision = "202602260082"
down_revision = "202602260081"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_check_constraint(
        "ck_raw_data_catalog_records_access_tier",
        "raw_data_catalog_records",
        "access_tier IN ('HOT', 'WARM', 'COLD')",
    )
    op.create_check_constraint(
        "ck_raw_data_catalog_records_storage_region",
        "raw_data_catalog_records",
        "storage_region IS NULL OR storage_region <> ''",
    )
    op.create_check_constraint(
        "ck_raw_upload_sessions_storage_region",
        "raw_upload_sessions",
        "storage_region <> ''",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_raw_upload_sessions_storage_region",
        "raw_upload_sessions",
        type_="check",
    )
    op.drop_constraint(
        "ck_raw_data_catalog_records_storage_region",
        "raw_data_catalog_records",
        type_="check",
    )
    op.drop_constraint(
        "ck_raw_data_catalog_records_access_tier",
        "raw_data_catalog_records",
        type_="check",
    )
