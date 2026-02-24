from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import event
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, SQLModel, create_engine

from app.domain.models import Incident, InspectionTask, InspectionTemplate, Tenant


@pytest.fixture()
def incident_engine(tmp_path: Path):
    db_path = tmp_path / "incident_test.db"
    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
    )

    @event.listens_for(engine, "connect")
    def _enable_foreign_keys(dbapi_connection: object, _connection_record: object) -> None:
        cursor = dbapi_connection.cursor()  # type: ignore[attr-defined]
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    SQLModel.metadata.create_all(engine)
    return engine


def test_incident_linked_task_composite_fk_enforced_in_db(incident_engine) -> None:
    with Session(incident_engine, expire_on_commit=False) as session:
        tenant_a = Tenant(name="incident-fk-a")
        tenant_b = Tenant(name="incident-fk-b")
        session.add(tenant_a)
        session.add(tenant_b)
        session.flush()

        template_a = InspectionTemplate(
            tenant_id=tenant_a.id,
            name="template-a",
            category="incident-fk",
            description="template-a",
            is_active=True,
        )
        template_b = InspectionTemplate(
            tenant_id=tenant_b.id,
            name="template-b",
            category="incident-fk",
            description="template-b",
            is_active=True,
        )
        session.add(template_a)
        session.add(template_b)
        session.flush()

        task_a = InspectionTask(
            tenant_id=tenant_a.id,
            name="task-a",
            template_id=template_a.id,
            mission_id=None,
            area_geom="",
            priority=5,
        )
        task_b = InspectionTask(
            tenant_id=tenant_b.id,
            name="task-b",
            template_id=template_b.id,
            mission_id=None,
            area_geom="",
            priority=5,
        )
        session.add(task_a)
        session.add(task_b)
        session.commit()

        session.add(
            Incident(
                tenant_id=tenant_a.id,
                title="cross-tenant-link",
                level="HIGH",
                location_geom="POINT(0 0)",
                linked_task_id=task_b.id,
            )
        )
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()

        session.add(
            Incident(
                tenant_id=tenant_a.id,
                title="same-tenant-link",
                level="HIGH",
                location_geom="POINT(1 1)",
                linked_task_id=task_a.id,
            )
        )
        session.commit()
