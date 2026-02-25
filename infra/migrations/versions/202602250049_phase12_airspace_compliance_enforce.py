"""phase12 airspace compliance enforce

Revision ID: 202602250049
Revises: 202602250048
Create Date: 2026-02-25
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "202602250049"
down_revision = "202602250048"
branch_labels = None
depends_on = None


def _drop_legacy_fk(
    *,
    table: str,
    constrained_columns: list[str],
    referred_table: str,
) -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    for foreign_key in inspector.get_foreign_keys(table):
        name = foreign_key.get("name")
        if not name:
            continue
        fk_columns = foreign_key.get("constrained_columns") or []
        fk_referred_table = foreign_key.get("referred_table")
        if fk_columns == constrained_columns and fk_referred_table == referred_table:
            op.drop_constraint(name, table, type_="foreignkey")


def upgrade() -> None:
    op.alter_column(
        "command_requests",
        "compliance_detail",
        existing_type=sa.JSON(),
        nullable=False,
    )

    op.create_check_constraint(
        "ck_airspace_zones_zone_type",
        "airspace_zones",
        "zone_type IN ('NO_FLY', 'ALT_LIMIT', 'SENSITIVE')",
    )
    op.create_check_constraint(
        "ck_airspace_zones_max_alt_non_negative",
        "airspace_zones",
        "max_alt_m IS NULL OR max_alt_m >= 0",
    )
    op.create_check_constraint(
        "ck_mission_preflight_checklists_status",
        "mission_preflight_checklists",
        "status IN ('PENDING', 'IN_PROGRESS', 'COMPLETED', 'WAIVED')",
    )
    op.create_check_constraint(
        "ck_command_requests_compliance_reason_code",
        "command_requests",
        """
        compliance_reason_code IS NULL OR compliance_reason_code IN (
            'AIRSPACE_NO_FLY',
            'AIRSPACE_ALT_LIMIT_EXCEEDED',
            'AIRSPACE_SENSITIVE_RESTRICTED',
            'PREFLIGHT_CHECKLIST_REQUIRED',
            'PREFLIGHT_CHECKLIST_INCOMPLETE',
            'COMMAND_GEOFENCE_BLOCKED',
            'COMMAND_ALTITUDE_BLOCKED',
            'COMMAND_SENSITIVE_RESTRICTED'
        )
        """,
    )

    _drop_legacy_fk(
        table="mission_preflight_checklists",
        constrained_columns=["mission_id"],
        referred_table="missions",
    )
    _drop_legacy_fk(
        table="mission_preflight_checklists",
        constrained_columns=["template_id"],
        referred_table="preflight_checklist_templates",
    )

    op.create_foreign_key(
        "fk_mission_preflight_checklists_tenant_mission",
        "mission_preflight_checklists",
        "missions",
        ["tenant_id", "mission_id"],
        ["tenant_id", "id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_mission_preflight_checklists_tenant_template",
        "mission_preflight_checklists",
        "preflight_checklist_templates",
        ["tenant_id", "template_id"],
        ["tenant_id", "id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_mission_preflight_checklists_tenant_template",
        "mission_preflight_checklists",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_mission_preflight_checklists_tenant_mission",
        "mission_preflight_checklists",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "fk_mission_preflight_checklists_template_id",
        "mission_preflight_checklists",
        "preflight_checklist_templates",
        ["template_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_mission_preflight_checklists_mission_id",
        "mission_preflight_checklists",
        "missions",
        ["mission_id"],
        ["id"],
        ondelete="CASCADE",
    )

    op.drop_constraint(
        "ck_command_requests_compliance_reason_code",
        "command_requests",
        type_="check",
    )
    op.drop_constraint(
        "ck_mission_preflight_checklists_status",
        "mission_preflight_checklists",
        type_="check",
    )
    op.drop_constraint(
        "ck_airspace_zones_max_alt_non_negative",
        "airspace_zones",
        type_="check",
    )
    op.drop_constraint(
        "ck_airspace_zones_zone_type",
        "airspace_zones",
        type_="check",
    )
    op.alter_column(
        "command_requests",
        "compliance_detail",
        existing_type=sa.JSON(),
        nullable=True,
    )
