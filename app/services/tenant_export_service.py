from __future__ import annotations

import enum
import hashlib
import json
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, cast
from uuid import uuid4
from zipfile import ZIP_DEFLATED, ZipFile

from sqlalchemy import Table, select
from sqlmodel import Session, SQLModel

from app.domain.models import Tenant
from app.infra.db import get_engine


class TenantExportError(Exception):
    pass


class NotFoundError(TenantExportError):
    pass


class TenantExportWriter:
    def __init__(self, root_dir: Path | None = None) -> None:
        self.root_dir = root_dir or (Path("logs") / "exports")

    def prepare_export_dir(self, tenant_id: str, export_id: str) -> Path:
        export_dir = self.root_dir / tenant_id / export_id
        tables_dir = export_dir / "tables"
        tables_dir.mkdir(parents=True, exist_ok=True)
        return export_dir

    def write_table_jsonl(
        self,
        *,
        export_dir: Path,
        table_name: str,
        rows: list[dict[str, Any]],
    ) -> dict[str, Any]:
        relative_path = Path("tables") / f"{table_name}.jsonl"
        output_path = export_dir / relative_path
        digest = hashlib.sha256()
        row_count = 0

        with output_path.open("w", encoding="utf-8") as handle:
            for row in rows:
                line = json.dumps(row, ensure_ascii=False, sort_keys=True)
                handle.write(f"{line}\n")
                digest.update(line.encode("utf-8"))
                digest.update(b"\n")
                row_count += 1

        return {
            "table": table_name,
            "row_count": row_count,
            "sha256": digest.hexdigest(),
            "file": str(relative_path).replace("\\", "/"),
        }

    def write_manifest(self, export_dir: Path, manifest: dict[str, Any]) -> Path:
        manifest_path = export_dir / "manifest.json"
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return manifest_path

    def write_zip(self, *, export_dir: Path, export_id: str) -> Path:
        zip_name = f"{export_id}.zip"
        zip_path = export_dir / zip_name
        with ZipFile(zip_path, "w", compression=ZIP_DEFLATED) as archive:
            for file_path in export_dir.rglob("*"):
                if not file_path.is_file():
                    continue
                if file_path == zip_path:
                    continue
                archive.write(file_path, arcname=str(file_path.relative_to(export_dir)))
        return zip_path


class TenantExportService:
    EXPORT_VERSION = "07C-1"

    def __init__(self, writer: TenantExportWriter | None = None) -> None:
        self._writer = writer or TenantExportWriter()

    def _session(self) -> Session:
        return Session(get_engine(), expire_on_commit=False)

    def _discover_tables(self) -> tuple[list[Table], list[str]]:
        scoped_tables: list[Table] = []
        global_tables: list[str] = []
        for table in SQLModel.metadata.sorted_tables:
            if "tenant_id" in table.columns:
                scoped_tables.append(table)
            else:
                global_tables.append(table.name)
        scoped_tables.sort(key=lambda item: item.name)
        global_tables.sort()
        return scoped_tables, global_tables

    def _normalize_value(self, value: Any) -> Any:
        if isinstance(value, datetime):
            if value.tzinfo is None:
                return value.replace(tzinfo=UTC).isoformat()
            return value.astimezone(UTC).isoformat()
        if isinstance(value, date):
            return value.isoformat()
        if isinstance(value, enum.Enum):
            return value.value
        if isinstance(value, str | int | float | bool) or value is None:
            return value
        if isinstance(value, list):
            return [self._normalize_value(item) for item in value]
        if isinstance(value, dict):
            return {key: self._normalize_value(item) for key, item in value.items()}
        return str(value)

    def _fetch_table_rows(
        self,
        *,
        session: Session,
        table: Table,
        tenant_id: str,
    ) -> list[dict[str, Any]]:
        columns = list(table.columns)
        statement = select(*columns).where(table.c.tenant_id == tenant_id)
        primary_keys = list(table.primary_key.columns)
        if primary_keys:
            statement = statement.order_by(*primary_keys)
        rows = session.execute(statement).mappings().all()
        normalized_rows: list[dict[str, Any]] = []
        for row in rows:
            normalized_rows.append(
                {
                    column.key: self._normalize_value(row[column.key])
                    for column in columns
                }
            )
        return normalized_rows

    def create_export(self, tenant_id: str, *, include_zip: bool = False) -> dict[str, Any]:
        export_id = str(uuid4())
        with self._session() as session:
            tenant = session.get(Tenant, tenant_id)
            if tenant is None:
                raise NotFoundError("tenant not found")

            scoped_tables, global_tables = self._discover_tables()
            export_dir = self._writer.prepare_export_dir(tenant_id, export_id)
            table_summaries: list[dict[str, Any]] = []
            for table in scoped_tables:
                rows = self._fetch_table_rows(session=session, table=table, tenant_id=tenant_id)
                table_summaries.append(
                    self._writer.write_table_jsonl(
                        export_dir=export_dir,
                        table_name=table.name,
                        rows=rows,
                    )
                )

        manifest: dict[str, Any] = {
            "export_id": export_id,
            "tenant_id": tenant_id,
            "status": "completed",
            "export_version": self.EXPORT_VERSION,
            "created_at": datetime.now(UTC).isoformat(),
            "tables": table_summaries,
            "global_tables_skipped": global_tables,
            "zip_file": None,
        }

        # Write manifest before optional zip packaging so zip can include it.
        manifest_path = self._writer.write_manifest(export_dir, manifest)
        zip_path: Path | None = None
        if include_zip:
            zip_path = self._writer.write_zip(export_dir=export_dir, export_id=export_id)
            manifest["zip_file"] = zip_path.name
            manifest_path = self._writer.write_manifest(export_dir, manifest)
        return {
            "export_id": export_id,
            "status": manifest["status"],
            "manifest_path": str(manifest_path),
            "zip_path": str(zip_path) if zip_path is not None else None,
        }

    def get_export_manifest(self, tenant_id: str, export_id: str) -> dict[str, Any]:
        manifest_path = self._writer.root_dir / tenant_id / export_id / "manifest.json"
        if not manifest_path.exists():
            raise NotFoundError("export not found")
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        return cast(dict[str, Any], payload)

    def get_export_zip_path(self, tenant_id: str, export_id: str) -> Path:
        manifest = self.get_export_manifest(tenant_id, export_id)
        zip_file = manifest.get("zip_file")
        if not isinstance(zip_file, str) or not zip_file:
            raise NotFoundError("zip export not found")
        zip_path = self._writer.root_dir / tenant_id / export_id / zip_file
        if not zip_path.exists():
            raise NotFoundError("zip export not found")
        return zip_path
