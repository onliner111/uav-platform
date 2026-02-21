from __future__ import annotations

from pathlib import Path

from sqlmodel import Session, select

from app.domain.models import (
    Defect,
    DefectStatus,
    DeviceUtilizationRead,
    Drone,
    InspectionTask,
    Mission,
    ReportingClosureRateRead,
    ReportingExportRequest,
    ReportingOverviewRead,
)
from app.infra.db import get_engine
from app.services.defect_service import DefectService


class ReportingService:
    def __init__(self) -> None:
        self._defect_service = DefectService()

    def _session(self) -> Session:
        return Session(get_engine(), expire_on_commit=False)

    def overview(self, tenant_id: str) -> ReportingOverviewRead:
        with self._session() as session:
            missions = list(session.exec(select(Mission).where(Mission.tenant_id == tenant_id)).all())
            inspections = list(session.exec(select(InspectionTask).where(InspectionTask.tenant_id == tenant_id)).all())
            defects = list(session.exec(select(Defect).where(Defect.tenant_id == tenant_id)).all())
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

    def closure_rate(self, tenant_id: str) -> ReportingClosureRateRead:
        stats = self._defect_service.stats(tenant_id)
        return ReportingClosureRateRead(
            total=stats.total,
            closed=stats.closed,
            closure_rate=stats.closure_rate,
        )

    def device_utilization(self, tenant_id: str) -> list[DeviceUtilizationRead]:
        with self._session() as session:
            drones = list(session.exec(select(Drone).where(Drone.tenant_id == tenant_id)).all())
            missions = list(session.exec(select(Mission).where(Mission.tenant_id == tenant_id)).all())
            inspections = list(session.exec(select(InspectionTask).where(InspectionTask.tenant_id == tenant_id)).all())

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

    def export_report(self, tenant_id: str, payload: ReportingExportRequest) -> str:
        overview = self.overview(tenant_id)
        closure = self.closure_rate(tenant_id)
        export_dir = Path("logs") / "exports"
        export_dir.mkdir(parents=True, exist_ok=True)
        output_file = export_dir / f"report_{tenant_id}.pdf"
        text = (
            f"{payload.title}\n"
            f"missions_total={overview.missions_total}\n"
            f"inspections_total={overview.inspections_total}\n"
            f"defects_total={overview.defects_total}\n"
            f"defects_closed={overview.defects_closed}\n"
            f"closure_rate={closure.closure_rate:.4f}\n"
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
