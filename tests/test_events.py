from __future__ import annotations

from sqlmodel import Session, SQLModel, create_engine, select

from app.domain.models import EventEnvelope, EventRecord
from app.infra.events import EventBus


def test_event_bus_publish_and_subscribe() -> None:
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)

    bus = EventBus()
    seen: list[str] = []

    def handler(event: EventEnvelope) -> None:
        seen.append(event.event_id)

    event = EventEnvelope(
        event_type="telemetry.normalized",
        tenant_id="tenant-a",
        payload={"drone_id": "drone-1"},
    )
    bus.subscribe("telemetry.normalized", handler)

    with Session(engine) as session:
        bus.publish(event, session=session)
        session.commit()

    with Session(engine) as session:
        stored = session.exec(select(EventRecord)).all()

    assert len(stored) == 1
    assert stored[0].event_id == event.event_id
    assert seen == [event.event_id]

