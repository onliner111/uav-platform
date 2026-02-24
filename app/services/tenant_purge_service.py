from __future__ import annotations

import hashlib
import json
from collections import deque
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast
from uuid import uuid4

import sqlalchemy as sa
from sqlalchemy import Table
from sqlalchemy.sql.elements import ColumnElement
from sqlmodel import Session, SQLModel

from app.domain.models import Tenant
from app.infra.db import get_engine

TENANT_PURGE_CONFIRM_PHRASE = "I_UNDERSTAND_THIS_WILL_DELETE_TENANT_DATA"


class TenantPurgeError(Exception):
    pass


class NotFoundError(TenantPurgeError):
    pass


class ValidationError(TenantPurgeError):
    pass


class ConflictError(TenantPurgeError):
    pass


@dataclass(frozen=True)
class PurgeTarget:
    table: Table
    mode: str
    links: tuple[tuple[str, str, str], ...] = ()


class TenantPurgeWriter:
    def __init__(self, root_dir: Path | None = None) -> None:
        self.root_dir = root_dir or (Path("logs") / "purge")

    def write_dry_run(self, tenant_id: str, dry_run_id: str, payload: dict[str, Any]) -> Path:
        output_dir = self.root_dir / tenant_id / dry_run_id
        output_dir.mkdir(parents=True, exist_ok=True)
        path = output_dir / "dry_run.json"
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return path

    def read_dry_run(self, tenant_id: str, dry_run_id: str) -> dict[str, Any]:
        path = self.root_dir / tenant_id / dry_run_id / "dry_run.json"
        if not path.exists():
            raise NotFoundError("dry run not found")
        payload = json.loads(path.read_text(encoding="utf-8"))
        return cast(dict[str, Any], payload)

    def write_report(self, tenant_id: str, purge_id: str, payload: dict[str, Any]) -> Path:
        output_dir = self.root_dir / tenant_id / purge_id
        output_dir.mkdir(parents=True, exist_ok=True)
        path = output_dir / "report.json"
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return path

    def read_report(self, tenant_id: str, purge_id: str) -> dict[str, Any]:
        path = self.root_dir / tenant_id / purge_id / "report.json"
        if not path.exists():
            raise NotFoundError("purge report not found")
        payload = json.loads(path.read_text(encoding="utf-8"))
        return cast(dict[str, Any], payload)


class TenantPurgeService:
    PURGE_VERSION = "07C-3"

    def __init__(self, writer: TenantPurgeWriter | None = None) -> None:
        self._writer = writer or TenantPurgeWriter()

    def _session(self) -> Session:
        return Session(get_engine(), expire_on_commit=False)

    def _discover_purge_targets(self) -> dict[str, PurgeTarget]:
        all_tables = {table.name: table for table in SQLModel.metadata.sorted_tables}
        targets: dict[str, PurgeTarget] = {}

        for table in all_tables.values():
            if "tenant_id" in table.columns:
                targets[table.name] = PurgeTarget(table=table, mode="tenant_id")

        for table in all_tables.values():
            if table.name in targets:
                continue
            links: list[tuple[str, str, str]] = []
            for fk in table.foreign_keys:
                parent_table = fk.column.table
                if "tenant_id" not in parent_table.columns:
                    continue
                links.append((fk.parent.key, parent_table.name, fk.column.key))
            if links:
                targets[table.name] = PurgeTarget(
                    table=table,
                    mode="fk_exists",
                    links=tuple(sorted(set(links))),
                )
        return targets

    def _build_purge_plan(self, target_map: dict[str, PurgeTarget]) -> tuple[list[str], list[str]]:
        graph: dict[str, set[str]] = {name: set() for name in target_map}
        indegree: dict[str, int] = {name: 0 for name in target_map}

        for child_name, target in target_map.items():
            for fk in target.table.foreign_keys:
                parent_name = fk.column.table.name
                if parent_name == child_name or parent_name not in target_map:
                    continue
                if parent_name in graph[child_name]:
                    continue
                graph[child_name].add(parent_name)
                indegree[parent_name] += 1

        queue = deque(sorted([name for name, degree in indegree.items() if degree == 0]))
        order: list[str] = []
        while queue:
            current = queue.popleft()
            order.append(current)
            for parent_name in sorted(graph[current]):
                indegree[parent_name] -= 1
                if indegree[parent_name] == 0:
                    queue.append(parent_name)

        warnings: list[str] = []
        if len(order) < len(target_map):
            remaining = sorted([name for name in target_map if name not in order])
            warnings.append(
                "dependency cycle detected; falling back to deterministic alphabetical order "
                f"for remaining tables: {remaining}"
            )
            order.extend(remaining)
        return order, warnings

    def _target_clause(
        self,
        *,
        target: PurgeTarget,
        tenant_id: str,
        target_map: dict[str, PurgeTarget],
    ) -> ColumnElement[bool]:
        if target.mode == "tenant_id":
            return target.table.c.tenant_id == tenant_id
        if target.mode != "fk_exists":
            raise ValidationError(f"unsupported purge target mode: {target.mode}")

        clauses: list[ColumnElement[bool]] = []
        for child_col, parent_name, parent_col in target.links:
            if parent_name not in target_map:
                continue
            parent_table = target_map[parent_name].table
            clauses.append(
                sa.exists(
                    sa.select(1)
                    .select_from(parent_table)
                    .where(parent_table.c[parent_col] == target.table.c[child_col])
                    .where(parent_table.c.tenant_id == tenant_id)
                )
            )
        if not clauses:
            raise ValidationError(f"no tenant linkage discovered for table: {target.table.name}")
        if len(clauses) == 1:
            return clauses[0]
        return sa.or_(*clauses)

    def _target_row_count(
        self,
        session: Session,
        *,
        target: PurgeTarget,
        tenant_id: str,
        target_map: dict[str, PurgeTarget],
    ) -> int:
        clause = self._target_clause(target=target, tenant_id=tenant_id, target_map=target_map)
        statement = sa.select(sa.func.count()).select_from(target.table).where(clause)
        return int(session.execute(statement).scalar_one())

    def _collect_counts(
        self,
        session: Session,
        *,
        target_map: dict[str, PurgeTarget],
        table_names: list[str],
        tenant_id: str,
    ) -> dict[str, int]:
        return {
            table_name: self._target_row_count(
                session,
                target=target_map[table_name],
                tenant_id=tenant_id,
                target_map=target_map,
            )
            for table_name in table_names
        }

    def _ensure_tenant_exists(self, session: Session, tenant_id: str) -> None:
        tenant = session.get(Tenant, tenant_id)
        if tenant is None:
            raise NotFoundError("tenant not found")

    def _generate_confirm_token(self, *, tenant_id: str, dry_run_id: str, plan: list[str], total_rows: int) -> str:
        raw = f"{tenant_id}:{dry_run_id}:{total_rows}:{'|'.join(plan)}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def create_dry_run(self, tenant_id: str) -> dict[str, Any]:
        dry_run_id = str(uuid4())
        with self._session() as session:
            self._ensure_tenant_exists(session, tenant_id)
            target_map = self._discover_purge_targets()
            plan, warnings = self._build_purge_plan(target_map)
            counts = self._collect_counts(
                session,
                target_map=target_map,
                table_names=plan,
                tenant_id=tenant_id,
            )

        estimated_rows = sum(counts.values())
        confirm_token = self._generate_confirm_token(
            tenant_id=tenant_id,
            dry_run_id=dry_run_id,
            plan=plan,
            total_rows=estimated_rows,
        )
        safety_warnings = list(warnings)
        if estimated_rows == 0:
            safety_warnings.append("tenant currently has zero rows across purge targets")
        payload: dict[str, Any] = {
            "dry_run_id": dry_run_id,
            "tenant_id": tenant_id,
            "status": "dry_run_ready",
            "purge_version": self.PURGE_VERSION,
            "created_at": datetime.now(UTC).isoformat(),
            "plan": plan,
            "counts": counts,
            "estimated_rows": estimated_rows,
            "safety": {
                "requires_confirmation": True,
                "warnings": safety_warnings,
                "confirm_phrase": TENANT_PURGE_CONFIRM_PHRASE,
            },
            "confirm_token": confirm_token,
        }
        dry_run_path = self._writer.write_dry_run(tenant_id, dry_run_id, payload)
        return {
            **payload,
            "dry_run_path": str(dry_run_path),
        }

    def execute_purge(
        self,
        *,
        tenant_id: str,
        dry_run_id: str,
        confirm_token: str | None,
        confirm_phrase: str | None,
        mode: str,
    ) -> dict[str, Any]:
        if mode.lower() != "hard":
            raise ValidationError("only hard mode is supported")

        dry_run_payload = self._writer.read_dry_run(tenant_id, dry_run_id)
        expected_token = dry_run_payload.get("confirm_token")
        if not isinstance(expected_token, str) or not expected_token:
            raise ValidationError("dry run confirmation token is invalid")

        confirmed = (confirm_token == expected_token) or (confirm_phrase == TENANT_PURGE_CONFIRM_PHRASE)
        if not confirmed:
            raise ConflictError("confirmation required: provide valid confirm_token or confirm_phrase")

        plan = dry_run_payload.get("plan")
        if not isinstance(plan, list) or not all(isinstance(name, str) for name in plan):
            raise ValidationError("dry run plan is invalid")
        plan_names = cast(list[str], plan)
        dry_run_counts_raw = dry_run_payload.get("counts")
        if not isinstance(dry_run_counts_raw, dict):
            raise ValidationError("dry run counts are invalid")
        dry_run_counts = cast(dict[str, Any], dry_run_counts_raw)

        target_map = self._discover_purge_targets()
        missing_tables = [name for name in plan_names if name not in target_map]
        if missing_tables:
            raise ValidationError(f"dry run plan references unknown tables: {missing_tables}")

        purge_id = str(uuid4())
        with self._session() as session:
            self._ensure_tenant_exists(session, tenant_id)
            pre_delete_counts = self._collect_counts(
                session,
                target_map=target_map,
                table_names=plan_names,
                tenant_id=tenant_id,
            )
            deleted_counts: dict[str, int] = {}
            for table_name in plan_names:
                target = target_map[table_name]
                clause = self._target_clause(target=target, tenant_id=tenant_id, target_map=target_map)
                delete_result = session.execute(sa.delete(target.table).where(clause))
                rowcount = getattr(delete_result, "rowcount", None)
                deleted_counts[table_name] = int(rowcount or 0)
            post_delete_counts = self._collect_counts(
                session,
                target_map=target_map,
                table_names=plan_names,
                tenant_id=tenant_id,
            )
            non_zero = {name: count for name, count in post_delete_counts.items() if count > 0}
            if non_zero:
                session.rollback()
                raise ConflictError(f"purge verification failed; remaining rows detected: {non_zero}")
            session.commit()

        deleted_rows = sum(deleted_counts.values())
        drift_detected = any(
            int(pre_delete_counts.get(name, 0)) != int(dry_run_counts.get(name, 0))
            for name in plan_names
        )
        report_payload: dict[str, Any] = {
            "purge_id": purge_id,
            "dry_run_id": dry_run_id,
            "tenant_id": tenant_id,
            "status": "completed",
            "purge_version": self.PURGE_VERSION,
            "executed_at": datetime.now(UTC).isoformat(),
            "mode": "hard",
            "confirm_method": "token" if confirm_token == expected_token else "phrase",
            "plan": plan_names,
            "dry_run_counts": dry_run_counts,
            "pre_delete_counts": pre_delete_counts,
            "deleted_counts": deleted_counts,
            "post_delete_counts": post_delete_counts,
            "deleted_rows": deleted_rows,
            "dry_run_drift_detected": drift_detected,
        }
        report_path = self._writer.write_report(tenant_id, purge_id, report_payload)
        return {
            "purge_id": purge_id,
            "tenant_id": tenant_id,
            "dry_run_id": dry_run_id,
            "status": "completed",
            "report_path": str(report_path),
            "deleted_rows": deleted_rows,
            "post_delete_counts": post_delete_counts,
        }

    def get_purge_report(self, tenant_id: str, purge_id: str) -> dict[str, Any]:
        return self._writer.read_report(tenant_id, purge_id)
