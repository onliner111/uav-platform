"""phase15 kpi open platform enforce

Revision ID: 202602250061
Revises: 202602250060
Create Date: 2026-02-25
"""

from __future__ import annotations

from alembic import op

# revision identifiers, used by Alembic.
revision = "202602250061"
down_revision = "202602250060"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_check_constraint(
        "ck_kpi_snapshot_records_window_type",
        "kpi_snapshot_records",
        "window_type IN ('DAILY', 'WEEKLY', 'MONTHLY', 'QUARTERLY', 'CUSTOM')",
    )
    op.create_check_constraint(
        "ck_kpi_snapshot_records_period",
        "kpi_snapshot_records",
        "to_ts > from_ts",
    )
    op.create_check_constraint(
        "ck_kpi_heatmap_bin_records_source",
        "kpi_heatmap_bin_records",
        "source IN ('OUTCOME', 'ALERT')",
    )
    op.create_check_constraint(
        "ck_kpi_heatmap_bin_records_count",
        "kpi_heatmap_bin_records",
        "count >= 0",
    )
    op.create_check_constraint(
        "ck_open_webhook_endpoints_auth_type",
        "open_webhook_endpoints",
        "auth_type IN ('HMAC_SHA256')",
    )
    op.create_check_constraint(
        "ck_open_webhook_deliveries_status",
        "open_webhook_deliveries",
        "status IN ('SENT', 'FAILED', 'SKIPPED')",
    )
    op.create_check_constraint(
        "ck_open_adapter_ingress_events_status",
        "open_adapter_ingress_events",
        "status IN ('ACCEPTED', 'REJECTED')",
    )

    op.create_foreign_key(
        "fk_kpi_heatmap_bin_records_tenant_snapshot",
        "kpi_heatmap_bin_records",
        "kpi_snapshot_records",
        ["tenant_id", "snapshot_id"],
        ["tenant_id", "id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_open_webhook_endpoints_tenant_credential",
        "open_webhook_endpoints",
        "open_platform_credentials",
        ["tenant_id", "credential_id"],
        ["tenant_id", "id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_open_webhook_deliveries_tenant_endpoint",
        "open_webhook_deliveries",
        "open_webhook_endpoints",
        ["tenant_id", "endpoint_id"],
        ["tenant_id", "id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_open_adapter_ingress_events_tenant_key",
        "open_adapter_ingress_events",
        "open_platform_credentials",
        ["tenant_id", "key_id"],
        ["tenant_id", "key_id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_open_adapter_ingress_events_tenant_key",
        "open_adapter_ingress_events",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_open_webhook_deliveries_tenant_endpoint",
        "open_webhook_deliveries",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_open_webhook_endpoints_tenant_credential",
        "open_webhook_endpoints",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_kpi_heatmap_bin_records_tenant_snapshot",
        "kpi_heatmap_bin_records",
        type_="foreignkey",
    )

    op.drop_constraint(
        "ck_open_adapter_ingress_events_status",
        "open_adapter_ingress_events",
        type_="check",
    )
    op.drop_constraint(
        "ck_open_webhook_deliveries_status",
        "open_webhook_deliveries",
        type_="check",
    )
    op.drop_constraint(
        "ck_open_webhook_endpoints_auth_type",
        "open_webhook_endpoints",
        type_="check",
    )
    op.drop_constraint(
        "ck_kpi_heatmap_bin_records_count",
        "kpi_heatmap_bin_records",
        type_="check",
    )
    op.drop_constraint(
        "ck_kpi_heatmap_bin_records_source",
        "kpi_heatmap_bin_records",
        type_="check",
    )
    op.drop_constraint(
        "ck_kpi_snapshot_records_period",
        "kpi_snapshot_records",
        type_="check",
    )
    op.drop_constraint(
        "ck_kpi_snapshot_records_window_type",
        "kpi_snapshot_records",
        type_="check",
    )
