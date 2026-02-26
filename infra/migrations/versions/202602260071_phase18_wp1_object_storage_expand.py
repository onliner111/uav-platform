"""phase18 wp1 object storage expand

Revision ID: 202602260071
Revises: 202602260070
Create Date: 2026-02-26
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "202602260071"
down_revision = "202602260070"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("raw_data_catalog_records", sa.Column("bucket", sa.String(length=120), nullable=True))
    op.add_column("raw_data_catalog_records", sa.Column("object_key", sa.String(length=500), nullable=True))
    op.add_column("raw_data_catalog_records", sa.Column("object_version", sa.String(length=120), nullable=True))
    op.add_column("raw_data_catalog_records", sa.Column("size_bytes", sa.BigInteger(), nullable=True))
    op.add_column("raw_data_catalog_records", sa.Column("content_type", sa.String(length=120), nullable=True))
    op.add_column("raw_data_catalog_records", sa.Column("storage_class", sa.String(length=50), nullable=True))
    op.add_column("raw_data_catalog_records", sa.Column("etag", sa.String(length=200), nullable=True))
    op.create_index("ix_raw_data_catalog_records_bucket", "raw_data_catalog_records", ["bucket"])
    op.create_index("ix_raw_data_catalog_records_etag", "raw_data_catalog_records", ["etag"])
    op.create_index(
        "ix_raw_data_catalog_records_tenant_bucket_key",
        "raw_data_catalog_records",
        ["tenant_id", "bucket", "object_key"],
    )

    op.create_table(
        "raw_upload_sessions",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("task_id", sa.String(), nullable=True),
        sa.Column("mission_id", sa.String(), nullable=True),
        sa.Column("data_type", sa.String(length=20), nullable=False),
        sa.Column("file_name", sa.String(length=200), nullable=False),
        sa.Column("content_type", sa.String(length=120), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("checksum", sa.String(length=200), nullable=True),
        sa.Column(
            "meta",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'{}'::json"),
        ),
        sa.Column("bucket", sa.String(length=120), nullable=False),
        sa.Column("object_key", sa.String(length=500), nullable=False),
        sa.Column(
            "storage_class",
            sa.String(length=50),
            nullable=False,
            server_default="STANDARD",
        ),
        sa.Column(
            "status",
            sa.String(length=20),
            nullable=False,
            server_default="INITIATED",
        ),
        sa.Column("upload_token", sa.String(length=120), nullable=False),
        sa.Column("etag", sa.String(length=200), nullable=True),
        sa.Column("completed_raw_id", sa.String(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["tenant_id", "task_id"],
            ["inspection_tasks.tenant_id", "inspection_tasks.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "mission_id"],
            ["missions.tenant_id", "missions.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(["completed_raw_id"], ["raw_data_catalog_records.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "id", name="uq_raw_upload_sessions_tenant_id_id"),
        sa.UniqueConstraint("upload_token", name="uq_raw_upload_sessions_upload_token"),
    )
    op.create_index("ix_raw_upload_sessions_tenant_id", "raw_upload_sessions", ["tenant_id"])
    op.create_index("ix_raw_upload_sessions_task_id", "raw_upload_sessions", ["task_id"])
    op.create_index("ix_raw_upload_sessions_mission_id", "raw_upload_sessions", ["mission_id"])
    op.create_index("ix_raw_upload_sessions_data_type", "raw_upload_sessions", ["data_type"])
    op.create_index("ix_raw_upload_sessions_status", "raw_upload_sessions", ["status"])
    op.create_index("ix_raw_upload_sessions_upload_token", "raw_upload_sessions", ["upload_token"])
    op.create_index("ix_raw_upload_sessions_checksum", "raw_upload_sessions", ["checksum"])
    op.create_index("ix_raw_upload_sessions_bucket", "raw_upload_sessions", ["bucket"])
    op.create_index("ix_raw_upload_sessions_expires_at", "raw_upload_sessions", ["expires_at"])
    op.create_index("ix_raw_upload_sessions_completed_raw_id", "raw_upload_sessions", ["completed_raw_id"])
    op.create_index("ix_raw_upload_sessions_created_by", "raw_upload_sessions", ["created_by"])
    op.create_index("ix_raw_upload_sessions_created_at", "raw_upload_sessions", ["created_at"])
    op.create_index("ix_raw_upload_sessions_updated_at", "raw_upload_sessions", ["updated_at"])
    op.create_index(
        "ix_raw_upload_sessions_tenant_id_id",
        "raw_upload_sessions",
        ["tenant_id", "id"],
    )
    op.create_index(
        "ix_raw_upload_sessions_tenant_status",
        "raw_upload_sessions",
        ["tenant_id", "status"],
    )
    op.create_index(
        "ix_raw_upload_sessions_tenant_created_at",
        "raw_upload_sessions",
        ["tenant_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_raw_upload_sessions_tenant_created_at", table_name="raw_upload_sessions")
    op.drop_index("ix_raw_upload_sessions_tenant_status", table_name="raw_upload_sessions")
    op.drop_index("ix_raw_upload_sessions_tenant_id_id", table_name="raw_upload_sessions")
    op.drop_index("ix_raw_upload_sessions_updated_at", table_name="raw_upload_sessions")
    op.drop_index("ix_raw_upload_sessions_created_at", table_name="raw_upload_sessions")
    op.drop_index("ix_raw_upload_sessions_created_by", table_name="raw_upload_sessions")
    op.drop_index("ix_raw_upload_sessions_completed_raw_id", table_name="raw_upload_sessions")
    op.drop_index("ix_raw_upload_sessions_expires_at", table_name="raw_upload_sessions")
    op.drop_index("ix_raw_upload_sessions_bucket", table_name="raw_upload_sessions")
    op.drop_index("ix_raw_upload_sessions_checksum", table_name="raw_upload_sessions")
    op.drop_index("ix_raw_upload_sessions_upload_token", table_name="raw_upload_sessions")
    op.drop_index("ix_raw_upload_sessions_status", table_name="raw_upload_sessions")
    op.drop_index("ix_raw_upload_sessions_data_type", table_name="raw_upload_sessions")
    op.drop_index("ix_raw_upload_sessions_mission_id", table_name="raw_upload_sessions")
    op.drop_index("ix_raw_upload_sessions_task_id", table_name="raw_upload_sessions")
    op.drop_index("ix_raw_upload_sessions_tenant_id", table_name="raw_upload_sessions")
    op.drop_table("raw_upload_sessions")

    op.drop_index("ix_raw_data_catalog_records_tenant_bucket_key", table_name="raw_data_catalog_records")
    op.drop_index("ix_raw_data_catalog_records_etag", table_name="raw_data_catalog_records")
    op.drop_index("ix_raw_data_catalog_records_bucket", table_name="raw_data_catalog_records")
    op.drop_column("raw_data_catalog_records", "etag")
    op.drop_column("raw_data_catalog_records", "storage_class")
    op.drop_column("raw_data_catalog_records", "content_type")
    op.drop_column("raw_data_catalog_records", "size_bytes")
    op.drop_column("raw_data_catalog_records", "object_version")
    op.drop_column("raw_data_catalog_records", "object_key")
    op.drop_column("raw_data_catalog_records", "bucket")
