"""phase15 kpi open platform expand

Revision ID: 202602250059
Revises: 202602250058
Create Date: 2026-02-25
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "202602250059"
down_revision = "202602250058"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "kpi_snapshot_records",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("window_type", sa.String(length=20), nullable=False),
        sa.Column("from_ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("to_ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("metrics", sa.JSON(), nullable=False),
        sa.Column("generated_by", sa.String(), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "id", name="uq_kpi_snapshot_records_tenant_id_id"),
    )
    op.create_index("ix_kpi_snapshot_records_tenant_id", "kpi_snapshot_records", ["tenant_id"])
    op.create_index("ix_kpi_snapshot_records_window_type", "kpi_snapshot_records", ["window_type"])
    op.create_index("ix_kpi_snapshot_records_from_ts", "kpi_snapshot_records", ["from_ts"])
    op.create_index("ix_kpi_snapshot_records_to_ts", "kpi_snapshot_records", ["to_ts"])
    op.create_index("ix_kpi_snapshot_records_generated_by", "kpi_snapshot_records", ["generated_by"])
    op.create_index("ix_kpi_snapshot_records_generated_at", "kpi_snapshot_records", ["generated_at"])
    op.create_index("ix_kpi_snapshot_records_tenant_id_id", "kpi_snapshot_records", ["tenant_id", "id"])
    op.create_index(
        "ix_kpi_snapshot_records_tenant_window",
        "kpi_snapshot_records",
        ["tenant_id", "window_type"],
    )
    op.create_index(
        "ix_kpi_snapshot_records_tenant_period",
        "kpi_snapshot_records",
        ["tenant_id", "from_ts", "to_ts"],
    )

    op.create_table(
        "kpi_heatmap_bin_records",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("snapshot_id", sa.String(), nullable=False),
        sa.Column("source", sa.String(length=20), nullable=False),
        sa.Column("grid_lat", sa.Float(), nullable=False),
        sa.Column("grid_lon", sa.Float(), nullable=False),
        sa.Column("count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("detail", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["snapshot_id"], ["kpi_snapshot_records.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "id", name="uq_kpi_heatmap_bin_records_tenant_id_id"),
    )
    op.create_index("ix_kpi_heatmap_bin_records_tenant_id", "kpi_heatmap_bin_records", ["tenant_id"])
    op.create_index("ix_kpi_heatmap_bin_records_snapshot_id", "kpi_heatmap_bin_records", ["snapshot_id"])
    op.create_index("ix_kpi_heatmap_bin_records_source", "kpi_heatmap_bin_records", ["source"])
    op.create_index("ix_kpi_heatmap_bin_records_grid_lat", "kpi_heatmap_bin_records", ["grid_lat"])
    op.create_index("ix_kpi_heatmap_bin_records_grid_lon", "kpi_heatmap_bin_records", ["grid_lon"])
    op.create_index("ix_kpi_heatmap_bin_records_created_at", "kpi_heatmap_bin_records", ["created_at"])
    op.create_index(
        "ix_kpi_heatmap_bin_records_tenant_id_id",
        "kpi_heatmap_bin_records",
        ["tenant_id", "id"],
    )
    op.create_index(
        "ix_kpi_heatmap_bin_records_tenant_snapshot",
        "kpi_heatmap_bin_records",
        ["tenant_id", "snapshot_id"],
    )
    op.create_index(
        "ix_kpi_heatmap_bin_records_tenant_source",
        "kpi_heatmap_bin_records",
        ["tenant_id", "source"],
    )

    op.create_table(
        "open_platform_credentials",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("key_id", sa.String(length=120), nullable=False),
        sa.Column("api_key", sa.String(length=200), nullable=False),
        sa.Column("signing_secret", sa.String(length=200), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_by", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "id", name="uq_open_platform_credentials_tenant_id_id"),
        sa.UniqueConstraint("tenant_id", "key_id", name="uq_open_platform_credentials_tenant_key"),
    )
    op.create_index("ix_open_platform_credentials_tenant_id", "open_platform_credentials", ["tenant_id"])
    op.create_index("ix_open_platform_credentials_key_id", "open_platform_credentials", ["key_id"])
    op.create_index("ix_open_platform_credentials_api_key", "open_platform_credentials", ["api_key"])
    op.create_index("ix_open_platform_credentials_is_active", "open_platform_credentials", ["is_active"])
    op.create_index("ix_open_platform_credentials_created_by", "open_platform_credentials", ["created_by"])
    op.create_index("ix_open_platform_credentials_created_at", "open_platform_credentials", ["created_at"])
    op.create_index("ix_open_platform_credentials_updated_at", "open_platform_credentials", ["updated_at"])
    op.create_index(
        "ix_open_platform_credentials_tenant_id_id",
        "open_platform_credentials",
        ["tenant_id", "id"],
    )
    op.create_index(
        "ix_open_platform_credentials_tenant_key",
        "open_platform_credentials",
        ["tenant_id", "key_id"],
    )

    op.create_table(
        "open_webhook_endpoints",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("endpoint_url", sa.Text(), nullable=False),
        sa.Column("event_type", sa.String(length=120), nullable=False),
        sa.Column("credential_id", sa.String(), nullable=True),
        sa.Column("auth_type", sa.String(length=30), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("extra_headers", sa.JSON(), nullable=False),
        sa.Column("created_by", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["credential_id"], ["open_platform_credentials.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "id", name="uq_open_webhook_endpoints_tenant_id_id"),
    )
    op.create_index("ix_open_webhook_endpoints_tenant_id", "open_webhook_endpoints", ["tenant_id"])
    op.create_index("ix_open_webhook_endpoints_name", "open_webhook_endpoints", ["name"])
    op.create_index("ix_open_webhook_endpoints_event_type", "open_webhook_endpoints", ["event_type"])
    op.create_index("ix_open_webhook_endpoints_credential_id", "open_webhook_endpoints", ["credential_id"])
    op.create_index("ix_open_webhook_endpoints_auth_type", "open_webhook_endpoints", ["auth_type"])
    op.create_index("ix_open_webhook_endpoints_is_active", "open_webhook_endpoints", ["is_active"])
    op.create_index("ix_open_webhook_endpoints_created_by", "open_webhook_endpoints", ["created_by"])
    op.create_index("ix_open_webhook_endpoints_created_at", "open_webhook_endpoints", ["created_at"])
    op.create_index("ix_open_webhook_endpoints_updated_at", "open_webhook_endpoints", ["updated_at"])
    op.create_index("ix_open_webhook_endpoints_tenant_id_id", "open_webhook_endpoints", ["tenant_id", "id"])
    op.create_index(
        "ix_open_webhook_endpoints_tenant_event",
        "open_webhook_endpoints",
        ["tenant_id", "event_type"],
    )

    op.create_table(
        "open_webhook_deliveries",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("endpoint_id", sa.String(), nullable=False),
        sa.Column("event_type", sa.String(length=120), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("signature", sa.String(length=200), nullable=True),
        sa.Column("request_headers", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("detail", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["endpoint_id"], ["open_webhook_endpoints.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "id", name="uq_open_webhook_deliveries_tenant_id_id"),
    )
    op.create_index("ix_open_webhook_deliveries_tenant_id", "open_webhook_deliveries", ["tenant_id"])
    op.create_index("ix_open_webhook_deliveries_endpoint_id", "open_webhook_deliveries", ["endpoint_id"])
    op.create_index("ix_open_webhook_deliveries_event_type", "open_webhook_deliveries", ["event_type"])
    op.create_index("ix_open_webhook_deliveries_signature", "open_webhook_deliveries", ["signature"])
    op.create_index("ix_open_webhook_deliveries_status", "open_webhook_deliveries", ["status"])
    op.create_index("ix_open_webhook_deliveries_created_at", "open_webhook_deliveries", ["created_at"])
    op.create_index(
        "ix_open_webhook_deliveries_tenant_id_id",
        "open_webhook_deliveries",
        ["tenant_id", "id"],
    )
    op.create_index(
        "ix_open_webhook_deliveries_tenant_endpoint",
        "open_webhook_deliveries",
        ["tenant_id", "endpoint_id"],
    )

    op.create_table(
        "open_adapter_ingress_events",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("key_id", sa.String(length=120), nullable=False),
        sa.Column("event_type", sa.String(length=120), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("signature_valid", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("detail", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "id", name="uq_open_adapter_ingress_events_tenant_id_id"),
    )
    op.create_index("ix_open_adapter_ingress_events_tenant_id", "open_adapter_ingress_events", ["tenant_id"])
    op.create_index("ix_open_adapter_ingress_events_key_id", "open_adapter_ingress_events", ["key_id"])
    op.create_index("ix_open_adapter_ingress_events_event_type", "open_adapter_ingress_events", ["event_type"])
    op.create_index(
        "ix_open_adapter_ingress_events_signature_valid",
        "open_adapter_ingress_events",
        ["signature_valid"],
    )
    op.create_index("ix_open_adapter_ingress_events_status", "open_adapter_ingress_events", ["status"])
    op.create_index("ix_open_adapter_ingress_events_created_at", "open_adapter_ingress_events", ["created_at"])
    op.create_index(
        "ix_open_adapter_ingress_events_tenant_id_id",
        "open_adapter_ingress_events",
        ["tenant_id", "id"],
    )
    op.create_index(
        "ix_open_adapter_ingress_events_tenant_key",
        "open_adapter_ingress_events",
        ["tenant_id", "key_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_open_adapter_ingress_events_tenant_key", table_name="open_adapter_ingress_events")
    op.drop_index("ix_open_adapter_ingress_events_tenant_id_id", table_name="open_adapter_ingress_events")
    op.drop_index("ix_open_adapter_ingress_events_created_at", table_name="open_adapter_ingress_events")
    op.drop_index("ix_open_adapter_ingress_events_status", table_name="open_adapter_ingress_events")
    op.drop_index("ix_open_adapter_ingress_events_signature_valid", table_name="open_adapter_ingress_events")
    op.drop_index("ix_open_adapter_ingress_events_event_type", table_name="open_adapter_ingress_events")
    op.drop_index("ix_open_adapter_ingress_events_key_id", table_name="open_adapter_ingress_events")
    op.drop_index("ix_open_adapter_ingress_events_tenant_id", table_name="open_adapter_ingress_events")
    op.drop_table("open_adapter_ingress_events")

    op.drop_index("ix_open_webhook_deliveries_tenant_endpoint", table_name="open_webhook_deliveries")
    op.drop_index("ix_open_webhook_deliveries_tenant_id_id", table_name="open_webhook_deliveries")
    op.drop_index("ix_open_webhook_deliveries_created_at", table_name="open_webhook_deliveries")
    op.drop_index("ix_open_webhook_deliveries_status", table_name="open_webhook_deliveries")
    op.drop_index("ix_open_webhook_deliveries_signature", table_name="open_webhook_deliveries")
    op.drop_index("ix_open_webhook_deliveries_event_type", table_name="open_webhook_deliveries")
    op.drop_index("ix_open_webhook_deliveries_endpoint_id", table_name="open_webhook_deliveries")
    op.drop_index("ix_open_webhook_deliveries_tenant_id", table_name="open_webhook_deliveries")
    op.drop_table("open_webhook_deliveries")

    op.drop_index("ix_open_webhook_endpoints_tenant_event", table_name="open_webhook_endpoints")
    op.drop_index("ix_open_webhook_endpoints_tenant_id_id", table_name="open_webhook_endpoints")
    op.drop_index("ix_open_webhook_endpoints_updated_at", table_name="open_webhook_endpoints")
    op.drop_index("ix_open_webhook_endpoints_created_at", table_name="open_webhook_endpoints")
    op.drop_index("ix_open_webhook_endpoints_created_by", table_name="open_webhook_endpoints")
    op.drop_index("ix_open_webhook_endpoints_is_active", table_name="open_webhook_endpoints")
    op.drop_index("ix_open_webhook_endpoints_auth_type", table_name="open_webhook_endpoints")
    op.drop_index("ix_open_webhook_endpoints_credential_id", table_name="open_webhook_endpoints")
    op.drop_index("ix_open_webhook_endpoints_event_type", table_name="open_webhook_endpoints")
    op.drop_index("ix_open_webhook_endpoints_name", table_name="open_webhook_endpoints")
    op.drop_index("ix_open_webhook_endpoints_tenant_id", table_name="open_webhook_endpoints")
    op.drop_table("open_webhook_endpoints")

    op.drop_index("ix_open_platform_credentials_tenant_key", table_name="open_platform_credentials")
    op.drop_index("ix_open_platform_credentials_tenant_id_id", table_name="open_platform_credentials")
    op.drop_index("ix_open_platform_credentials_updated_at", table_name="open_platform_credentials")
    op.drop_index("ix_open_platform_credentials_created_at", table_name="open_platform_credentials")
    op.drop_index("ix_open_platform_credentials_created_by", table_name="open_platform_credentials")
    op.drop_index("ix_open_platform_credentials_is_active", table_name="open_platform_credentials")
    op.drop_index("ix_open_platform_credentials_api_key", table_name="open_platform_credentials")
    op.drop_index("ix_open_platform_credentials_key_id", table_name="open_platform_credentials")
    op.drop_index("ix_open_platform_credentials_tenant_id", table_name="open_platform_credentials")
    op.drop_table("open_platform_credentials")

    op.drop_index("ix_kpi_heatmap_bin_records_tenant_source", table_name="kpi_heatmap_bin_records")
    op.drop_index("ix_kpi_heatmap_bin_records_tenant_snapshot", table_name="kpi_heatmap_bin_records")
    op.drop_index("ix_kpi_heatmap_bin_records_tenant_id_id", table_name="kpi_heatmap_bin_records")
    op.drop_index("ix_kpi_heatmap_bin_records_created_at", table_name="kpi_heatmap_bin_records")
    op.drop_index("ix_kpi_heatmap_bin_records_grid_lon", table_name="kpi_heatmap_bin_records")
    op.drop_index("ix_kpi_heatmap_bin_records_grid_lat", table_name="kpi_heatmap_bin_records")
    op.drop_index("ix_kpi_heatmap_bin_records_source", table_name="kpi_heatmap_bin_records")
    op.drop_index("ix_kpi_heatmap_bin_records_snapshot_id", table_name="kpi_heatmap_bin_records")
    op.drop_index("ix_kpi_heatmap_bin_records_tenant_id", table_name="kpi_heatmap_bin_records")
    op.drop_table("kpi_heatmap_bin_records")

    op.drop_index("ix_kpi_snapshot_records_tenant_period", table_name="kpi_snapshot_records")
    op.drop_index("ix_kpi_snapshot_records_tenant_window", table_name="kpi_snapshot_records")
    op.drop_index("ix_kpi_snapshot_records_tenant_id_id", table_name="kpi_snapshot_records")
    op.drop_index("ix_kpi_snapshot_records_generated_at", table_name="kpi_snapshot_records")
    op.drop_index("ix_kpi_snapshot_records_generated_by", table_name="kpi_snapshot_records")
    op.drop_index("ix_kpi_snapshot_records_to_ts", table_name="kpi_snapshot_records")
    op.drop_index("ix_kpi_snapshot_records_from_ts", table_name="kpi_snapshot_records")
    op.drop_index("ix_kpi_snapshot_records_window_type", table_name="kpi_snapshot_records")
    op.drop_index("ix_kpi_snapshot_records_tenant_id", table_name="kpi_snapshot_records")
    op.drop_table("kpi_snapshot_records")
