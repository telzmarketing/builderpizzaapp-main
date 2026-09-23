"""Hard API boundary for single-purpose KDS station accounts."""
from __future__ import annotations


STATION_MODULE_BY_ROLE = {"cozinha": "cozinha", "expedicao": "expedicao"}


def station_path_allowed(role_name: str, path: str) -> bool:
    role_name = role_name.strip().lower()
    module = STATION_MODULE_BY_ROLE.get(role_name)
    if module is None:
        return True
    normalized = path.removeprefix("/api")
    common = {
        "/admin/auth/me",
        "/admin/auth/me/permissions",
        "/admin/auth/tenants",
        "/admin/auth/select-tenant",
        "/admin/auth/change-password",
    }
    if normalized in common:
        return True
    expected = "/kds/kitchen" if module == "cozinha" else "/kds/dispatch"
    return normalized == expected or normalized.startswith(f"{expected}/")
