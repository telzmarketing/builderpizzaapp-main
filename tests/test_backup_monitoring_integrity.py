import ast
import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
COLLECTOR = ROOT / "scripts/collect-telz-monitoring.sh"


CONSTANTS = {
    "SAFE_ID",
    "BACKUP_RUN_ID",
    "SHA256_LINE",
    "BACKUP_COMPONENT_KEYS",
    "REQUIRED_BACKUP_COMPONENTS",
    "BACKUP_METADATA_FILES",
    "FULL_VALIDATION_TTL_SECONDS",
    "MAX_METADATA_BYTES",
}
FUNCTIONS = {
    "trusted_directory_stat",
    "regular_file_stat",
    "utc_timestamp",
    "read_metadata",
    "parse_sha256sums",
    "inspect_backup_set",
    "file_sha256",
    "pg_restore_list_valid",
    "full_validate_backup_set",
    "cache_entry_is_fresh",
    "public_backup_components",
    "existing_backup_entry_ids",
    "remove_stale_backup_snapshots",
}


def collector_source() -> str:
    return COLLECTOR.read_text(encoding="utf-8")


def backup_validation_namespace() -> dict:
    source = collector_source().split("/usr/bin/python3 - <<'PY'\n", 1)[1].rsplit("\nPY\n", 1)[0]
    tree = ast.parse(source)
    selected = []
    for node in tree.body:
        if isinstance(node, ast.Import):
            selected.append(node)
        elif isinstance(node, ast.ImportFrom) and node.module != "grp":
            selected.append(node)
        elif isinstance(node, ast.Assign):
            names = {target.id for target in node.targets if isinstance(target, ast.Name)}
            if names & CONSTANTS:
                selected.append(node)
        elif isinstance(node, ast.FunctionDef) and node.name in FUNCTIONS:
            selected.append(node)
    namespace: dict = {}
    exec(compile(ast.Module(body=selected, type_ignores=[]), str(COLLECTOR), "exec"), namespace)
    real_directory_stat = namespace["trusted_directory_stat"]
    real_file_stat = namespace["regular_file_stat"]
    namespace["trusted_directory_stat"] = lambda path: (
        path.lstat() if path.is_dir() and not path.is_symlink() else None
    )
    namespace["regular_file_stat"] = lambda path: (
        path.lstat() if path.is_file() and not path.is_symlink() else None
    )
    namespace["_production_trusted_directory_stat"] = real_directory_stat
    namespace["_production_regular_file_stat"] = real_file_stat
    return namespace


def create_backup_set(root: Path, run_id: str = "20260809-210000-42") -> Path:
    backup_set = root / run_id
    backup_set.mkdir(parents=True)
    payloads = {
        "database.dump": b"postgres-custom-dump",
        "environment.env": b"DATABASE_URL=postgresql://redacted\n",
        "uploads.tar.gz": b"compressed-uploads",
    }
    components = {}
    for name, content in payloads.items():
        (backup_set / name).write_bytes(content)
        components[name] = {
            "size_bytes": len(content),
            "sha256": hashlib.sha256(content).hexdigest(),
        }
    manifest = {
        "schema_version": 1,
        "backup_id": run_id,
        "created_at": "2026-08-09T21:00:00Z",
        "status": "validated",
        "components": components,
    }
    (backup_set / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    (backup_set / "SHA256SUMS").write_text(
        "".join(f"{components[name]['sha256']}  {name}\n" for name in payloads),
        encoding="ascii",
    )
    return backup_set


def test_backup_projection_requires_real_checksums_and_pg_restore(tmp_path):
    namespace = backup_validation_namespace()
    backup_set = create_backup_set(tmp_path)
    run_id = backup_set.name
    inspection = namespace["inspect_backup_set"](backup_set, run_id, "2026-08-09T21:01:00Z")
    assert inspection["quick_valid"] is True

    pg_restore_calls = []
    namespace["pg_restore_list_valid"] = lambda path: pg_restore_calls.append(path.name) or True
    assert namespace["full_validate_backup_set"](backup_set, inspection) is True
    assert pg_restore_calls == ["database.dump"]

    public_components = namespace["public_backup_components"](inspection, True)
    serialized = json.dumps(public_components)
    assert {item["key"] for item in public_components} == {"database", "environment", "uploads"}
    assert all(item["status"] == "healthy" and item["validated"] for item in public_components)
    assert "sha256" not in serialized
    assert str(backup_set) not in serialized
    assert not any(component["sha256"] in serialized for component in inspection["manifest_components"].values())


def test_tampering_or_non_regular_entries_are_projected_as_critical(tmp_path):
    namespace = backup_validation_namespace()
    backup_set = create_backup_set(tmp_path)
    run_id = backup_set.name

    database_dump = backup_set / "database.dump"
    original = database_dump.read_bytes()
    database_dump.write_bytes(b"X" * len(original))
    inspection = namespace["inspect_backup_set"](backup_set, run_id, "2026-08-09T21:01:00Z")
    assert inspection["quick_valid"] is True
    namespace["pg_restore_list_valid"] = lambda _path: True
    assert namespace["full_validate_backup_set"](backup_set, inspection) is False
    assert all(
        item["status"] == "critical" and item["validated"] is False
        for item in namespace["public_backup_components"](inspection, False)
    )

    uploads = backup_set / "uploads.tar.gz"
    uploads.unlink()
    uploads.mkdir()
    non_regular = namespace["inspect_backup_set"](backup_set, run_id, "2026-08-09T21:01:00Z")
    assert non_regular["quick_valid"] is False


def test_cache_ttl_metadata_invalidation_and_stale_snapshot_cleanup(tmp_path):
    namespace = backup_validation_namespace()
    backup_set = create_backup_set(tmp_path / "sets")
    inspection = namespace["inspect_backup_set"](backup_set, backup_set.name, "2026-08-09T21:01:00Z")
    now = datetime(2026, 8, 9, 21, 5, tzinfo=timezone.utc)
    entry = {
        "fingerprint": inspection["fingerprint"],
        "size_bytes": inspection["size_bytes"],
        "mtime_ns": inspection["mtime_ns"],
        "checked_at": now.isoformat().replace("+00:00", "Z"),
        "validated": True,
    }
    assert namespace["cache_entry_is_fresh"](entry, inspection, now) is True
    assert namespace["cache_entry_is_fresh"](
        entry,
        inspection,
        now + timedelta(seconds=24 * 60 * 60),
    ) is False
    changed = {**inspection, "mtime_ns": inspection["mtime_ns"] + 1}
    assert namespace["cache_entry_is_fresh"](entry, changed, now) is False

    snapshots = tmp_path / "snapshots"
    snapshots.mkdir()
    active = snapshots / f"{backup_set.name}.json"
    stale = snapshots / "removed-set.json"
    stale_run = snapshots / "20260808-210000-99.json"
    active.write_text("{}", encoding="utf-8")
    stale.write_text("{}", encoding="utf-8")
    stale_run.write_text("{}", encoding="utf-8")
    namespace["remove_stale_backup_snapshots"](snapshots, {backup_set.name})
    assert active.exists()
    assert stale.exists()
    assert not stale_run.exists()


def test_collector_uses_root_private_cache_and_never_trusts_manifest_status_alone():
    source = collector_source()
    assert "FULL_VALIDATION_TTL_SECONDS = 24 * 60 * 60" in source
    assert 'cache_root = root / ".cache"' in source
    assert 'cache_root = prepare_private_cache(output_root)' in source
    assert 'cache_file = cache_root / "backup-validation.json"' in source
    assert "os.chown(cache_root, 0, 0)" in source
    assert "os.chmod(cache_root, 0o700)" in source
    assert "os.fchmod(stream.fileno(), 0o600)" in source
    assert "os.fchown(stream.fileno(), 0, 0)" in source
    assert 'PG_RESTORE_BIN="$(realpath -e "$PG_RESTORE_BIN")"' in source
    assert 'require_root_owned_executable "$PG_RESTORE_BIN"' in source
    assert '[str(pg_restore_bin), "--list", str(database_dump)]' in source
    assert "candidate_stat.st_uid != 0" in source
    assert "candidate_stat.st_mode & 0o022" in source
    assert 'manifest.get("status") == "validated"' not in source
    assert 'valid = manifest.get("status") == "validated"' not in source
    assert "remove_stale_backup_snapshots(output_root / \"backups\", active_run_ids)" in source


def test_monitoring_unit_allows_private_cache_and_has_explicit_budget():
    unit = (ROOT / "installer/templates/telz-monitoring.service").read_text(encoding="utf-8")
    assert "ReadWritePaths=/var/lib/telz/monitoring" in unit
    assert "TimeoutStartSec=15min" in unit
