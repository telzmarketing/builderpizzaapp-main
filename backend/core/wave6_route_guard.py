"""Fail-closed guard for Wave 6 routes that are not fully tenant-scoped yet."""
from __future__ import annotations

from fastapi import HTTPException

from backend.config import get_settings


def require_wave6_route_isolation_complete() -> None:
    """Block legacy Wave 6 route surfaces when Wave 6 tenant ORM is enabled.

    Wave 6 tables already have tenant columns, but several legacy route modules
    still contain raw SQL and ad hoc SQLAlchemy queries. Until a route module is
    migrated end-to-end, enabling the flag must not expose cross-tenant data.
    """
    if get_settings().MULTI_TENANT_WAVE6_ORM_ENABLED:
        raise HTTPException(
            status_code=503,
            detail=(
                "Modulo Wave 6 aguardando isolamento completo de rotas. "
                "A flag MULTI_TENANT_WAVE6_ORM_ENABLED bloqueia esta superficie "
                "para evitar acesso cruzado entre empresas."
            ),
        )


def block_unsafe_wave6_route() -> None:
    """FastAPI dependency alias used by legacy Wave 6 route modules."""
    require_wave6_route_isolation_complete()
