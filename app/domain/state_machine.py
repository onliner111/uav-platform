from __future__ import annotations

from enum import StrEnum


class MissionState(StrEnum):
    DRAFT = "DRAFT"
    APPROVED = "APPROVED"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    ABORTED = "ABORTED"


ALLOWED_TRANSITIONS: dict[MissionState, set[MissionState]] = {
    MissionState.DRAFT: {MissionState.APPROVED, MissionState.ABORTED},
    MissionState.APPROVED: {MissionState.RUNNING, MissionState.ABORTED},
    MissionState.RUNNING: {
        MissionState.PAUSED,
        MissionState.COMPLETED,
        MissionState.ABORTED,
    },
    MissionState.PAUSED: {MissionState.RUNNING, MissionState.ABORTED},
    MissionState.COMPLETED: set(),
    MissionState.ABORTED: set(),
}


def can_transition(source: MissionState, target: MissionState) -> bool:
    return target in ALLOWED_TRANSITIONS.get(source, set())

