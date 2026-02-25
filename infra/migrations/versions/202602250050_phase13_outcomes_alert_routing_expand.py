"""phase13 outcomes alert routing expand

Revision ID: 202602250050
Revises: 202602250049
Create Date: 2026-02-25
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "202602250050"
down_revision = "202602250049"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("alerts", sa.Column("priority_level", sa.String(length=10), nullable=True))
    op.add_column("alerts", sa.Column("route_status", sa.String(length=20), nullable=True))
    op.add_column("alerts", sa.Column("routed_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_alerts_priority_level", "alerts", ["priority_level"])
    op.create_index("ix_alerts_route_status", "alerts", ["route_status"])
    op.create_index("ix_alerts_routed_at", "alerts", ["routed_at"])

    op.create_table(
        "alert_routing_rules",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("priority_level", sa.String(length=10), nullable=False),
        sa.Column("alert_type", sa.String(length=50), nullable=True),
        sa.Column("channel", sa.String(length=20), nullable=False),
        sa.Column("target", sa.String(length=200), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("detail", sa.JSON(), nullable=False),
        sa.Column("created_by", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "id", name="uq_alert_routing_rules_tenant_id_id"),
    )
    op.create_index("ix_alert_routing_rules_tenant_id", "alert_routing_rules", ["tenant_id"])
    op.create_index("ix_alert_routing_rules_priority_level", "alert_routing_rules", ["priority_level"])
    op.create_index("ix_alert_routing_rules_alert_type", "alert_routing_rules", ["alert_type"])
    op.create_index("ix_alert_routing_rules_channel", "alert_routing_rules", ["channel"])
    op.create_index("ix_alert_routing_rules_is_active", "alert_routing_rules", ["is_active"])
    op.create_index("ix_alert_routing_rules_created_by", "alert_routing_rules", ["created_by"])
    op.create_index("ix_alert_routing_rules_created_at", "alert_routing_rules", ["created_at"])
    op.create_index("ix_alert_routing_rules_updated_at", "alert_routing_rules", ["updated_at"])
    op.create_index("ix_alert_routing_rules_tenant_id_id", "alert_routing_rules", ["tenant_id", "id"])
    op.create_index("ix_alert_routing_rules_tenant_priority", "alert_routing_rules", ["tenant_id", "priority_level"])
    op.create_index("ix_alert_routing_rules_tenant_type", "alert_routing_rules", ["tenant_id", "alert_type"])

    op.create_table(
        "alert_route_logs",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("alert_id", sa.String(), nullable=False),
        sa.Column("rule_id", sa.String(), nullable=True),
        sa.Column("priority_level", sa.String(length=10), nullable=False),
        sa.Column("channel", sa.String(length=20), nullable=False),
        sa.Column("target", sa.String(length=200), nullable=False),
        sa.Column("delivery_status", sa.String(length=20), nullable=False),
        sa.Column("detail", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "id", name="uq_alert_route_logs_tenant_id_id"),
    )
    op.create_index("ix_alert_route_logs_tenant_id", "alert_route_logs", ["tenant_id"])
    op.create_index("ix_alert_route_logs_alert_id", "alert_route_logs", ["alert_id"])
    op.create_index("ix_alert_route_logs_rule_id", "alert_route_logs", ["rule_id"])
    op.create_index("ix_alert_route_logs_priority_level", "alert_route_logs", ["priority_level"])
    op.create_index("ix_alert_route_logs_channel", "alert_route_logs", ["channel"])
    op.create_index("ix_alert_route_logs_delivery_status", "alert_route_logs", ["delivery_status"])
    op.create_index("ix_alert_route_logs_created_at", "alert_route_logs", ["created_at"])
    op.create_index("ix_alert_route_logs_tenant_id_id", "alert_route_logs", ["tenant_id", "id"])
    op.create_index("ix_alert_route_logs_tenant_alert", "alert_route_logs", ["tenant_id", "alert_id"])
    op.create_index("ix_alert_route_logs_tenant_priority", "alert_route_logs", ["tenant_id", "priority_level"])

    op.create_table(
        "raw_data_catalog_records",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("task_id", sa.String(), nullable=True),
        sa.Column("mission_id", sa.String(), nullable=True),
        sa.Column("data_type", sa.String(length=20), nullable=False),
        sa.Column("source_uri", sa.Text(), nullable=False),
        sa.Column("checksum", sa.String(length=200), nullable=True),
        sa.Column("meta", sa.JSON(), nullable=False),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "id", name="uq_raw_data_catalog_records_tenant_id_id"),
    )
    op.create_index("ix_raw_data_catalog_records_tenant_id", "raw_data_catalog_records", ["tenant_id"])
    op.create_index("ix_raw_data_catalog_records_task_id", "raw_data_catalog_records", ["task_id"])
    op.create_index("ix_raw_data_catalog_records_mission_id", "raw_data_catalog_records", ["mission_id"])
    op.create_index("ix_raw_data_catalog_records_data_type", "raw_data_catalog_records", ["data_type"])
    op.create_index("ix_raw_data_catalog_records_checksum", "raw_data_catalog_records", ["checksum"])
    op.create_index("ix_raw_data_catalog_records_captured_at", "raw_data_catalog_records", ["captured_at"])
    op.create_index("ix_raw_data_catalog_records_created_by", "raw_data_catalog_records", ["created_by"])
    op.create_index("ix_raw_data_catalog_records_created_at", "raw_data_catalog_records", ["created_at"])
    op.create_index("ix_raw_data_catalog_records_tenant_id_id", "raw_data_catalog_records", ["tenant_id", "id"])
    op.create_index("ix_raw_data_catalog_records_tenant_type", "raw_data_catalog_records", ["tenant_id", "data_type"])
    op.create_index("ix_raw_data_catalog_records_tenant_task", "raw_data_catalog_records", ["tenant_id", "task_id"])
    op.create_index("ix_raw_data_catalog_records_tenant_mission", "raw_data_catalog_records", ["tenant_id", "mission_id"])

    op.create_table(
        "outcome_catalog_records",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("task_id", sa.String(), nullable=True),
        sa.Column("mission_id", sa.String(), nullable=True),
        sa.Column("source_type", sa.String(length=40), nullable=False),
        sa.Column("source_id", sa.String(), nullable=False),
        sa.Column("outcome_type", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("point_lat", sa.Float(), nullable=True),
        sa.Column("point_lon", sa.Float(), nullable=True),
        sa.Column("alt_m", sa.Float(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("reviewed_by", sa.String(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "id", name="uq_outcome_catalog_records_tenant_id_id"),
    )
    op.create_index("ix_outcome_catalog_records_tenant_id", "outcome_catalog_records", ["tenant_id"])
    op.create_index("ix_outcome_catalog_records_task_id", "outcome_catalog_records", ["task_id"])
    op.create_index("ix_outcome_catalog_records_mission_id", "outcome_catalog_records", ["mission_id"])
    op.create_index("ix_outcome_catalog_records_source_type", "outcome_catalog_records", ["source_type"])
    op.create_index("ix_outcome_catalog_records_source_id", "outcome_catalog_records", ["source_id"])
    op.create_index("ix_outcome_catalog_records_outcome_type", "outcome_catalog_records", ["outcome_type"])
    op.create_index("ix_outcome_catalog_records_status", "outcome_catalog_records", ["status"])
    op.create_index("ix_outcome_catalog_records_reviewed_by", "outcome_catalog_records", ["reviewed_by"])
    op.create_index("ix_outcome_catalog_records_reviewed_at", "outcome_catalog_records", ["reviewed_at"])
    op.create_index("ix_outcome_catalog_records_created_by", "outcome_catalog_records", ["created_by"])
    op.create_index("ix_outcome_catalog_records_created_at", "outcome_catalog_records", ["created_at"])
    op.create_index("ix_outcome_catalog_records_updated_at", "outcome_catalog_records", ["updated_at"])
    op.create_index("ix_outcome_catalog_records_tenant_id_id", "outcome_catalog_records", ["tenant_id", "id"])
    op.create_index("ix_outcome_catalog_records_tenant_status", "outcome_catalog_records", ["tenant_id", "status"])
    op.create_index("ix_outcome_catalog_records_tenant_type", "outcome_catalog_records", ["tenant_id", "outcome_type"])
    op.create_index("ix_outcome_catalog_records_tenant_task", "outcome_catalog_records", ["tenant_id", "task_id"])
    op.create_index("ix_outcome_catalog_records_tenant_mission", "outcome_catalog_records", ["tenant_id", "mission_id"])
    op.create_index(
        "ix_outcome_catalog_records_tenant_source",
        "outcome_catalog_records",
        ["tenant_id", "source_type", "source_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_outcome_catalog_records_tenant_source", table_name="outcome_catalog_records")
    op.drop_index("ix_outcome_catalog_records_tenant_mission", table_name="outcome_catalog_records")
    op.drop_index("ix_outcome_catalog_records_tenant_task", table_name="outcome_catalog_records")
    op.drop_index("ix_outcome_catalog_records_tenant_type", table_name="outcome_catalog_records")
    op.drop_index("ix_outcome_catalog_records_tenant_status", table_name="outcome_catalog_records")
    op.drop_index("ix_outcome_catalog_records_tenant_id_id", table_name="outcome_catalog_records")
    op.drop_index("ix_outcome_catalog_records_updated_at", table_name="outcome_catalog_records")
    op.drop_index("ix_outcome_catalog_records_created_at", table_name="outcome_catalog_records")
    op.drop_index("ix_outcome_catalog_records_created_by", table_name="outcome_catalog_records")
    op.drop_index("ix_outcome_catalog_records_reviewed_at", table_name="outcome_catalog_records")
    op.drop_index("ix_outcome_catalog_records_reviewed_by", table_name="outcome_catalog_records")
    op.drop_index("ix_outcome_catalog_records_status", table_name="outcome_catalog_records")
    op.drop_index("ix_outcome_catalog_records_outcome_type", table_name="outcome_catalog_records")
    op.drop_index("ix_outcome_catalog_records_source_id", table_name="outcome_catalog_records")
    op.drop_index("ix_outcome_catalog_records_source_type", table_name="outcome_catalog_records")
    op.drop_index("ix_outcome_catalog_records_mission_id", table_name="outcome_catalog_records")
    op.drop_index("ix_outcome_catalog_records_task_id", table_name="outcome_catalog_records")
    op.drop_index("ix_outcome_catalog_records_tenant_id", table_name="outcome_catalog_records")
    op.drop_table("outcome_catalog_records")

    op.drop_index("ix_raw_data_catalog_records_tenant_mission", table_name="raw_data_catalog_records")
    op.drop_index("ix_raw_data_catalog_records_tenant_task", table_name="raw_data_catalog_records")
    op.drop_index("ix_raw_data_catalog_records_tenant_type", table_name="raw_data_catalog_records")
    op.drop_index("ix_raw_data_catalog_records_tenant_id_id", table_name="raw_data_catalog_records")
    op.drop_index("ix_raw_data_catalog_records_created_at", table_name="raw_data_catalog_records")
    op.drop_index("ix_raw_data_catalog_records_created_by", table_name="raw_data_catalog_records")
    op.drop_index("ix_raw_data_catalog_records_captured_at", table_name="raw_data_catalog_records")
    op.drop_index("ix_raw_data_catalog_records_checksum", table_name="raw_data_catalog_records")
    op.drop_index("ix_raw_data_catalog_records_data_type", table_name="raw_data_catalog_records")
    op.drop_index("ix_raw_data_catalog_records_mission_id", table_name="raw_data_catalog_records")
    op.drop_index("ix_raw_data_catalog_records_task_id", table_name="raw_data_catalog_records")
    op.drop_index("ix_raw_data_catalog_records_tenant_id", table_name="raw_data_catalog_records")
    op.drop_table("raw_data_catalog_records")

    op.drop_index("ix_alert_route_logs_tenant_priority", table_name="alert_route_logs")
    op.drop_index("ix_alert_route_logs_tenant_alert", table_name="alert_route_logs")
    op.drop_index("ix_alert_route_logs_tenant_id_id", table_name="alert_route_logs")
    op.drop_index("ix_alert_route_logs_created_at", table_name="alert_route_logs")
    op.drop_index("ix_alert_route_logs_delivery_status", table_name="alert_route_logs")
    op.drop_index("ix_alert_route_logs_channel", table_name="alert_route_logs")
    op.drop_index("ix_alert_route_logs_priority_level", table_name="alert_route_logs")
    op.drop_index("ix_alert_route_logs_rule_id", table_name="alert_route_logs")
    op.drop_index("ix_alert_route_logs_alert_id", table_name="alert_route_logs")
    op.drop_index("ix_alert_route_logs_tenant_id", table_name="alert_route_logs")
    op.drop_table("alert_route_logs")

    op.drop_index("ix_alert_routing_rules_tenant_type", table_name="alert_routing_rules")
    op.drop_index("ix_alert_routing_rules_tenant_priority", table_name="alert_routing_rules")
    op.drop_index("ix_alert_routing_rules_tenant_id_id", table_name="alert_routing_rules")
    op.drop_index("ix_alert_routing_rules_updated_at", table_name="alert_routing_rules")
    op.drop_index("ix_alert_routing_rules_created_at", table_name="alert_routing_rules")
    op.drop_index("ix_alert_routing_rules_created_by", table_name="alert_routing_rules")
    op.drop_index("ix_alert_routing_rules_is_active", table_name="alert_routing_rules")
    op.drop_index("ix_alert_routing_rules_channel", table_name="alert_routing_rules")
    op.drop_index("ix_alert_routing_rules_alert_type", table_name="alert_routing_rules")
    op.drop_index("ix_alert_routing_rules_priority_level", table_name="alert_routing_rules")
    op.drop_index("ix_alert_routing_rules_tenant_id", table_name="alert_routing_rules")
    op.drop_table("alert_routing_rules")

    op.drop_index("ix_alerts_routed_at", table_name="alerts")
    op.drop_index("ix_alerts_route_status", table_name="alerts")
    op.drop_index("ix_alerts_priority_level", table_name="alerts")
    op.drop_column("alerts", "routed_at")
    op.drop_column("alerts", "route_status")
    op.drop_column("alerts", "priority_level")
