from __future__ import annotations

from contextvars import ContextVar

tenant_id_ctx: ContextVar[str | None] = ContextVar("tenant_id", default=None)
user_id_ctx: ContextVar[str | None] = ContextVar("user_id", default=None)


def set_request_context(tenant_id: str | None, user_id: str | None) -> None:
    tenant_id_ctx.set(tenant_id)
    user_id_ctx.set(user_id)


def get_tenant_id() -> str | None:
    return tenant_id_ctx.get()


def get_user_id() -> str | None:
    return user_id_ctx.get()

