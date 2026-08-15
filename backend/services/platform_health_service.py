"""Read-only health projection for the Master Central."""
from __future__ import annotations

from time import perf_counter

from sqlalchemy import text

from backend.services.platform_operations_common import (
    PlatformSnapshotReader,
    normalize_health,
    non_negative_int,
    parse_datetime,
    safe_identifier,
    snapshot_freshness,
    utcnow,
)


COMPONENT_LABELS = {
    "api": "API",
    "database": "PostgreSQL",
    "migration": "Alembic",
    "web": "Aplicacao web",
    "nginx": "Nginx",
    "gateway_service": "Servico WhatsApp Gateway",
    "gateway_runtime": "Runtime WhatsApp Gateway",
    "observer": "Coletor operacional",
}
MESSAGE_CODES = {
    "ok": "Verificacao concluida.",
    "timeout": "Tempo limite excedido.",
    "inactive": "Servico inativo.",
    "config_invalid": "Configuracao invalida.",
    "unreachable": "Servico indisponivel.",
    "snapshot_stale": "Coleta operacional desatualizada.",
}


class PlatformHealthService:
    def __init__(self, db, *, snapshots: PlatformSnapshotReader | None = None):
        self.db = db
        self.snapshots = snapshots or PlatformSnapshotReader()

    def _database_components(self) -> list[dict]:
        started = perf_counter()
        try:
            self.db.execute(text("SELECT 1"))
            latency_ms = max(0, round((perf_counter() - started) * 1000))
            database = {
                "key": "database",
                "label": COMPONENT_LABELS["database"],
                "status": "healthy",
                "checked_at": utcnow(),
                "latency_ms": latency_ms,
                "message": MESSAGE_CODES["ok"],
            }
        except Exception:
            return [{
                "key": "database",
                "label": COMPONENT_LABELS["database"],
                "status": "critical",
                "checked_at": utcnow(),
                "latency_ms": None,
                "message": MESSAGE_CODES["unreachable"],
            }, {
                "key": "migration",
                "label": COMPONENT_LABELS["migration"],
                "status": "unknown",
                "checked_at": utcnow(),
                "latency_ms": None,
                "message": None,
            }]

        try:
            revisions = self.db.execute(text(
                "SELECT version_num FROM alembic_version ORDER BY version_num"
            )).scalars().all()
            migration_status = "healthy" if len(revisions) == 1 else "degraded"
            migration_message = MESSAGE_CODES["ok"] if revisions else "Revisao nao identificada."
        except Exception:
            migration_status = "unknown"
            migration_message = None
        return [database, {
            "key": "migration",
            "label": COMPONENT_LABELS["migration"],
            "status": migration_status,
            "checked_at": utcnow(),
            "latency_ms": None,
            "message": migration_message,
        }]

    def get_health(self) -> dict:
        snapshot = self.snapshots.read_json("health.json")
        generated_at, stale = snapshot_freshness(snapshot, max_age_seconds=180)
        components: list[dict] = []
        seen: set[str] = set()
        raw_components = (snapshot or {}).get("components", [])
        if isinstance(raw_components, list):
            for raw in raw_components:
                if not isinstance(raw, dict):
                    continue
                key = safe_identifier(raw.get("key"))
                if key not in COMPONENT_LABELS or key in {"database", "migration"} or key in seen:
                    continue
                seen.add(key)
                code = safe_identifier(raw.get("message_code"), default="")
                components.append({
                    "key": key,
                    "label": COMPONENT_LABELS[key],
                    "status": normalize_health(raw.get("status")),
                    "checked_at": parse_datetime(raw.get("checked_at")) or generated_at,
                    "latency_ms": non_negative_int(raw.get("latency_ms")) if raw.get("latency_ms") is not None else None,
                    "message": MESSAGE_CODES.get(code),
                })
        components.extend(self._database_components())

        if snapshot is None:
            components.append({
                "key": "observer",
                "label": COMPONENT_LABELS["observer"],
                "status": "unknown",
                "checked_at": generated_at,
                "latency_ms": None,
                "message": None,
            })
        elif "observer" not in seen:
            components.append({
                "key": "observer",
                "label": COMPONENT_LABELS["observer"],
                "status": "degraded" if stale else "healthy",
                "checked_at": generated_at,
                "latency_ms": None,
                "message": MESSAGE_CODES["snapshot_stale"] if stale else MESSAGE_CODES["ok"],
            })

        statuses = {component["status"] for component in components}
        if "critical" in statuses:
            overall = "critical"
        elif snapshot is None:
            overall = "unknown"
        elif stale or "degraded" in statuses or "unknown" in statuses:
            overall = "degraded"
        else:
            overall = "healthy"
        alerts: list[str] = []
        if snapshot is None:
            alerts.append("Coleta operacional indisponivel.")
        elif stale:
            alerts.append("Coleta operacional desatualizada.")
        if any(component["key"] == "database" and component["status"] == "critical" for component in components):
            alerts.append("Banco de dados indisponivel.")
        return {
            "status": overall,
            "generated_at": generated_at,
            "stale": stale,
            "components": components,
            "alerts": alerts,
        }
