import ast
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from backend.schemas.platform_operations import (
    BackupsOverviewOut,
    PlatformHealthOut,
    StorageOverviewOut,
    WorkerHeartbeatOut,
)
from backend.services.platform_backups_service import PlatformBackupsService
from backend.services.platform_health_service import PlatformHealthService
from backend.services.platform_jobs_service import PlatformJobsService
from backend.services.platform_operations_common import PlatformSnapshotReader, redact_text
from backend.services.platform_storage_service import PlatformStorageService


ROOT = Path(__file__).parents[1]
MIGRATION = ROOT / "backend/migrations/versions/20260818_platform_operations.py"


class _ScalarResult:
    def all(self):
        return ["20260818_platform_operations"]


class _DbResult:
    def scalars(self):
        return _ScalarResult()


class _HealthyDb:
    def execute(self, _statement, _params=None):
        return _DbResult()


class _UnusedDb:
    pass


class _MappingsResult:
    def __init__(self, rows):
        self._rows = rows

    def mappings(self):
        return self

    def all(self):
        return self._rows


class _WorkerDb:
    def __init__(self, rows):
        self._rows = rows

    def execute(self, _statement, _params=None):
        return _MappingsResult(self._rows)


def _assignment(tree: ast.Module, name: str):
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == name for target in node.targets
        ):
            return ast.literal_eval(node.value)
    raise AssertionError(f"assignment {name} missing")


def test_operations_migration_is_linear_and_contains_only_operational_tables():
    source = MIGRATION.read_text(encoding="utf-8")
    tree = ast.parse(source)
    assert _assignment(tree, "revision") == "20260818_platform_operations"
    assert _assignment(tree, "down_revision") == "20260817_platform_wave0"
    assert '"platform_error_events"' in source
    assert '"platform_worker_heartbeats"' in source
    assert "uq_platform_error_events_open_fingerprint" in source
    assert "uq_platform_worker_heartbeats_worker_instance" in source
    assert "credentials" not in source.lower()
    assert "payload_json" not in source
    assert "traceback" not in source.lower()


def test_snapshot_reader_rejects_traversal_corruption_and_oversized_files(tmp_path):
    reader = PlatformSnapshotReader(tmp_path)
    (tmp_path / "valid.json").write_text('{"generated_at":"2026-08-03T12:00:00Z"}', encoding="utf-8")
    (tmp_path / "broken.json").write_text("{", encoding="utf-8")
    (tmp_path / "large.json").write_text("x" * 1_048_577, encoding="utf-8")
    assert reader.read_json("valid.json") == {"generated_at": "2026-08-03T12:00:00Z"}
    assert reader.read_json("broken.json") is None
    assert reader.read_json("large.json") is None
    with pytest.raises(ValueError):
        reader.read_json("../outside.json")


def test_missing_snapshots_are_unknown_and_stale_not_healthy(tmp_path):
    snapshots = PlatformSnapshotReader(tmp_path)
    health = PlatformHealthOut.model_validate(
        PlatformHealthService(_HealthyDb(), snapshots=snapshots).get_health()
    )
    storage = StorageOverviewOut.model_validate(
        PlatformStorageService(_UnusedDb(), snapshots=snapshots).overview()
    )
    backups = BackupsOverviewOut.model_validate(
        PlatformBackupsService(snapshots=snapshots).overview()
    )
    assert health.status == "unknown" and health.stale is True
    assert storage.status == "unknown" and storage.stale is True
    assert backups.status == "unknown" and backups.stale is True


def test_worker_heartbeat_response_preserves_each_instance_identity():
    heartbeat_at = datetime.now(timezone.utc)
    rows = [
        {
            "worker_key": "agente_whatsapp",
            "instance_key": "host-a:123",
            "status": "running",
            "last_heartbeat_at": heartbeat_at,
        },
        {
            "worker_key": "agente_whatsapp",
            "instance_key": "host-b:456",
            "status": "idle",
            "last_heartbeat_at": heartbeat_at,
        },
    ]

    workers = [
        WorkerHeartbeatOut.model_validate(item)
        for item in PlatformJobsService(_WorkerDb(rows))._workers()
    ]

    assert [(worker.key, worker.instance_key) for worker in workers] == [
        ("agente_whatsapp", "host-a:123"),
        ("agente_whatsapp", "host-b:456"),
    ]


def test_redaction_removes_secrets_pii_network_and_paths():
    raw = (
        "Bearer token-secret-value password=hunter2 "
        "admin@example.com +55 11 99999-1234 192.0.2.10 "
        "/opt/telz/backend/.env C:\\private\\secret.txt "
        "abcdefghijklmnopqrstuvwxyz0123456789TOKEN"
    )
    redacted = redact_text(raw)
    for sentinel in (
        "token-secret-value", "hunter2", "admin@example.com", "99999-1234",
        "192.0.2.10", "/opt/telz", "C:\\private", "abcdefghijklmnopqrstuvwxyz0123456789TOKEN",
    ):
        assert sentinel not in redacted


@pytest.mark.parametrize("key", [
    "password",
    "passwd",
    "secret",
    "token",
    "api_key",
    "api-key",
    "authorization",
    "cookie",
    "client_secret",
    "access_token",
    "refresh_token",
])
def test_redaction_removes_complete_quoted_and_unquoted_sensitive_values(key):
    literal = "s3nsitive-fragment tail-marker"
    quoted = redact_text(json.dumps({key: literal, "status": "kept"}))
    unquoted = redact_text(f"{key}={literal}; status=kept")

    for redacted in (quoted, unquoted):
        assert "s3nsitive-fragment" not in redacted
        assert "tail-marker" not in redacted
        assert "[REDACTED]" in redacted
    assert json.loads(quoted) == {key: "[REDACTED]", "status": "kept"}
    assert "status=kept" in unquoted


@pytest.mark.parametrize("key", [
    "password_hash",
    "mp_access_token",
    "asaas_api_key",
    "stripe_secret_key",
    "uazapi_token",
    "webhook_secret",
    "jwt_secret_key",
    "client_secret_value",
])
def test_redaction_removes_qualified_sensitive_assignment_keys(key):
    literal = "project-secret-123"
    quoted = redact_text(json.dumps({key: literal, "status": "kept"}))
    unquoted = redact_text(f"{key}={literal}; status=kept")

    assert literal not in quoted
    assert literal not in unquoted
    assert json.loads(quoted) == {key: "[REDACTED]", "status": "kept"}
    assert "status=kept" in unquoted


@pytest.mark.parametrize("safe_text", [
    "tokenizer_status=ready; status=kept",
    "secretary_name=Ana; status=kept",
    "Falha temporaria ao processar pedido 123; status pendente.",
])
def test_redaction_preserves_safe_words_that_only_share_a_prefix(safe_text):
    assert redact_text(safe_text) == safe_text


def test_redaction_removes_basic_uri_and_sensitive_query_credentials():
    basic = redact_text("Authorization: Basic dXNlcjpwYXNz")
    uri = redact_text(
        "GET https://demo-user:super-pass@example.test/callback"
        "?access_token=query-secret&state=keep-me"
    )

    assert "dXNlcjpwYXNz" not in basic
    for sentinel in ("demo-user", "super-pass", "query-secret"):
        assert sentinel not in uri
    assert "state=keep-me" in uri


def test_redaction_consumes_unquoted_secret_with_spaces_and_preserves_safe_text():
    assert redact_text("token=short secret tail") == "token=[REDACTED]"
    safe_text = "Falha temporaria ao processar pedido 123; status pendente."
    assert redact_text(safe_text) == safe_text


def test_snapshot_contracts_strip_unplanned_secret_fields(tmp_path):
    (tmp_path / "health.json").write_text(json.dumps({
        "generated_at": "2026-08-03T12:00:00Z",
        "token": "snapshot-secret",
        "components": [{
            "key": "web", "status": "healthy", "checked_at": "2026-08-03T12:00:00Z",
            "message": "password=should-not-leak", "message_code": "ok",
        }],
    }), encoding="utf-8")
    payload = PlatformHealthService(
        _HealthyDb(), snapshots=PlatformSnapshotReader(tmp_path)
    ).get_health()
    serialized = PlatformHealthOut.model_validate(payload).model_dump_json()
    assert "snapshot-secret" not in serialized
    assert "should-not-leak" not in serialized


def test_operational_routes_are_rbac_protected_and_read_only_except_error_lifecycle():
    expected = {
        "platform_health.py": "monitoring.view",
        "platform_integrations.py": "integrations.view",
        "platform_jobs.py": "jobs.view",
        "platform_gateway.py": "gateway.view",
        "platform_storage.py": "storage.view",
        "platform_backups.py": "backups.view",
    }
    for filename, permission in expected.items():
        source = (ROOT / "backend/routes" / filename).read_text(encoding="utf-8")
        assert f'require_platform_permission("{permission}")' in source
        assert "@router.post" not in source
        assert "@router.put" not in source
        assert "@router.patch" not in source
        assert "@router.delete" not in source
        assert "subprocess" not in source
        assert "systemctl" not in source
        assert "sudo" not in source

    errors = (ROOT / "backend/routes/platform_errors.py").read_text(encoding="utf-8")
    assert 'require_platform_permission("errors.view")' in errors
    assert errors.count('require_platform_permission("errors.manage")') == 2
    assert '@router.post("/{error_id}/acknowledge"' in errors
    assert '@router.post("/{error_id}/resolve"' in errors
    assert "@router.delete" not in errors


def test_services_expose_capture_and_heartbeat_without_http_shell_execution():
    errors = (ROOT / "backend/services/platform_errors_service.py").read_text(encoding="utf-8")
    jobs = (ROOT / "backend/services/platform_jobs_service.py").read_text(encoding="utf-8")
    common = (ROOT / "backend/services/platform_operations_common.py").read_text(encoding="utf-8")
    assert "def capture_exception(" in errors
    assert "def record_heartbeat(" in jobs
    assert "ON CONFLICT (worker_key, instance_key) DO UPDATE" in jobs
    combined = errors + jobs + common
    for forbidden in ("subprocess", "os.system", "systemctl", "sudo "):
        assert forbidden not in combined


def test_sql_projections_never_select_sensitive_operational_columns():
    files = [
        "platform_integrations_service.py",
        "platform_jobs_service.py",
        "platform_gateway_service.py",
    ]
    sources = {name: (ROOT / "backend/services" / name).read_text(encoding="utf-8") for name in files}
    for forbidden in (
        "SELECT credentials_json", "SELECT payload_json", "SELECT session_key",
        "SELECT qr_code", "SELECT access_token_encrypted", "SELECT phone_number",
    ):
        assert all(forbidden not in source for source in sources.values())
    assert "error_present" in sources["platform_jobs_service.py"]
    assert "phone_masked" in sources["platform_gateway_service.py"]
    assert "i.phone_number," not in sources["platform_gateway_service.py"]
    assert "AS phone_suffix" in sources["platform_gateway_service.py"]
