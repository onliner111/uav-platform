from __future__ import annotations

import math
from datetime import datetime
from pathlib import Path

from sqlmodel import Session, select

from app.domain.models import (
    AlertRecord,
    EventRecord,
    KpiGovernanceExportRequest,
    KpiHeatmapBinRecord,
    KpiHeatmapSource,
    KpiSnapshotRecomputeRequest,
    KpiSnapshotRecord,
    Mission,
    MissionRun,
    OutcomeCatalogRecord,
)
from app.infra.db import get_engine


class KpiError(Exception):
    pass


class NotFoundError(KpiError):
    pass


class ConflictError(KpiError):
    pass


class KpiService:
    def _session(self) -> Session:
        return Session(get_engine(), expire_on_commit=False)

    @staticmethod
    def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        radius_km = 6371.0
        d_lat = math.radians(lat2 - lat1)
        d_lon = math.radians(lon2 - lon1)
        a = (
            math.sin(d_lat / 2) ** 2
            + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(d_lon / 2) ** 2
        )
        return 2 * radius_km * math.asin(math.sqrt(a))

    def _aggregate_telemetry(
        self,
        session: Session,
        tenant_id: str,
        from_ts: datetime,
        to_ts: datetime,
    ) -> tuple[float, float]:
        rows = list(
            session.exec(
                select(EventRecord)
                .where(EventRecord.tenant_id == tenant_id)
                .where(EventRecord.event_type == "telemetry.normalized")
                .where(EventRecord.ts >= from_ts)
                .where(EventRecord.ts <= to_ts)
            ).all()
        )
        grouped: dict[str, list[tuple[datetime, float, float]]] = {}
        for row in rows:
            drone_id_raw = row.payload.get("drone_id")
            position_raw = row.payload.get("position", {})
            ts_raw = row.payload.get("ts")
            if not isinstance(drone_id_raw, str):
                continue
            if not isinstance(position_raw, dict):
                continue
            lat = position_raw.get("lat")
            lon = position_raw.get("lon")
            if not isinstance(lat, int | float) or not isinstance(lon, int | float):
                continue
            if isinstance(ts_raw, str):
                try:
                    ts = datetime.fromisoformat(ts_raw.replace("Z", "+00:00"))
                except ValueError:
                    ts = row.ts
            else:
                ts = row.ts
            grouped.setdefault(drone_id_raw, []).append((ts, float(lat), float(lon)))

        duration_seconds = 0.0
        mileage_km = 0.0
        for points in grouped.values():
            points.sort(key=lambda item: item[0])
            if len(points) >= 2:
                duration_seconds += (points[-1][0] - points[0][0]).total_seconds()
            for idx in range(1, len(points)):
                _ts1, lat1, lon1 = points[idx - 1]
                _ts2, lat2, lon2 = points[idx]
                mileage_km += self._haversine_km(lat1, lon1, lat2, lon2)
        return duration_seconds, mileage_km

    def recompute_snapshot(
        self,
        tenant_id: str,
        actor_id: str,
        payload: KpiSnapshotRecomputeRequest,
    ) -> KpiSnapshotRecord:
        if payload.to_ts <= payload.from_ts:
            raise ConflictError("to_ts must be greater than from_ts")

        with self._session() as session:
            missions = list(
                session.exec(
                    select(Mission)
                    .where(Mission.tenant_id == tenant_id)
                    .where(Mission.created_at >= payload.from_ts)
                    .where(Mission.created_at <= payload.to_ts)
                ).all()
            )
            mission_runs = list(
                session.exec(
                    select(MissionRun)
                    .where(MissionRun.tenant_id == tenant_id)
                    .where(MissionRun.started_at >= payload.from_ts)
                    .where(MissionRun.started_at <= payload.to_ts)
                ).all()
            )
            alerts = list(
                session.exec(
                    select(AlertRecord)
                    .where(AlertRecord.tenant_id == tenant_id)
                    .where(AlertRecord.first_seen_at >= payload.from_ts)
                    .where(AlertRecord.first_seen_at <= payload.to_ts)
                ).all()
            )
            outcomes = list(
                session.exec(
                    select(OutcomeCatalogRecord)
                    .where(OutcomeCatalogRecord.tenant_id == tenant_id)
                    .where(OutcomeCatalogRecord.created_at >= payload.from_ts)
                    .where(OutcomeCatalogRecord.created_at <= payload.to_ts)
                ).all()
            )

            flight_duration_sec, flight_mileage_km = self._aggregate_telemetry(
                session,
                tenant_id,
                payload.from_ts,
                payload.to_ts,
            )
            completed_missions = len([item for item in missions if item.state.value == "COMPLETED"])
            mission_completion_rate = (completed_missions / len(missions)) if missions else 0.0

            closed_alert_durations = [
                (item.closed_at - item.first_seen_at).total_seconds()
                for item in alerts
                if item.closed_at is not None
            ]
            alert_closure_avg_sec = (
                sum(closed_alert_durations) / len(closed_alert_durations)
                if closed_alert_durations
                else 0.0
            )
            metrics = {
                "missions_total": len(missions),
                "missions_completed": completed_missions,
                "mission_completion_rate": mission_completion_rate,
                "mission_runs_total": len(mission_runs),
                "flight_duration_sec": round(flight_duration_sec, 2),
                "flight_mileage_km": round(flight_mileage_km, 3),
                "alerts_total": len(alerts),
                "outcomes_total": len(outcomes),
                "alert_closure_avg_sec": round(alert_closure_avg_sec, 2),
            }

            snapshot = KpiSnapshotRecord(
                tenant_id=tenant_id,
                window_type=payload.window_type,
                from_ts=payload.from_ts,
                to_ts=payload.to_ts,
                metrics=metrics,
                generated_by=actor_id,
            )
            session.add(snapshot)
            session.flush()

            bins = self._build_heatmap_bins(tenant_id, snapshot.id, outcomes, alerts)
            for item in bins:
                session.add(item)

            session.commit()
            session.refresh(snapshot)
            return snapshot

    def _build_heatmap_bins(
        self,
        tenant_id: str,
        snapshot_id: str,
        outcomes: list[OutcomeCatalogRecord],
        alerts: list[AlertRecord],
    ) -> list[KpiHeatmapBinRecord]:
        counter: dict[tuple[KpiHeatmapSource, float, float], int] = {}

        for outcome in outcomes:
            if outcome.point_lat is None or outcome.point_lon is None:
                continue
            key = (
                KpiHeatmapSource.OUTCOME,
                round(outcome.point_lat, 2),
                round(outcome.point_lon, 2),
            )
            counter[key] = counter.get(key, 0) + 1

        for alert in alerts:
            position_raw = alert.detail.get("position")
            if not isinstance(position_raw, dict):
                continue
            lat = position_raw.get("lat")
            lon = position_raw.get("lon")
            if not isinstance(lat, int | float) or not isinstance(lon, int | float):
                continue
            key = (
                KpiHeatmapSource.ALERT,
                round(float(lat), 2),
                round(float(lon), 2),
            )
            counter[key] = counter.get(key, 0) + 1

        rows: list[KpiHeatmapBinRecord] = []
        for (source, grid_lat, grid_lon), count in counter.items():
            rows.append(
                KpiHeatmapBinRecord(
                    tenant_id=tenant_id,
                    snapshot_id=snapshot_id,
                    source=source,
                    grid_lat=grid_lat,
                    grid_lon=grid_lon,
                    count=count,
                    detail={},
                )
            )
        return rows

    def list_snapshots(
        self,
        tenant_id: str,
        *,
        from_ts: datetime | None = None,
        to_ts: datetime | None = None,
    ) -> list[KpiSnapshotRecord]:
        with self._session() as session:
            statement = select(KpiSnapshotRecord).where(KpiSnapshotRecord.tenant_id == tenant_id)
            if from_ts is not None:
                statement = statement.where(KpiSnapshotRecord.from_ts >= from_ts)
            if to_ts is not None:
                statement = statement.where(KpiSnapshotRecord.to_ts <= to_ts)
            rows = list(session.exec(statement).all())
            return sorted(rows, key=lambda item: item.generated_at, reverse=True)

    def get_latest_snapshot(self, tenant_id: str) -> KpiSnapshotRecord:
        rows = self.list_snapshots(tenant_id)
        if not rows:
            raise NotFoundError("kpi snapshot not found")
        return rows[0]

    def list_heatmap_bins(
        self,
        tenant_id: str,
        *,
        snapshot_id: str | None = None,
        source: KpiHeatmapSource | None = None,
    ) -> list[KpiHeatmapBinRecord]:
        with self._session() as session:
            if snapshot_id is None:
                latest = self.get_latest_snapshot(tenant_id)
                snapshot_id = latest.id
            statement = (
                select(KpiHeatmapBinRecord)
                .where(KpiHeatmapBinRecord.tenant_id == tenant_id)
                .where(KpiHeatmapBinRecord.snapshot_id == snapshot_id)
            )
            if source is not None:
                statement = statement.where(KpiHeatmapBinRecord.source == source)
            rows = list(session.exec(statement).all())
            return sorted(rows, key=lambda item: (item.source, item.grid_lat, item.grid_lon))

    def export_governance_report(
        self,
        tenant_id: str,
        actor_id: str,
        payload: KpiGovernanceExportRequest,
    ) -> str:
        if payload.from_ts is not None and payload.to_ts is not None:
            snapshot = self.recompute_snapshot(
                tenant_id,
                actor_id,
                KpiSnapshotRecomputeRequest(
                    from_ts=payload.from_ts,
                    to_ts=payload.to_ts,
                    window_type=payload.window_type,
                ),
            )
        else:
            snapshot = self.get_latest_snapshot(tenant_id)
        bins = self.list_heatmap_bins(tenant_id, snapshot_id=snapshot.id)
        top_bins = sorted(bins, key=lambda item: item.count, reverse=True)[:5]
        bin_lines = " | ".join(
            [
                f"{item.source.value}@({item.grid_lat:.2f},{item.grid_lon:.2f})={item.count}"
                for item in top_bins
            ]
        )
        text = (
            f"{payload.title}\n"
            f"window_type={snapshot.window_type.value}\n"
            f"from_ts={snapshot.from_ts.isoformat()}\n"
            f"to_ts={snapshot.to_ts.isoformat()}\n"
            f"missions_total={snapshot.metrics.get('missions_total', 0)}\n"
            f"missions_completed={snapshot.metrics.get('missions_completed', 0)}\n"
            f"mission_completion_rate={snapshot.metrics.get('mission_completion_rate', 0)}\n"
            f"flight_duration_sec={snapshot.metrics.get('flight_duration_sec', 0)}\n"
            f"flight_mileage_km={snapshot.metrics.get('flight_mileage_km', 0)}\n"
            f"alerts_total={snapshot.metrics.get('alerts_total', 0)}\n"
            f"outcomes_total={snapshot.metrics.get('outcomes_total', 0)}\n"
            f"top_heatmap_bins={bin_lines}\n"
        )
        export_dir = Path("logs") / "exports"
        export_dir.mkdir(parents=True, exist_ok=True)
        output_file = export_dir / f"governance_{tenant_id}_{payload.window_type.value.lower()}.pdf"
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
