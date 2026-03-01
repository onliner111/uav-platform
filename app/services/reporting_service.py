from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, col, select

from app.domain.models import (
    AlertHandlingAction,
    AlertRecord,
    Defect,
    DefectStatus,
    DeviceUtilizationRead,
    Drone,
    InspectionTask,
    Mission,
    OutcomeCatalogRecord,
    OutcomeReportExport,
    OutcomeReportExportCreateRequest,
    OutcomeReportRetentionRunRead,
    OutcomeReportRetentionRunRequest,
    OutcomeReportTemplate,
    OutcomeReportTemplateCreate,
    ReportExportStatus,
    ReportFileFormat,
    ReportingClosureRateRead,
    ReportingExportRequest,
    ReportingOverviewRead,
    now_utc,
)
from app.infra.db import get_engine
from app.services.data_perimeter_service import DataPerimeterScope, DataPerimeterService
from app.services.defect_service import DefectService


class ReportingError(Exception):
    pass


class NotFoundError(ReportingError):
    pass


class ConflictError(ReportingError):
    pass


class ReportingService:
    def __init__(self) -> None:
        self._defect_service = DefectService()
        self._data_perimeter = DataPerimeterService()

    def _session(self) -> Session:
        return Session(get_engine(), expire_on_commit=False)

    def _as_utc(self, value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)

    def _get_scoped_outcome_report_template(
        self,
        session: Session,
        tenant_id: str,
        template_id: str,
    ) -> OutcomeReportTemplate:
        row = session.exec(
            select(OutcomeReportTemplate)
            .where(OutcomeReportTemplate.tenant_id == tenant_id)
            .where(OutcomeReportTemplate.id == template_id)
        ).first()
        if row is None:
            raise NotFoundError("outcome report template not found")
        return row

    def _get_scoped_outcome_report_export(
        self,
        session: Session,
        tenant_id: str,
        export_id: str,
    ) -> OutcomeReportExport:
        row = session.exec(
            select(OutcomeReportExport)
            .where(OutcomeReportExport.tenant_id == tenant_id)
            .where(OutcomeReportExport.id == export_id)
        ).first()
        if row is None:
            raise NotFoundError("outcome report export not found")
        return row

    def _is_outcome_visible(
        self,
        session: Session,
        scope: DataPerimeterScope,
        outcome: OutcomeCatalogRecord,
    ) -> bool:
        if outcome.task_id is not None:
            task = session.exec(
                select(InspectionTask)
                .where(InspectionTask.tenant_id == outcome.tenant_id)
                .where(InspectionTask.id == outcome.task_id)
            ).first()
            if task is None:
                return False
            return self._data_perimeter.inspection_task_visible(task, scope)
        if outcome.mission_id is not None:
            mission = session.exec(
                select(Mission)
                .where(Mission.tenant_id == outcome.tenant_id)
                .where(Mission.id == outcome.mission_id)
            ).first()
            if mission is None:
                return False
            return self._data_perimeter.mission_visible(mission, scope)
        return True

    def create_outcome_report_template(
        self,
        tenant_id: str,
        actor_id: str,
        payload: OutcomeReportTemplateCreate,
    ) -> OutcomeReportTemplate:
        with self._session() as session:
            row = OutcomeReportTemplate(
                tenant_id=tenant_id,
                name=payload.name,
                format_default=payload.format_default,
                title_template=payload.title_template,
                body_template=payload.body_template,
                is_active=payload.is_active,
                created_by=actor_id,
            )
            session.add(row)
            try:
                session.commit()
            except IntegrityError as exc:
                session.rollback()
                raise ConflictError("outcome report template name already exists") from exc
            session.refresh(row)
            return row

    def list_outcome_report_templates(self, tenant_id: str) -> list[OutcomeReportTemplate]:
        with self._session() as session:
            statement = (
                select(OutcomeReportTemplate)
                .where(OutcomeReportTemplate.tenant_id == tenant_id)
                .order_by(col(OutcomeReportTemplate.created_at).desc())
            )
            return list(session.exec(statement).all())

    def get_outcome_report_export(self, tenant_id: str, export_id: str) -> OutcomeReportExport:
        with self._session() as session:
            return self._get_scoped_outcome_report_export(session, tenant_id, export_id)

    def list_outcome_report_exports(
        self,
        tenant_id: str,
        *,
        status: ReportExportStatus | None = None,
        limit: int = 50,
    ) -> list[OutcomeReportExport]:
        with self._session() as session:
            statement = select(OutcomeReportExport).where(OutcomeReportExport.tenant_id == tenant_id)
            if status is not None:
                statement = statement.where(OutcomeReportExport.status == status)
            rows = list(session.exec(statement).all())
            rows.sort(key=lambda item: item.created_at, reverse=True)
            return rows[: max(1, min(limit, 200))]

    def run_outcome_report_retention(
        self,
        tenant_id: str,
        payload: OutcomeReportRetentionRunRequest,
    ) -> OutcomeReportRetentionRunRead:
        cutoff = now_utc() - timedelta(days=payload.retention_days)
        with self._session() as session:
            statement = (
                select(OutcomeReportExport)
                .where(OutcomeReportExport.tenant_id == tenant_id)
                .where(OutcomeReportExport.status == ReportExportStatus.SUCCEEDED)
            )
            rows = [item for item in list(session.exec(statement).all()) if item.file_path]
            expired = [
                item
                for item in rows
                if item.completed_at is not None and self._as_utc(item.completed_at) < cutoff
            ]

            deleted_files = 0
            skipped_files = 0
            if not payload.dry_run:
                for item in expired:
                    file_deleted = False
                    if item.file_path:
                        path = Path(item.file_path)
                        if path.exists():
                            path.unlink()
                            deleted_files += 1
                            file_deleted = True
                        else:
                            skipped_files += 1
                    detail = dict(item.detail)
                    detail["lifecycle"] = {
                        "retention_days": payload.retention_days,
                        "retention_cutoff": cutoff.isoformat(),
                        "retention_deleted_at": now_utc().isoformat(),
                        "file_deleted": file_deleted,
                    }
                    item.detail = detail
                    item.file_path = None
                    item.updated_at = now_utc()
                    session.add(item)
                session.commit()

            return OutcomeReportRetentionRunRead(
                scanned_count=len(rows),
                expired_count=len(expired),
                deleted_files=deleted_files,
                skipped_files=skipped_files,
            )

    def overview(self, tenant_id: str, viewer_user_id: str | None = None) -> ReportingOverviewRead:
        with self._session() as session:
            missions = list(session.exec(select(Mission).where(Mission.tenant_id == tenant_id)).all())
            inspections = list(session.exec(select(InspectionTask).where(InspectionTask.tenant_id == tenant_id)).all())
            defects = list(session.exec(select(Defect).where(Defect.tenant_id == tenant_id)).all())
            scope = self._data_perimeter.resolve_scope(session, tenant_id, viewer_user_id)
            missions = [item for item in missions if self._data_perimeter.mission_visible(item, scope)]
            inspections = [
                item for item in inspections if self._data_perimeter.inspection_task_visible(item, scope)
            ]
            defects = [item for item in defects if self._data_perimeter.defect_visible(item, scope)]
        defects_total = len(defects)
        defects_closed = len([item for item in defects if item.status == DefectStatus.CLOSED])
        closure_rate = (defects_closed / defects_total) if defects_total else 0.0
        return ReportingOverviewRead(
            missions_total=len(missions),
            inspections_total=len(inspections),
            defects_total=defects_total,
            defects_closed=defects_closed,
            closure_rate=closure_rate,
        )

    def closure_rate(self, tenant_id: str, viewer_user_id: str | None = None) -> ReportingClosureRateRead:
        stats = self._defect_service.stats(tenant_id, viewer_user_id=viewer_user_id)
        return ReportingClosureRateRead(
            total=stats.total,
            closed=stats.closed,
            closure_rate=stats.closure_rate,
        )

    def device_utilization(self, tenant_id: str, viewer_user_id: str | None = None) -> list[DeviceUtilizationRead]:
        with self._session() as session:
            drones = list(session.exec(select(Drone).where(Drone.tenant_id == tenant_id)).all())
            missions = list(session.exec(select(Mission).where(Mission.tenant_id == tenant_id)).all())
            inspections = list(session.exec(select(InspectionTask).where(InspectionTask.tenant_id == tenant_id)).all())
            scope = self._data_perimeter.resolve_scope(session, tenant_id, viewer_user_id)
            missions = [item for item in missions if self._data_perimeter.mission_visible(item, scope)]
            inspections = [
                item for item in inspections if self._data_perimeter.inspection_task_visible(item, scope)
            ]

        usage: list[DeviceUtilizationRead] = []
        for drone in drones:
            drone_mission_ids = {item.id for item in missions if item.drone_id == drone.id}
            drone_missions = len(drone_mission_ids)
            drone_inspections = len([item for item in inspections if item.mission_id in drone_mission_ids])
            usage.append(
                DeviceUtilizationRead(
                    drone_id=drone.id,
                    drone_name=drone.name,
                    missions=drone_missions,
                    inspections=drone_inspections,
                )
            )
        return usage

    def create_outcome_report_export(
        self,
        tenant_id: str,
        actor_id: str,
        payload: OutcomeReportExportCreateRequest,
        *,
        viewer_user_id: str | None,
    ) -> OutcomeReportExport:
        with self._session() as session:
            template = self._get_scoped_outcome_report_template(session, tenant_id, payload.template_id)
            if not template.is_active:
                raise ConflictError("outcome report template is inactive")

            report_format = payload.report_format or template.format_default
            export_row = OutcomeReportExport(
                tenant_id=tenant_id,
                template_id=template.id,
                report_format=report_format,
                status=ReportExportStatus.RUNNING,
                task_id=payload.task_id,
                from_ts=payload.from_ts,
                to_ts=payload.to_ts,
                topic=payload.topic,
                requested_by=actor_id,
                detail={},
            )
            session.add(export_row)
            session.commit()
            session.refresh(export_row)

            scope = self._data_perimeter.resolve_scope(session, tenant_id, viewer_user_id)
            outcomes = list(
                session.exec(select(OutcomeCatalogRecord).where(OutcomeCatalogRecord.tenant_id == tenant_id)).all()
            )
            outcomes = [item for item in outcomes if self._is_outcome_visible(session, scope, item)]
            if export_row.task_id is not None:
                outcomes = [item for item in outcomes if item.task_id == export_row.task_id]

            def _within(ts: datetime) -> bool:
                if export_row.from_ts is not None and ts < export_row.from_ts:
                    return False
                return not (export_row.to_ts is not None and ts > export_row.to_ts)

            outcomes = [item for item in outcomes if _within(item.created_at)]

            if export_row.topic:
                topic = export_row.topic.strip().lower()
                outcomes = [
                    item
                    for item in outcomes
                    if topic in item.outcome_type.value.lower() or topic in str(item.payload).lower()
                ]

            export_dir = Path("logs") / "exports"
            export_dir.mkdir(parents=True, exist_ok=True)
            suffix = "pdf" if report_format == ReportFileFormat.PDF else "docx"
            output_file = export_dir / f"outcome_report_{export_row.id}.{suffix}"

            content = self._render_outcome_report_text(template, export_row, outcomes)
            try:
                if report_format == ReportFileFormat.PDF:
                    self._write_minimal_pdf(output_file, content)
                else:
                    self._write_minimal_docx(output_file, content)
            except Exception as exc:
                export_row.status = ReportExportStatus.FAILED
                export_row.detail = {"error": str(exc)}
                export_row.updated_at = now_utc()
                export_row.completed_at = now_utc()
                session.add(export_row)
                session.commit()
                session.refresh(export_row)
                raise ConflictError("outcome report export failed") from exc

            export_row.status = ReportExportStatus.SUCCEEDED
            export_row.file_path = str(output_file)
            export_row.detail = {"outcomes_total": len(outcomes), "template_id": template.id}
            export_row.updated_at = now_utc()
            export_row.completed_at = now_utc()
            session.add(export_row)
            session.commit()
            session.refresh(export_row)
            return export_row

    def _render_outcome_report_text(
        self,
        template: OutcomeReportTemplate,
        export_row: OutcomeReportExport,
        outcomes: list[OutcomeCatalogRecord],
    ) -> str:
        context = {
            "task_id": export_row.task_id or "",
            "from_ts": export_row.from_ts.isoformat() if export_row.from_ts else "",
            "to_ts": export_row.to_ts.isoformat() if export_row.to_ts else "",
            "topic": export_row.topic or "",
            "count": len(outcomes),
        }

        def _safe_format(text: str) -> str:
            try:
                return text.format(**context)
            except Exception:
                return text

        title = _safe_format(template.title_template)
        body_template = _safe_format(template.body_template)
        lines = [title, "", body_template, "", "Outcomes:"]
        for item in outcomes:
            lines.append(
                
                    f"- id={item.id} type={item.outcome_type.value} status={item.status.value} "
                    f"task_id={item.task_id or ''} mission_id={item.mission_id or ''}"
                
            )
        return "\n".join(lines)

    def export_report(
        self,
        tenant_id: str,
        payload: ReportingExportRequest,
        viewer_user_id: str | None = None,
    ) -> str:
        overview = self.overview(tenant_id, viewer_user_id=viewer_user_id)
        closure = self.closure_rate(tenant_id, viewer_user_id=viewer_user_id)
        with self._session() as session:
            outcomes = list(
                session.exec(select(OutcomeCatalogRecord).where(OutcomeCatalogRecord.tenant_id == tenant_id)).all()
            )
            alerts = list(session.exec(select(AlertRecord).where(AlertRecord.tenant_id == tenant_id)).all())
            actions = list(
                session.exec(select(AlertHandlingAction).where(AlertHandlingAction.tenant_id == tenant_id)).all()
            )

        if payload.task_id is not None:
            outcomes = [item for item in outcomes if item.task_id == payload.task_id]

        def _within(ts: datetime) -> bool:
            if payload.from_ts is not None and ts < payload.from_ts:
                return False
            return not (payload.to_ts is not None and ts > payload.to_ts)

        outcomes = [item for item in outcomes if _within(item.created_at)]
        alerts = [item for item in alerts if _within(item.first_seen_at)]
        actions = [item for item in actions if _within(item.created_at)]

        if payload.topic:
            topic = payload.topic.strip().lower()
            outcomes = [
                item
                for item in outcomes
                if topic in item.outcome_type.value.lower() or topic in str(item.payload).lower()
            ]
            alerts = [
                item
                for item in alerts
                if topic in item.alert_type.value.lower()
                or topic in item.message.lower()
                or topic in str(item.detail).lower()
            ]
            actions = [
                item
                for item in actions
                if topic in item.action_type.value.lower() or topic in str(item.note or "").lower()
            ]

        export_dir = Path("logs") / "exports"
        export_dir.mkdir(parents=True, exist_ok=True)
        output_file = export_dir / f"report_{tenant_id}.pdf"
        text = (
            f"{payload.title}\n"
            f"task_id={payload.task_id or ''}\n"
            f"from_ts={payload.from_ts.isoformat() if payload.from_ts else ''}\n"
            f"to_ts={payload.to_ts.isoformat() if payload.to_ts else ''}\n"
            f"topic={payload.topic or ''}\n"
            f"missions_total={overview.missions_total}\n"
            f"inspections_total={overview.inspections_total}\n"
            f"defects_total={overview.defects_total}\n"
            f"defects_closed={overview.defects_closed}\n"
            f"closure_rate={closure.closure_rate:.4f}\n"
            f"outcomes_total={len(outcomes)}\n"
            f"alerts_total={len(alerts)}\n"
            f"alert_actions_total={len(actions)}\n"
        )
        self._write_minimal_pdf(output_file, text)
        return str(output_file)

    def _write_minimal_pdf(self, path: Path, content: str) -> None:
        escaped = content.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        stream = f"BT /F1 11 Tf 50 760 Td ({escaped}) Tj ET"
        stream_bytes = stream.encode("latin-1", errors="replace")
        objects = [
            b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n",
            b"2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj\n",
            b"3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >> endobj\n",
            b"4 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj\n",
            f"5 0 obj << /Length {len(stream_bytes)} >> stream\n".encode("ascii")
            + stream_bytes
            + b"\nendstream endobj\n",
        ]
        result = bytearray(b"%PDF-1.4\n")
        offsets = [0]
        for obj in objects:
            offsets.append(len(result))
            result.extend(obj)
        xref_pos = len(result)
        result.extend(f"xref\n0 {len(offsets)}\n".encode("ascii"))
        result.extend(b"0000000000 65535 f \n")
        for offset in offsets[1:]:
            result.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
        result.extend(
            (
                "trailer << /Size "
                f"{len(offsets)} /Root 1 0 R >>\nstartxref\n{xref_pos}\n%%EOF\n"
            ).encode("ascii")
        )
        path.write_bytes(bytes(result))

    def _write_minimal_docx(self, path: Path, content: str) -> None:
        escaped_lines = (
            content.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .splitlines()
        )
        if not escaped_lines:
            escaped_lines = [""]
        paragraphs = "".join(
            (
                "<w:p><w:r><w:t xml:space=\"preserve\">"
                f"{line}"
                "</w:t></w:r></w:p>"
            )
            for line in escaped_lines
        )
        document_xml = (
            "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>"
            "<w:document "
            "xmlns:wpc=\"http://schemas.microsoft.com/office/word/2010/wordprocessingCanvas\" "
            "xmlns:mc=\"http://schemas.openxmlformats.org/markup-compatibility/2006\" "
            "xmlns:o=\"urn:schemas-microsoft-com:office:office\" "
            "xmlns:r=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships\" "
            "xmlns:m=\"http://schemas.openxmlformats.org/officeDocument/2006/math\" "
            "xmlns:v=\"urn:schemas-microsoft-com:vml\" "
            "xmlns:wp14=\"http://schemas.microsoft.com/office/word/2010/wordprocessingDrawing\" "
            "xmlns:wp=\"http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing\" "
            "xmlns:w10=\"urn:schemas-microsoft-com:office:word\" "
            "xmlns:w=\"http://schemas.openxmlformats.org/wordprocessingml/2006/main\" "
            "xmlns:w14=\"http://schemas.microsoft.com/office/word/2010/wordml\" "
            "xmlns:wpg=\"http://schemas.microsoft.com/office/word/2010/wordprocessingGroup\" "
            "xmlns:wpi=\"http://schemas.microsoft.com/office/word/2010/wordprocessingInk\" "
            "xmlns:wne=\"http://schemas.microsoft.com/office/word/2006/wordml\" "
            "xmlns:wps=\"http://schemas.microsoft.com/office/word/2010/wordprocessingShape\" "
            "mc:Ignorable=\"w14 wp14\">"
            f"<w:body>{paragraphs}<w:sectPr><w:pgSz w:w=\"12240\" w:h=\"15840\"/>"
            "<w:pgMar w:top=\"1440\" w:right=\"1440\" w:bottom=\"1440\" w:left=\"1440\" "
            "w:header=\"708\" w:footer=\"708\" w:gutter=\"0\"/></w:sectPr></w:body></w:document>"
        )
        with ZipFile(path, mode="w", compression=ZIP_DEFLATED) as docx:
            docx.writestr(
                "[Content_Types].xml",
                (
                    "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>"
                    "<Types xmlns=\"http://schemas.openxmlformats.org/package/2006/content-types\">"
                    "<Default Extension=\"rels\" ContentType=\"application/vnd.openxmlformats-package.relationships+xml\"/>"
                    "<Default Extension=\"xml\" ContentType=\"application/xml\"/>"
                    "<Override PartName=\"/word/document.xml\" "
                    "ContentType=\"application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml\"/>"
                    "</Types>"
                ),
            )
            docx.writestr(
                "_rels/.rels",
                (
                    "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>"
                    "<Relationships xmlns=\"http://schemas.openxmlformats.org/package/2006/relationships\">"
                    "<Relationship Id=\"rId1\" "
                    "Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument\" "
                    "Target=\"word/document.xml\"/>"
                    "</Relationships>"
                ),
            )
            docx.writestr(
                "word/_rels/document.xml.rels",
                (
                    "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>"
                    "<Relationships xmlns=\"http://schemas.openxmlformats.org/package/2006/relationships\"/>"
                ),
            )
            docx.writestr("word/document.xml", document_xml)
