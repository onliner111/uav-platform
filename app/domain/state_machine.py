from __future__ import annotations

from enum import StrEnum


class MissionState(StrEnum):
    DRAFT = "DRAFT"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    ABORTED = "ABORTED"


ALLOWED_TRANSITIONS: dict[MissionState, set[MissionState]] = {
    MissionState.DRAFT: {MissionState.APPROVED, MissionState.REJECTED, MissionState.ABORTED},
    MissionState.REJECTED: {MissionState.DRAFT, MissionState.ABORTED},
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


class TaskCenterState(StrEnum):
    DRAFT = "DRAFT"
    APPROVAL_PENDING = "APPROVAL_PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    DISPATCHED = "DISPATCHED"
    IN_PROGRESS = "IN_PROGRESS"
    ACCEPTED = "ACCEPTED"
    ARCHIVED = "ARCHIVED"
    CANCELED = "CANCELED"


TASK_CENTER_ALLOWED_TRANSITIONS: dict[TaskCenterState, set[TaskCenterState]] = {
    TaskCenterState.DRAFT: {
        TaskCenterState.APPROVAL_PENDING,
        TaskCenterState.DISPATCHED,
        TaskCenterState.CANCELED,
    },
    TaskCenterState.APPROVAL_PENDING: {
        TaskCenterState.APPROVED,
        TaskCenterState.REJECTED,
        TaskCenterState.CANCELED,
    },
    TaskCenterState.REJECTED: {
        TaskCenterState.DRAFT,
        TaskCenterState.CANCELED,
    },
    TaskCenterState.APPROVED: {
        TaskCenterState.DISPATCHED,
        TaskCenterState.CANCELED,
    },
    TaskCenterState.DISPATCHED: {
        TaskCenterState.IN_PROGRESS,
        TaskCenterState.CANCELED,
    },
    TaskCenterState.IN_PROGRESS: {
        TaskCenterState.ACCEPTED,
        TaskCenterState.CANCELED,
    },
    TaskCenterState.ACCEPTED: {TaskCenterState.ARCHIVED},
    TaskCenterState.ARCHIVED: set(),
    TaskCenterState.CANCELED: set(),
}


def can_task_center_transition(source: TaskCenterState, target: TaskCenterState) -> bool:
    return target in TASK_CENTER_ALLOWED_TRANSITIONS.get(source, set())
