from pathlib import Path


VERSIONS = Path(__file__).parents[1] / "backend/migrations/versions"


def test_whatsapp_campaigns_precedes_audio_delivery_foreign_key():
    migration = (
        VERSIONS / "20260701_whatsapp_audio_phase1_deliveries.py"
    ).read_text(encoding="utf-8")

    assert migration.index(
        "CREATE TABLE IF NOT EXISTS whatsapp_campaigns"
    ) < migration.index(
        "CREATE TABLE IF NOT EXISTS whatsapp_campaign_deliveries"
    )


def test_whatsapp_audio_phase_chain_creates_tables_before_later_usage():
    phase2 = (
        VERSIONS / "20260701_whatsapp_audio_phase2_inbound_jobs.py"
    ).read_text(encoding="utf-8")
    phase3 = (
        VERSIONS / "20260701_whatsapp_audio_phase3_audio_stt.py"
    ).read_text(encoding="utf-8")
    phase5 = (
        VERSIONS / "20260701_whatsapp_audio_phase5_agent_response.py"
    ).read_text(encoding="utf-8")

    assert "CREATE TABLE IF NOT EXISTS agente_whatsapp_processing_jobs" in phase2
    assert "CREATE TABLE IF NOT EXISTS agente_whatsapp_transcriptions" in phase3
    assert 'down_revision = "20260701_whatsapp_audio_phase3_audio_stt"' in phase5
