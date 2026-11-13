from datetime import datetime, timezone
import json

from backend.services.agente_whatsapp_ai_service import _json_dump as dump_ai_payload
from backend.services.agente_whatsapp_service import _json_dump as dump_event_payload


def test_ai_payload_serializes_guardrail_datetimes():
    timestamp = datetime(2026, 11, 13, 19, 59, 12, 123456, tzinfo=timezone.utc)

    serialized = dump_ai_payload({"guardrails": {"last_inbound_at": timestamp}})

    assert json.loads(serialized)["guardrails"]["last_inbound_at"] == str(timestamp)


def test_event_payload_serializes_nested_datetimes_for_text_and_audio_jobs():
    timestamp = datetime(2026, 11, 13, 19, 59, 47, tzinfo=timezone.utc)
    payload = {
        "message_type": "text",
        "text_result": {"created_at": timestamp},
        "audio_result": {"transcription_completed_at": timestamp},
    }

    serialized = dump_event_payload(payload)

    decoded = json.loads(serialized)
    assert decoded["text_result"]["created_at"] == str(timestamp)
    assert decoded["audio_result"]["transcription_completed_at"] == str(timestamp)
