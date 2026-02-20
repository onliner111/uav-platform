from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt

JWT_SECRET = os.getenv("JWT_SECRET", "dev-secret-change-me")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
JWT_EXPIRES_MIN = int(os.getenv("JWT_EXPIRES_MIN", "60"))


def create_access_token(
    *,
    user_id: str,
    tenant_id: str,
    permissions: list[str] | None = None,
    expires_minutes: int | None = None,
) -> str:
    now = datetime.now(UTC)
    expire_delta = timedelta(minutes=expires_minutes or JWT_EXPIRES_MIN)
    payload: dict[str, Any] = {
        "sub": user_id,
        "tenant_id": tenant_id,
        "permissions": permissions or [],
        "iat": int(now.timestamp()),
        "exp": int((now + expire_delta).timestamp()),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> dict[str, Any]:
    decoded = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    if not isinstance(decoded, dict):
        raise ValueError("Invalid token payload")
    return decoded
