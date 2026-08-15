"""Read-only backup manifests; archives are never opened or exposed."""
from __future__ import annotations

from backend.services.platform_operations_common import (
    PlatformSnapshotReader,
    non_negative_int,
    normalize_health,
    parse_datetime,
    safe_identifier,
    safe_label,
    snapshot_freshness,
    utcnow,
)


COMPONENT_KEYS = ("database", "uploads", "environment", "baileys")


def _components(payload: dict) -> list[dict]:
    source_rows = payload.get("components", [])
    source_by_key = {
        safe_identifier(row.get("key")): row
        for row in source_rows
        if isinstance(row, dict) and safe_identifier(row.get("key")) in COMPONENT_KEYS
    } if isinstance(source_rows, list) else {}
    result = []
    for key in COMPONENT_KEYS:
        source = source_by_key.get(key)
        validated = bool(source.get("validated")) if source else False
        status = normalize_health(source.get("status")) if source else "unknown"
        if status == "healthy" and not validated:
            status = "degraded"
        result.append({
            "key": key,
            "status": status,
            "size_bytes": (
                non_negative_int(source.get("size_bytes"))
                if source and source.get("size_bytes") is not None else None
            ),
            "validated": validated,
        })
    return result


class PlatformBackupsService:
    def __init__(self, *, snapshots: PlatformSnapshotReader | None = None):
        self.snapshots = snapshots or PlatformSnapshotReader()

    def _runs(self) -> list[dict]:
        manifests = self.snapshots.read_directory("backups", limit=100)
        rows = []
        for manifest in manifests:
            run_id = safe_identifier(manifest.get("run_id"), default="", max_length=120)
            if not run_id:
                continue
            components = _components(manifest)
            status = normalize_health(manifest.get("status"))
            component_statuses = {component["status"] for component in components}
            if "critical" in component_statuses:
                status = "critical"
            elif status == "healthy" and ("unknown" in component_statuses or "degraded" in component_statuses):
                status = "degraded"
            rows.append({
                "run_id": run_id,
                "generated_at": parse_datetime(manifest.get("generated_at")),
                "started_at": parse_datetime(manifest.get("started_at")),
                "finished_at": parse_datetime(manifest.get("finished_at")),
                "status": status,
                "components": components,
                "failure_phase": safe_identifier(manifest.get("failure_phase"), default="") or None,
                "failure_code": safe_identifier(manifest.get("failure_code"), default="") or None,
                "schedule": safe_label(manifest.get("schedule"), default="", max_length=80) or None,
                "restore_drill": manifest.get("restore_drill") if isinstance(manifest.get("restore_drill"), dict) else {},
            })
        rows.sort(
            key=lambda row: row["finished_at"] or row["started_at"] or row["generated_at"] or utcnow().replace(year=1970),
            reverse=True,
        )
        return rows

    def overview(self) -> dict:
        rows = self._runs()
        if not rows:
            return {
                "generated_at": utcnow(),
                "stale": True,
                "last_attempt_at": None,
                "last_success_at": None,
                "status": "unknown",
                "age_seconds": None,
                "schedule": None,
                "components": _components({}),
                "restore_drill": {"status": "unknown", "last_tested_at": None},
            }
        latest = rows[0]
        generated_at, stale = snapshot_freshness(
            {"generated_at": latest["generated_at"] or latest["finished_at"] or latest["started_at"]},
            max_age_seconds=36 * 60 * 60,
        )
        successful = next((row for row in rows if row["status"] == "healthy"), None)
        success_at = (
            successful["finished_at"] or successful["started_at"]
            if successful else None
        )
        age_seconds = max(0, int((utcnow() - success_at).total_seconds())) if success_at else None
        drill = latest["restore_drill"]
        return {
            "generated_at": generated_at,
            "stale": stale,
            "last_attempt_at": latest["started_at"],
            "last_success_at": success_at,
            "status": "degraded" if stale and latest["status"] == "healthy" else latest["status"],
            "age_seconds": age_seconds,
            "schedule": latest["schedule"],
            "components": latest["components"],
            "restore_drill": {
                "status": normalize_health(drill.get("status")),
                "last_tested_at": parse_datetime(drill.get("last_tested_at")),
            },
        }

    def list_runs(self, *, limit: int) -> dict:
        rows = self._runs()[:limit]
        return {"items": [{
            "run_id": row["run_id"],
            "started_at": row["started_at"],
            "finished_at": row["finished_at"],
            "status": row["status"],
            "components": row["components"],
            "failure_phase": row["failure_phase"],
            "failure_code": row["failure_code"],
        } for row in rows]}
