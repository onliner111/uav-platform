"""phase17 p2 policy inheritance enforce

Revision ID: 202602260070
Revises: 202602260069
Create Date: 2026-02-26
"""

from __future__ import annotations

from alembic import op

# revision identifiers, used by Alembic.
revision = "202602260070"
down_revision = "202602260069"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_check_constraint(
        "ck_data_access_policies_denied_org_unit_ids_is_array",
        "data_access_policies",
        "json_typeof(denied_org_unit_ids) = 'array'",
    )
    op.create_check_constraint(
        "ck_data_access_policies_denied_project_codes_is_array",
        "data_access_policies",
        "json_typeof(denied_project_codes) = 'array'",
    )
    op.create_check_constraint(
        "ck_data_access_policies_denied_area_codes_is_array",
        "data_access_policies",
        "json_typeof(denied_area_codes) = 'array'",
    )
    op.create_check_constraint(
        "ck_data_access_policies_denied_task_ids_is_array",
        "data_access_policies",
        "json_typeof(denied_task_ids) = 'array'",
    )
    op.create_check_constraint(
        "ck_data_access_policies_denied_resource_ids_is_array",
        "data_access_policies",
        "json_typeof(denied_resource_ids) = 'array'",
    )
    op.create_check_constraint(
        "ck_role_data_access_policies_scope_mode",
        "role_data_access_policies",
        "scope_mode IN ('ALL', 'SCOPED')",
    )
    op.create_check_constraint(
        "ck_role_data_access_policies_org_unit_ids_is_array",
        "role_data_access_policies",
        "json_typeof(org_unit_ids) = 'array'",
    )
    op.create_check_constraint(
        "ck_role_data_access_policies_project_codes_is_array",
        "role_data_access_policies",
        "json_typeof(project_codes) = 'array'",
    )
    op.create_check_constraint(
        "ck_role_data_access_policies_area_codes_is_array",
        "role_data_access_policies",
        "json_typeof(area_codes) = 'array'",
    )
    op.create_check_constraint(
        "ck_role_data_access_policies_task_ids_is_array",
        "role_data_access_policies",
        "json_typeof(task_ids) = 'array'",
    )
    op.create_check_constraint(
        "ck_role_data_access_policies_resource_ids_is_array",
        "role_data_access_policies",
        "json_typeof(resource_ids) = 'array'",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_role_data_access_policies_resource_ids_is_array",
        "role_data_access_policies",
        type_="check",
    )
    op.drop_constraint(
        "ck_role_data_access_policies_task_ids_is_array",
        "role_data_access_policies",
        type_="check",
    )
    op.drop_constraint(
        "ck_role_data_access_policies_area_codes_is_array",
        "role_data_access_policies",
        type_="check",
    )
    op.drop_constraint(
        "ck_role_data_access_policies_project_codes_is_array",
        "role_data_access_policies",
        type_="check",
    )
    op.drop_constraint(
        "ck_role_data_access_policies_org_unit_ids_is_array",
        "role_data_access_policies",
        type_="check",
    )
    op.drop_constraint(
        "ck_role_data_access_policies_scope_mode",
        "role_data_access_policies",
        type_="check",
    )
    op.drop_constraint(
        "ck_data_access_policies_denied_resource_ids_is_array",
        "data_access_policies",
        type_="check",
    )
    op.drop_constraint(
        "ck_data_access_policies_denied_task_ids_is_array",
        "data_access_policies",
        type_="check",
    )
    op.drop_constraint(
        "ck_data_access_policies_denied_area_codes_is_array",
        "data_access_policies",
        type_="check",
    )
    op.drop_constraint(
        "ck_data_access_policies_denied_project_codes_is_array",
        "data_access_policies",
        type_="check",
    )
    op.drop_constraint(
        "ck_data_access_policies_denied_org_unit_ids_is_array",
        "data_access_policies",
        type_="check",
    )
