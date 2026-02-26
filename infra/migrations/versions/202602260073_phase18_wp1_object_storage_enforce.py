"""phase18 wp1 object storage enforce

Revision ID: 202602260073
Revises: 202602260072
Create Date: 2026-02-26
"""

from __future__ import annotations

from alembic import op

# revision identifiers, used by Alembic.
revision = "202602260073"
down_revision = "202602260072"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_check_constraint(
        "ck_raw_data_catalog_records_bucket_object_pair",
        "raw_data_catalog_records",
        "(bucket IS NULL AND object_key IS NULL) OR (bucket IS NOT NULL AND object_key IS NOT NULL)",
    )
    op.create_check_constraint(
        "ck_raw_data_catalog_records_size_bytes_non_negative",
        "raw_data_catalog_records",
        "size_bytes IS NULL OR size_bytes >= 0",
    )
    op.create_check_constraint(
        "ck_raw_upload_sessions_status",
        "raw_upload_sessions",
        "status IN ('INITIATED', 'UPLOADED', 'COMPLETED', 'EXPIRED')",
    )
    op.create_check_constraint(
        "ck_raw_upload_sessions_size_bytes_positive",
        "raw_upload_sessions",
        "size_bytes > 0",
    )
    op.create_check_constraint(
        "ck_raw_upload_sessions_meta_is_object",
        "raw_upload_sessions",
        "json_typeof(meta) = 'object'",
    )
    op.create_check_constraint(
        "ck_raw_upload_sessions_completed_requires_status",
        "raw_upload_sessions",
        "completed_raw_id IS NULL OR status = 'COMPLETED'",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_raw_upload_sessions_completed_requires_status",
        "raw_upload_sessions",
        type_="check",
    )
    op.drop_constraint(
        "ck_raw_upload_sessions_meta_is_object",
        "raw_upload_sessions",
        type_="check",
    )
    op.drop_constraint(
        "ck_raw_upload_sessions_size_bytes_positive",
        "raw_upload_sessions",
        type_="check",
    )
    op.drop_constraint(
        "ck_raw_upload_sessions_status",
        "raw_upload_sessions",
        type_="check",
    )
    op.drop_constraint(
        "ck_raw_data_catalog_records_size_bytes_non_negative",
        "raw_data_catalog_records",
        type_="check",
    )
    op.drop_constraint(
        "ck_raw_data_catalog_records_bucket_object_pair",
        "raw_data_catalog_records",
        type_="check",
    )
