import asyncio
from pathlib import Path
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from backend.services import agente_whatsapp_worker as worker
from backend.services.platform_audit_service import PlatformAuditService


ROOT = Path(__file__).parents[1]


class _FakeDb:
    def __init__(self):
        self.added = []

    def __enter__(self):
        return self

    def __exit__(self, _exc_type, _exc, _traceback):
        return False

    def add(self, row):
        self.added.append(row)

    def commit(self):
        return None


class PlatformRuntimeIntegrationTests(TestCase):
    def test_main_registers_every_operational_router_and_runtime_hooks(self):
        source = (ROOT / "backend/main.py").read_text(encoding="utf-8")
        aliases = (
            "platform_session",
            "platform_health",
            "platform_integrations",
            "platform_jobs",
            "platform_gateway",
            "platform_errors",
            "platform_storage",
            "platform_backups",
        )
        for module in aliases:
            alias = f"{module}_routes"
            self.assertIn(f"from backend.routes import {module} as {alias}", source)
            self.assertIn(f'app.include_router({alias}.router, prefix="/api")', source)

        self.assertIn('@app.middleware("http")', source)
        self.assertIn('request.state.request_id = request_id', source)
        self.assertIn('request.state.correlation_id = correlation_id', source)
        self.assertIn('with SessionLocal() as error_db:', source)
        self.assertIn('PlatformErrorService(error_db).capture_exception(', source)

    def test_unhandled_error_journal_log_never_includes_raw_exception_details(self):
        source = (ROOT / "backend/main.py").read_text(encoding="utf-8")
        handler_start = source.index("async def unhandled_exception_handler")
        handler_end = source.index('if __name__ == "__main__"', handler_start)
        handler = source[handler_start:handler_end]

        self.assertNotIn(".exception(", handler)
        self.assertNotIn("exc_info=", handler)
        self.assertNotIn("str(exc)", handler)
        self.assertNotIn("repr(exc)", handler)
        self.assertIn("type(exc).__name__", handler)
        self.assertIn('request_id or "unknown"', handler)
        self.assertIn('correlation_id or "unknown"', handler)

    @patch(
        "backend.services.platform_audit_service.PlatformAuditLog",
        side_effect=lambda **fields: SimpleNamespace(**fields),
    )
    def test_audit_prefers_middleware_state_and_bounds_header_fallback(self, _audit_log):
        db = _FakeDb()
        actor = SimpleNamespace(id="actor-1", name="Operador", email=None, role_id="master")
        request = SimpleNamespace(
            state=SimpleNamespace(request_id="request-from-state", correlation_id="correlation-from-state"),
            headers={
                "x-request-id": "request-from-header",
                "x-correlation-id": "correlation-from-header",
                "user-agent": "test-agent",
            },
            client=SimpleNamespace(host="127.0.0.1"),
        )
        row = PlatformAuditService(db).record(action="runtime_test", actor=actor, request=request)
        self.assertEqual(row.request_id, "request-from-state")
        self.assertEqual(row.correlation_id, "correlation-from-state")

        fallback_request = SimpleNamespace(
            state=SimpleNamespace(),
            headers={
                "x-request-id": "request-from-header",
                "x-correlation-id": "invalid value with spaces",
            },
            client=None,
        )
        fallback = PlatformAuditService(db).record(
            action="runtime_test_fallback",
            actor=actor,
            request=fallback_request,
        )
        self.assertEqual(fallback.request_id, "request-from-header")
        self.assertIsNone(fallback.correlation_id)

    @staticmethod
    def _service_doubles(*, fail=False):
        agente = SimpleNamespace(
            process_scheduled_campaigns=(
                (lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("cycle failed")))
                if fail else (lambda **_kwargs: {"processed": 1})
            ),
            process_scheduled_stories=lambda **_kwargs: {"processed": 0},
            run_due_commercial_automations=lambda **_kwargs: {"queued": 0},
        )
        processing = SimpleNamespace(
            process_audio_transcriptions=lambda **_kwargs: {"processed": 0},
            process_agent_responses=lambda **_kwargs: {"processed": 0},
            process_tts_generations=lambda **_kwargs: {"processed": 0},
        )
        retention = SimpleNamespace(
            should_run_automatic_cleanup=lambda: False,
            audio_cleanup=lambda **_kwargs: {"deleted_files": 0},
        )
        outbox = SimpleNamespace(
            process_pending=lambda **_kwargs: {"processed": 0, "enqueued": 0},
            sync_internal_alerts=lambda: None,
        )
        return agente, processing, retention, outbox

    def _run_single_cycle(self, *, fail=False):
        statuses = []
        agente, processing, retention, outbox = self._service_doubles(fail=fail)

        async def cancel_after_cycle(_interval):
            raise asyncio.CancelledError

        with (
            patch.object(worker, "AgenteWhatsAppService", return_value=agente),
            patch.object(worker, "AgenteWhatsAppProcessingService", return_value=processing),
            patch.object(worker, "AgenteWhatsAppRetentionService", return_value=retention),
            patch.object(worker, "AgenteWhatsAppOutboxService", return_value=outbox),
            patch.object(worker, "_worker_instance_key", return_value="host:123"),
            patch.object(
                worker,
                "_record_worker_heartbeat",
                side_effect=lambda _factory, **kwargs: statuses.append(kwargs["status"]),
            ),
            patch.object(worker.asyncio, "sleep", side_effect=cancel_after_cycle),
        ):
            with self.assertRaises(asyncio.CancelledError):
                asyncio.run(worker.run_agente_whatsapp_outbox_worker(
                    _FakeDb,
                    interval_seconds=2,
                    batch_size=1,
                ))
        return statuses

    def test_worker_records_success_and_stopped_heartbeats(self):
        self.assertEqual(self._run_single_cycle(), ["running", "stopped"])

    def test_worker_records_degraded_and_stopped_heartbeats(self):
        self.assertEqual(self._run_single_cycle(fail=True), ["degraded", "stopped"])
