"""phase13 outcomes alert routing enforce

Revision ID: 202602250052
Revises: 202602250051
Create Date: 2026-02-25
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "202602250052"
down_revision = "202602250051"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("alerts", "priority_level", existing_type=sa.String(length=10), nullable=False)
    op.alter_column("alerts", "route_status", existing_type=sa.String(length=20), nullable=False)

    op.create_unique_constraint("uq_alerts_tenant_id_id", "alerts", ["tenant_id", "id"])
    op.create_index("ix_alerts_tenant_id_id", "alerts", ["tenant_id", "id"])

    op.create_check_constraint(
        "ck_alerts_priority_level",
        "alerts",
        "priority_level IN ('P1', 'P2', 'P3')",
    )
    op.create_check_constraint(
        "ck_alerts_route_status",
        "alerts",
        "route_status IN ('UNROUTED', 'ROUTED')",
    )
    op.create_check_constraint(
        "ck_alert_routing_rules_priority_level",
        "alert_routing_rules",
        "priority_level IN ('P1', 'P2', 'P3')",
    )
    op.create_check_constraint(
        "ck_alert_routing_rules_alert_type",
        "alert_routing_rules",
        "alert_type IS NULL OR alert_type IN ('LOW_BATTERY', 'LINK_LOSS', 'GEOFENCE_BREACH')",
    )
    op.create_check_constraint(
        "ck_alert_routing_rules_channel",
        "alert_routing_rules",
        "channel IN ('IN_APP', 'EMAIL', 'SMS', 'WEBHOOK')",
    )
    op.create_check_constraint(
        "ck_alert_route_logs_priority_level",
        "alert_route_logs",
        "priority_level IN ('P1', 'P2', 'P3')",
    )
    op.create_check_constraint(
        "ck_alert_route_logs_channel",
        "alert_route_logs",
        "channel IN ('IN_APP', 'EMAIL', 'SMS', 'WEBHOOK')",
    )
    op.create_check_constraint(
        "ck_alert_route_logs_delivery_status",
        "alert_route_logs",
        "delivery_status IN ('SENT', 'FAILED', 'SKIPPED')",
    )
    op.create_check_constraint(
        "ck_raw_data_catalog_records_data_type",
        "raw_data_catalog_records",
        "data_type IN ('TELEMETRY', 'IMAGE', 'VIDEO', 'DOCUMENT', 'LOG')",
    )
    op.create_check_constraint(
        "ck_outcome_catalog_records_source_type",
        "outcome_catalog_records",
        "source_type IN ('INSPECTION_OBSERVATION', 'ALERT', 'MANUAL')",
    )
    op.create_check_constraint(
        "ck_outcome_catalog_records_outcome_type",
        "outcome_catalog_records",
        "outcome_type IN ('DEFECT', 'HIDDEN_RISK', 'INCIDENT', 'OTHER')",
    )
    op.create_check_constraint(
        "ck_outcome_catalog_records_status",
        "outcome_catalog_records",
        "status IN ('NEW', 'IN_REVIEW', 'VERIFIED', 'ARCHIVED')",
    )

    op.create_foreign_key(
        "fk_alert_route_logs_tenant_alert",
        "alert_route_logs",
        "alerts",
        ["tenant_id", "alert_id"],
        ["tenant_id", "id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_alert_route_logs_tenant_rule",
        "alert_route_logs",
        "alert_routing_rules",
        ["tenant_id", "rule_id"],
        ["tenant_id", "id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_raw_data_catalog_records_tenant_task",
        "raw_data_catalog_records",
        "inspection_tasks",
        ["tenant_id", "task_id"],
        ["tenant_id", "id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_raw_data_catalog_records_tenant_mission",
        "raw_data_catalog_records",
        "missions",
        ["tenant_id", "mission_id"],
        ["tenant_id", "id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_outcome_catalog_records_tenant_task",
        "outcome_catalog_records",
        "inspection_tasks",
        ["tenant_id", "task_id"],
        ["tenant_id", "id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_outcome_catalog_records_tenant_mission",
        "outcome_catalog_records",
        "missions",
        ["tenant_id", "mission_id"],
        ["tenant_id", "id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_outcome_catalog_records_tenant_mission",
        "outcome_catalog_records",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_outcome_catalog_records_tenant_task",
        "outcome_catalog_records",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_raw_data_catalog_records_tenant_mission",
        "raw_data_catalog_records",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_raw_data_catalog_records_tenant_task",
        "raw_data_catalog_records",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_alert_route_logs_tenant_rule",
        "alert_route_logs",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_alert_route_logs_tenant_alert",
        "alert_route_logs",
        type_="foreignkey",
    )

    op.drop_constraint(
        "ck_outcome_catalog_records_status",
        "outcome_catalog_records",
        type_="check",
    )
    op.drop_constraint(
        "ck_outcome_catalog_records_outcome_type",
        "outcome_catalog_records",
        type_="check",
    )
    op.drop_constraint(
        "ck_outcome_catalog_records_source_type",
        "outcome_catalog_records",
        type_="check",
    )
    op.drop_constraint(
        "ck_raw_data_catalog_records_data_type",
        "raw_data_catalog_records",
        type_="check",
    )
    op.drop_constraint(
        "ck_alert_route_logs_delivery_status",
        "alert_route_logs",
        type_="check",
    )
    op.drop_constraint(
        "ck_alert_route_logs_channel",
        "alert_route_logs",
        type_="check",
    )
    op.drop_constraint(
        "ck_alert_route_logs_priority_level",
        "alert_route_logs",
        type_="check",
    )
    op.drop_constraint(
        "ck_alert_routing_rules_channel",
        "alert_routing_rules",
        type_="check",
    )
    op.drop_constraint(
        "ck_alert_routing_rules_alert_type",
        "alert_routing_rules",
        type_="check",
    )
    op.drop_constraint(
        "ck_alert_routing_rules_priority_level",
        "alert_routing_rules",
        type_="check",
    )
    op.drop_constraint(
        "ck_alerts_route_status",
        "alerts",
        type_="check",
    )
    op.drop_constraint(
        "ck_alerts_priority_level",
        "alerts",
        type_="check",
    )

    op.drop_index("ix_alerts_tenant_id_id", table_name="alerts")
    op.drop_constraint("uq_alerts_tenant_id_id", "alerts", type_="unique")

    op.alter_column("alerts", "route_status", existing_type=sa.String(length=20), nullable=True)
    op.alter_column("alerts", "priority_level", existing_type=sa.String(length=10), nullable=True)
