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
PERM_TELEMETRY_WRITE = "telemetry.write"
PERM_COMMAND_READ = "command.read"
PERM_COMMAND_WRITE = "command.write"
PERM_ALERT_READ = "alert.read"
PERM_ALERT_WRITE = "alert.write"
PERM_INSPECTION_READ = "inspection:read"
PERM_INSPECTION_WRITE = "inspection:write"
PERM_DEFECT_READ = "defect.read"
PERM_DEFECT_WRITE = "defect.write"
PERM_INCIDENT_READ = "incident.read"
PERM_INCIDENT_WRITE = "incident.write"
PERM_DASHBOARD_READ = "dashboard.read"
PERM_APPROVAL_READ = "approval.read"
PERM_APPROVAL_WRITE = "approval.write"
PERM_REPORTING_READ = "reporting.read"
PERM_REPORTING_WRITE = "reporting.write"
PERM_PLATFORM_SUPER_ADMIN = "platform.super_admin"

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
    PERM_TELEMETRY_WRITE,
    PERM_COMMAND_READ,
    PERM_COMMAND_WRITE,
    PERM_ALERT_READ,
    PERM_ALERT_WRITE,
    PERM_INSPECTION_READ,
    PERM_INSPECTION_WRITE,
    PERM_DEFECT_READ,
    PERM_DEFECT_WRITE,
    PERM_INCIDENT_READ,
    PERM_INCIDENT_WRITE,
    PERM_DASHBOARD_READ,
    PERM_APPROVAL_READ,
    PERM_APPROVAL_WRITE,
    PERM_REPORTING_READ,
    PERM_REPORTING_WRITE,
]


def has_permission(claims: dict[str, Any], permission: str) -> bool:
    permissions = claims.get("permissions", [])
    if not isinstance(permissions, list):
        return False
    return permission in permissions or PERM_WILDCARD in permissions
