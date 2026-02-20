from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable
from typing import Any

from sqlmodel import Session

from app.domain.models import EventEnvelope, EventRecord
from app.infra.db import engine

EventHandler = Callable[[EventEnvelope], None]


class EventBus:
    def __init__(self) -> None:
        self._subscribers: dict[str, list[EventHandler]] = defaultdict(list)

    def subscribe(self, event_type: str, handler: EventHandler) -> None:
        self._subscribers[event_type].append(handler)

    def unsubscribe(self, event_type: str, handler: EventHandler) -> None:
        if event_type in self._subscribers and handler in self._subscribers[event_type]:
            self._subscribers[event_type].remove(handler)

    def publish(self, event: EventEnvelope, session: Session | None = None) -> None:
        should_commit = session is None
        if session is None:
            session = Session(engine)
        try:
            record = EventRecord(
                event_id=event.event_id,
                event_type=event.event_type,
                tenant_id=event.tenant_id,
                ts=event.ts,
                actor_id=event.actor_id,
                correlation_id=event.correlation_id,
                payload=event.payload,
            )
            session.add(record)
            if should_commit:
                session.commit()
        finally:
            if should_commit:
                session.close()

        handlers = [*self._subscribers.get(event.event_type, []), *self._subscribers.get("*", [])]
        for handler in handlers:
            handler(event)

    def publish_dict(self, event_type: str, tenant_id: str, payload: dict[str, Any]) -> EventEnvelope:
        event = EventEnvelope(
            event_type=event_type,
            tenant_id=tenant_id,
            payload=payload,
        )
        self.publish(event)
        return event


event_bus = EventBus()

