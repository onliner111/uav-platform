"""phase23 wp1 ai model governance backfill validate

Revision ID: 202602270093
Revises: 202602270092
Create Date: 2026-02-27
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "202602270093"
down_revision = "202602270092"
branch_labels = None
depends_on = None


def _model_key(provider: str | None, model_name: str | None) -> str:
    provider_text = (provider or "builtin").strip().lower()
    model_text = (model_name or "uav-assistant-lite").strip().lower()
    if not provider_text or not model_text:
        raise RuntimeError("Phase23-WP1 validation failed: invalid model provider/name in ai_analysis_jobs")
    return f"{provider_text}:{model_text}"


def _assert_zero(bind: sa.Connection, sql: str, error_message: str) -> None:
    rows = list(bind.execute(sa.text(sql)))
    if rows:
        raise RuntimeError(f"{error_message}. count={len(rows)}")


def upgrade() -> None:
    bind = op.get_bind()
    now = datetime.now(UTC)

    catalog_rows = list(
        bind.execute(
            sa.text(
                """
                SELECT id, tenant_id, model_key
                FROM ai_model_catalogs
                """
            )
        ).mappings()
    )
    catalog_by_key: dict[tuple[str, str], str] = {
        (str(row["tenant_id"]), str(row["model_key"])): str(row["id"])
        for row in catalog_rows
    }

    version_rows = list(
        bind.execute(
            sa.text(
                """
                SELECT id, tenant_id, model_id, version, status
                FROM ai_model_versions
                """
            )
        ).mappings()
    )
    version_by_key: dict[tuple[str, str, str], str] = {}
    stable_by_model: dict[tuple[str, str], str] = {}
    for row in version_rows:
        tenant_id = str(row["tenant_id"])
        model_id = str(row["model_id"])
        version_text = str(row["version"])
        version_by_key[(tenant_id, model_id, version_text)] = str(row["id"])
        if str(row["status"]) == "STABLE":
            stable_by_model[(tenant_id, model_id)] = str(row["id"])

    job_rows = list(
        bind.execute(
            sa.text(
                """
                SELECT id, tenant_id, model_provider, model_name, model_version, threshold_config, created_by, created_at
                FROM ai_analysis_jobs
                ORDER BY created_at ASC
                """
            )
        ).mappings()
    )

    for row in job_rows:
        tenant_id = str(row["tenant_id"])
        provider = str(row["model_provider"] or "builtin")
        model_name = str(row["model_name"] or "uav-assistant-lite")
        model_version = str(row["model_version"] or "phase14.v1")
        created_by = str(row["created_by"] or "system")
        created_at = row["created_at"] or now
        model_key = _model_key(provider, model_name)

        catalog_id = catalog_by_key.get((tenant_id, model_key))
        if catalog_id is None:
            catalog_id = str(uuid4())
            bind.execute(
                sa.text(
                    """
                    INSERT INTO ai_model_catalogs
                    (id, tenant_id, model_key, provider, display_name, description, is_active, created_by, created_at, updated_at)
                    VALUES
                    (:id, :tenant_id, :model_key, :provider, :display_name, :description, :is_active, :created_by, :created_at, :updated_at)
                    """
                ),
                {
                    "id": catalog_id,
                    "tenant_id": tenant_id,
                    "model_key": model_key,
                    "provider": provider,
                    "display_name": model_name,
                    "description": "backfilled from ai_analysis_jobs",
                    "is_active": True,
                    "created_by": created_by,
                    "created_at": created_at,
                    "updated_at": created_at,
                },
            )
            catalog_by_key[(tenant_id, model_key)] = catalog_id

        version_id = version_by_key.get((tenant_id, catalog_id, model_version))
        if version_id is None:
            stable_key = (tenant_id, catalog_id)
            has_stable = stable_key in stable_by_model
            version_id = str(uuid4())
            bind.execute(
                sa.text(
                    """
                    INSERT INTO ai_model_versions
                    (id, tenant_id, model_id, version, status, artifact_ref, threshold_defaults, detail, created_by, promoted_at, created_at, updated_at)
                    VALUES
                    (:id, :tenant_id, :model_id, :version, :status, :artifact_ref, :threshold_defaults, :detail, :created_by, :promoted_at, :created_at, :updated_at)
                    """
                ),
                {
                    "id": version_id,
                    "tenant_id": tenant_id,
                    "model_id": catalog_id,
                    "version": model_version,
                    "status": "DRAFT" if has_stable else "STABLE",
                    "artifact_ref": None,
                    "threshold_defaults": row["threshold_config"] if isinstance(row["threshold_config"], dict) else {},
                    "detail": {"source": "phase23_wp1_backfill"},
                    "created_by": created_by,
                    "promoted_at": None if has_stable else created_at,
                    "created_at": created_at,
                    "updated_at": created_at,
                },
            )
            version_by_key[(tenant_id, catalog_id, model_version)] = version_id
            if not has_stable:
                stable_by_model[stable_key] = version_id

        bind.execute(
            sa.text(
                """
                UPDATE ai_analysis_jobs
                SET model_version_id = :model_version_id
                WHERE tenant_id = :tenant_id AND id = :job_id
                """
            ),
            {
                "model_version_id": version_id,
                "tenant_id": tenant_id,
                "job_id": str(row["id"]),
            },
        )

    policy_rows = list(
        bind.execute(
            sa.text(
                """
                SELECT id, tenant_id, model_id
                FROM ai_model_rollout_policies
                """
            )
        ).mappings()
    )
    policy_by_model = {(str(row["tenant_id"]), str(row["model_id"])): str(row["id"]) for row in policy_rows}

    for stable_key, stable_version_id in stable_by_model.items():
        tenant_id, model_id = stable_key
        policy_id = policy_by_model.get(stable_key)
        if policy_id is None:
            bind.execute(
                sa.text(
                    """
                    INSERT INTO ai_model_rollout_policies
                    (id, tenant_id, model_id, default_version_id, traffic_allocation, threshold_overrides, detail, is_active, updated_by, created_at, updated_at)
                    VALUES
                    (:id, :tenant_id, :model_id, :default_version_id, :traffic_allocation, :threshold_overrides, :detail, :is_active, :updated_by, :created_at, :updated_at)
                    """
                ),
                {
                    "id": str(uuid4()),
                    "tenant_id": tenant_id,
                    "model_id": model_id,
                    "default_version_id": stable_version_id,
                    "traffic_allocation": [{"version_id": stable_version_id, "weight": 100}],
                    "threshold_overrides": {},
                    "detail": {"source": "phase23_wp1_backfill"},
                    "is_active": True,
                    "updated_by": "phase23-backfill",
                    "created_at": now,
                    "updated_at": now,
                },
            )
            continue

        bind.execute(
            sa.text(
                """
                UPDATE ai_model_rollout_policies
                SET default_version_id = COALESCE(default_version_id, :default_version_id),
                    traffic_allocation = CASE
                        WHEN traffic_allocation IS NULL THEN :traffic_allocation
                        ELSE traffic_allocation
                    END,
                    updated_at = :updated_at
                WHERE tenant_id = :tenant_id AND model_id = :model_id
                """
            ),
            {
                "default_version_id": stable_version_id,
                "traffic_allocation": [{"version_id": stable_version_id, "weight": 100}],
                "updated_at": now,
                "tenant_id": tenant_id,
                "model_id": model_id,
            },
        )

    _assert_zero(
        bind,
        """
        SELECT id FROM ai_analysis_jobs WHERE model_version_id IS NULL
        """,
        "Phase23-WP1 validation failed: ai_analysis_jobs.model_version_id remains NULL",
    )
    _assert_zero(
        bind,
        """
        SELECT id
        FROM ai_model_versions
        WHERE status NOT IN ('DRAFT', 'CANARY', 'STABLE', 'DEPRECATED')
        """,
        "Phase23-WP1 validation failed: ai_model_versions.status out of enum range",
    )
    _assert_zero(
        bind,
        """
        SELECT tenant_id, model_id
        FROM ai_model_versions
        WHERE status = 'STABLE'
        GROUP BY tenant_id, model_id
        HAVING COUNT(*) > 1
        """,
        "Phase23-WP1 validation failed: multiple stable versions for same model",
    )
    _assert_zero(
        bind,
        """
        SELECT id
        FROM ai_model_rollout_policies
        WHERE default_version_id IS NULL
        """,
        "Phase23-WP1 validation failed: rollout policy missing default_version_id",
    )


def downgrade() -> None:
    # Validation and backfill step only.
    pass
