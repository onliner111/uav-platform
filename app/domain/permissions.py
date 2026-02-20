from __future__ import annotations

from typing import Any

PERM_WILDCARD = "*"
PERM_IDENTITY_READ = "identity.read"
PERM_IDENTITY_WRITE = "identity.write"
PERM_REGISTRY_READ = "registry.read"
PERM_REGISTRY_WRITE = "registry.write"
PERM_MISSION_READ = "mission.read"
PERM_MISSION_WRITE = "mission.write"
PERM_MISSION_APPROVE = "mission.approve"
PERM_MISSION_FASTLANE = "mission.fastlane"
PERM_TELEMETRY_READ = "telemetry.read"
PERM_COMMAND_READ = "command.read"
PERM_ALERT_READ = "alert.read"

DEFAULT_PERMISSION_NAMES = [
    PERM_WILDCARD,
    PERM_IDENTITY_READ,
    PERM_IDENTITY_WRITE,
    PERM_REGISTRY_READ,
    PERM_REGISTRY_WRITE,
    PERM_MISSION_READ,
    PERM_MISSION_WRITE,
    PERM_MISSION_APPROVE,
    PERM_MISSION_FASTLANE,
    PERM_TELEMETRY_READ,
    PERM_COMMAND_READ,
    PERM_ALERT_READ,
]


def has_permission(claims: dict[str, Any], permission: str) -> bool:
    permissions = claims.get("permissions", [])
    if not isinstance(permissions, list):
        return False
    return permission in permissions or PERM_WILDCARD in permissions
