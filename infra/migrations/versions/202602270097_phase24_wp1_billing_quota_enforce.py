"""phase24 wp1 billing quota enforce

Revision ID: 202602270097
Revises: 202602270096
Create Date: 2026-02-27
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "202602270097"
down_revision = "202602270096"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_check_constraint(
        "ck_billing_plan_catalogs_plan_code_not_empty",
        "billing_plan_catalogs",
        "plan_code <> ''",
    )
    op.create_check_constraint(
        "ck_billing_plan_catalogs_display_name_not_empty",
        "billing_plan_catalogs",
        "display_name <> ''",
    )
    op.create_check_constraint(
        "ck_billing_plan_catalogs_cycle",
        "billing_plan_catalogs",
        "billing_cycle IN ('MONTHLY', 'QUARTERLY', 'YEARLY')",
    )
    op.create_check_constraint(
        "ck_billing_plan_catalogs_price_non_negative",
        "billing_plan_catalogs",
        "price_cents >= 0",
    )
    op.create_check_constraint(
        "ck_billing_plan_quotas_key_not_empty",
        "billing_plan_quotas",
        "quota_key <> ''",
    )
    op.create_check_constraint(
        "ck_billing_plan_quotas_limit_non_negative",
        "billing_plan_quotas",
        "quota_limit >= 0",
    )
    op.create_check_constraint(
        "ck_billing_plan_quotas_mode",
        "billing_plan_quotas",
        "enforcement_mode IN ('HARD_LIMIT', 'SOFT_LIMIT')",
    )
    op.create_check_constraint(
        "ck_tenant_subscriptions_status",
        "tenant_subscriptions",
        "status IN ('TRIAL', 'ACTIVE', 'SUSPENDED', 'EXPIRED')",
    )
    op.create_check_constraint(
        "ck_tenant_subscriptions_window",
        "tenant_subscriptions",
        "(end_at IS NULL) OR (end_at > start_at)",
    )
    op.create_check_constraint(
        "ck_tenant_quota_overrides_key_not_empty",
        "tenant_quota_overrides",
        "quota_key <> ''",
    )
    op.create_check_constraint(
        "ck_tenant_quota_overrides_limit_non_negative",
        "tenant_quota_overrides",
        "override_limit >= 0",
    )
    op.create_check_constraint(
        "ck_tenant_quota_overrides_mode",
        "tenant_quota_overrides",
        "enforcement_mode IN ('HARD_LIMIT', 'SOFT_LIMIT')",
    )

    op.create_foreign_key(
        "fk_billing_plan_quotas_tenant_plan",
        "billing_plan_quotas",
        "billing_plan_catalogs",
        ["tenant_id", "plan_id"],
        ["tenant_id", "id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_tenant_subscriptions_tenant_plan",
        "tenant_subscriptions",
        "billing_plan_catalogs",
        ["tenant_id", "plan_id"],
        ["tenant_id", "id"],
        ondelete="RESTRICT",
    )

    op.create_index(
        "uq_tenant_subscriptions_tenant_active",
        "tenant_subscriptions",
        ["tenant_id"],
        unique=True,
        postgresql_where=sa.text("status = 'ACTIVE'"),
        sqlite_where=sa.text("status = 'ACTIVE'"),
    )


def downgrade() -> None:
    op.drop_index("uq_tenant_subscriptions_tenant_active", table_name="tenant_subscriptions")

    op.drop_constraint(
        "fk_tenant_subscriptions_tenant_plan",
        "tenant_subscriptions",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_billing_plan_quotas_tenant_plan",
        "billing_plan_quotas",
        type_="foreignkey",
    )

    op.drop_constraint(
        "ck_tenant_quota_overrides_mode",
        "tenant_quota_overrides",
        type_="check",
    )
    op.drop_constraint(
        "ck_tenant_quota_overrides_limit_non_negative",
        "tenant_quota_overrides",
        type_="check",
    )
    op.drop_constraint(
        "ck_tenant_quota_overrides_key_not_empty",
        "tenant_quota_overrides",
        type_="check",
    )
    op.drop_constraint(
        "ck_tenant_subscriptions_window",
        "tenant_subscriptions",
        type_="check",
    )
    op.drop_constraint(
        "ck_tenant_subscriptions_status",
        "tenant_subscriptions",
        type_="check",
    )
    op.drop_constraint(
        "ck_billing_plan_quotas_mode",
        "billing_plan_quotas",
        type_="check",
    )
    op.drop_constraint(
        "ck_billing_plan_quotas_limit_non_negative",
        "billing_plan_quotas",
        type_="check",
    )
    op.drop_constraint(
        "ck_billing_plan_quotas_key_not_empty",
        "billing_plan_quotas",
        type_="check",
    )
    op.drop_constraint(
        "ck_billing_plan_catalogs_price_non_negative",
        "billing_plan_catalogs",
        type_="check",
    )
    op.drop_constraint(
        "ck_billing_plan_catalogs_cycle",
        "billing_plan_catalogs",
        type_="check",
    )
    op.drop_constraint(
        "ck_billing_plan_catalogs_display_name_not_empty",
        "billing_plan_catalogs",
        type_="check",
    )
    op.drop_constraint(
        "ck_billing_plan_catalogs_plan_code_not_empty",
        "billing_plan_catalogs",
        type_="check",
    )
