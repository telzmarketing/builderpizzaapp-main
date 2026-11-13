from pathlib import Path


ROOT = Path(__file__).parents[1]
WORKER = ROOT / "backend/services/agente_whatsapp_worker.py"
PROCESSING = ROOT / "backend/services/agente_whatsapp_processing_service.py"


def test_wave6_worker_runs_processing_instead_of_deferring():
    source = WORKER.read_text(encoding="utf-8")

    assert "AgenteWhatsAppProcessingService(db, context)" in source
    assert '"deferred": 1' not in source
    assert "wave6_tenant_orm_enabled" not in source


def test_processing_propagates_trusted_context_to_tenant_services():
    source = PROCESSING.read_text(encoding="utf-8")

    for service in (
        "AgenteWhatsAppAIService",
        "AgenteWhatsAppAudioService",
        "AgenteWhatsAppRolloutService",
    ):
        assert f"{service}(" in source
        assert "self._tenant_context" in source

    assert "AgenteWhatsAppOutboxService(" in source
    assert "AgenteWhatsAppAudioSettingsService(" in source


def test_processing_jobs_are_claimed_without_duplicate_workers():
    assert PROCESSING.read_text(encoding="utf-8").count(
        ".with_for_update(skip_locked=True)"
    ) >= 3
