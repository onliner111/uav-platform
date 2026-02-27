from __future__ import annotations

from collections.abc import Callable
from typing import Annotated, Any

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer

from app.domain.permissions import has_permission
from app.infra.auth import decode_access_token
from app.infra.tenant import set_request_context

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/identity/dev-login")


def get_current_claims(
    request: Request,
    token: str = Depends(oauth2_scheme),
) -> dict[str, Any]:
    try:
        claims = decode_access_token(token)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        ) from exc
    request.state.claims = claims
    set_request_context(claims.get("tenant_id"), claims.get("sub"))
    return claims


def require_perm(permission: str) -> Callable[[dict[str, Any]], dict[str, Any]]:
    def _checker(
        claims: Annotated[dict[str, Any], Depends(get_current_claims)],
    ) -> dict[str, Any]:
        if not has_permission(claims, permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Missing permission: {permission}",
            )
        return claims

    return _checker


def require_any_perm(*permissions: str) -> Callable[[dict[str, Any]], dict[str, Any]]:
    expected = [item for item in permissions if item]

    def _checker(
        claims: Annotated[dict[str, Any], Depends(get_current_claims)],
    ) -> dict[str, Any]:
        if not expected:
            return claims
        if any(has_permission(claims, permission) for permission in expected):
            return claims
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Missing any permission: {', '.join(expected)}",
        )

    return _checker
