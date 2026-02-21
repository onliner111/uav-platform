from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from sqlmodel import Session, select

from app.domain.models import (
    InspectionExport,
    InspectionObservation,
    InspectionObservationCreate,
    InspectionTask,
    InspectionTaskCreate,
    InspectionTaskStatus,
    InspectionTemplate,
    InspectionTemplateCreate,
    InspectionTemplateItem,
    InspectionTemplateItemCreate,
)
from app.infra.db import get_engine
from app.infra.events import event_bus


class InspectionError(Exception):
    pass


class NotFoundError(InspectionError):
    pass


class ConflictError(InspectionError):
    pass


class InspectionService:
    def _session(self) -> Session:
        return Session(get_engine(), expire_on_commit=False)

    def create_template(self, tenant_id: str, payload: InspectionTemplateCreate) -> InspectionTemplate:
        with self._session() as session:
            template = InspectionTemplate(
                tenant_id=tenant_id,
                name=payload.name,
                category=payload.category,
                description=payload.description,
                is_active=payload.is_active,
            )
            session.add(template)
            session.commit()
            session.refresh(template)
        event_bus.publish_dict(
            "inspection.template.created",
            tenant_id,
            {"template_id": template.id, "name": template.name},
        )
        return template

    def list_templates(self, tenant_id: str) -> list[InspectionTemplate]:
        with self._session() as session:
            statement = select(InspectionTemplate).where(InspectionTemplate.tenant_id == tenant_id)
            return list(session.exec(statement).all())

    def get_template(self, tenant_id: str, template_id: str) -> InspectionTemplate:
        with self._session() as session:
            template = session.get(InspectionTemplate, template_id)
            if template is None or template.tenant_id != tenant_id:
                raise NotFoundError("template not found")
            return template

    def create_template_item(
        self,
        tenant_id: str,
        template_id: str,
        payload: InspectionTemplateItemCreate,
    ) -> InspectionTemplateItem:
        with self._session() as session:
            template = session.get(InspectionTemplate, template_id)
            if template is None or template.tenant_id != tenant_id:
                raise NotFoundError("template not found")
            item = InspectionTemplateItem(
                tenant_id=tenant_id,
                template_id=template_id,
                code=payload.code,
                title=payload.title,
                severity_default=payload.severity_default,
                required=payload.required,
                sort_order=payload.sort_order,
            )
            session.add(item)
            session.commit()
            session.refresh(item)
            return item

    def list_template_items(self, tenant_id: str, template_id: str) -> list[InspectionTemplateItem]:
        with self._session() as session:
            template = session.get(InspectionTemplate, template_id)
            if template is None or template.tenant_id != tenant_id:
                raise NotFoundError("template not found")
            statement = (
                select(InspectionTemplateItem)
                .where(InspectionTemplateItem.tenant_id == tenant_id)
                .where(InspectionTemplateItem.template_id == template_id)
            )
            return list(session.exec(statement).all())

    def create_task(self, tenant_id: str, payload: InspectionTaskCreate) -> InspectionTask:
        with self._session() as session:
            template = session.get(InspectionTemplate, payload.template_id)
            if template is None or template.tenant_id != tenant_id:
                raise NotFoundError("template not found")
            task = InspectionTask(
                tenant_id=tenant_id,
                name=payload.name,
                template_id=payload.template_id,
                mission_id=payload.mission_id,
                area_geom=payload.area_geom,
                priority=payload.priority,
                status=payload.status,
            )
            session.add(task)
            session.commit()
            session.refresh(task)
        event_bus.publish_dict(
            "inspection.task.created",
            tenant_id,
            {"task_id": task.id, "status": task.status},
        )
        return task

    def list_tasks(self, tenant_id: str, status: InspectionTaskStatus | None = None) -> list[InspectionTask]:
        with self._session() as session:
            statement = select(InspectionTask).where(InspectionTask.tenant_id == tenant_id)
            if status is not None:
                statement = statement.where(InspectionTask.status == status)
            return list(session.exec(statement).all())

    def get_task(self, tenant_id: str, task_id: str) -> InspectionTask:
        with self._session() as session:
            task = session.get(InspectionTask, task_id)
            if task is None or task.tenant_id != tenant_id:
                raise NotFoundError("task not found")
            return task

    def create_observation(
        self,
        tenant_id: str,
        task_id: str,
        payload: InspectionObservationCreate,
    ) -> InspectionObservation:
        with self._session() as session:
            task = session.get(InspectionTask, task_id)
            if task is None or task.tenant_id != tenant_id:
                raise NotFoundError("task not found")
            observation = InspectionObservation(
                tenant_id=tenant_id,
                task_id=task_id,
                drone_id=payload.drone_id,
                ts=payload.ts,
                position_lat=payload.position_lat,
                position_lon=payload.position_lon,
                alt_m=payload.alt_m,
                item_code=payload.item_code,
                severity=payload.severity,
                note=payload.note,
                media_url=payload.media_url,
                confidence=payload.confidence,
            )
            session.add(observation)
            session.commit()
            session.refresh(observation)
        event_bus.publish_dict(
            "inspection.observation.created",
            tenant_id,
            {"task_id": task_id, "observation_id": observation.id, "severity": observation.severity},
        )
        return observation

    def list_observations(self, tenant_id: str, task_id: str) -> list[InspectionObservation]:
        with self._session() as session:
            task = session.get(InspectionTask, task_id)
            if task is None or task.tenant_id != tenant_id:
                raise NotFoundError("task not found")
            statement = (
                select(InspectionObservation)
                .where(InspectionObservation.tenant_id == tenant_id)
                .where(InspectionObservation.task_id == task_id)
            )
            return list(session.exec(statement).all())

    def create_export(self, tenant_id: str, task_id: str, export_format: str) -> InspectionExport:
        if export_format.lower() != "html":
            raise ConflictError("only html export is supported")
        with self._session() as session:
            task = session.get(InspectionTask, task_id)
            if task is None or task.tenant_id != tenant_id:
                raise NotFoundError("task not found")
            observations = list(
                session.exec(
                    select(InspectionObservation)
                    .where(InspectionObservation.tenant_id == tenant_id)
                    .where(InspectionObservation.task_id == task_id)
                ).all()
            )
            export = InspectionExport(
                tenant_id=tenant_id,
                task_id=task_id,
                format="html",
                file_path="",
            )
            session.add(export)
            session.commit()
            session.refresh(export)

            export_dir = Path("logs") / "exports"
            export_dir.mkdir(parents=True, exist_ok=True)
            export_file = export_dir / f"{export.id}.html"
            html = self._render_export_html(task=task, observations=observations)
            export_file.write_text(html, encoding="utf-8")

            export.file_path = str(export_file)
            session.add(export)
            session.commit()
            session.refresh(export)

        event_bus.publish_dict(
            "inspection.export.created",
            tenant_id,
            {"task_id": task_id, "export_id": export.id, "format": export.format},
        )
        return export

    def get_export(self, tenant_id: str, export_id: str) -> InspectionExport:
        with self._session() as session:
            export = session.get(InspectionExport, export_id)
            if export is None or export.tenant_id != tenant_id:
                raise NotFoundError("export not found")
            return export

    def _render_export_html(
        self,
        *,
        task: InspectionTask,
        observations: list[InspectionObservation],
    ) -> str:
        rows = []
        for item in observations:
            rows.append(
                "<tr>"
                f"<td>{item.ts.isoformat()}</td>"
                f"<td>{item.item_code}</td>"
                f"<td>{item.severity}</td>"
                f"<td>{item.position_lat:.6f},{item.position_lon:.6f}</td>"
                f"<td>{item.note}</td>"
                "</tr>"
            )
        table_rows = "\n".join(rows)
        generated_at = datetime.now(UTC).isoformat()
        return (
            "<html><head><meta charset='utf-8'><title>Inspection Export</title></head><body>"
            f"<h1>Inspection Task: {task.name}</h1>"
            f"<p>Task ID: {task.id}</p>"
            f"<p>Generated At: {generated_at}</p>"
            "<table border='1' cellpadding='6' cellspacing='0'>"
            "<thead><tr><th>Time</th><th>Item</th><th>Severity</th><th>Position</th><th>Note</th></tr></thead>"
            f"<tbody>{table_rows}</tbody>"
            "</table></body></html>"
        )
