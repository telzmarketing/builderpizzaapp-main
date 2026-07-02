from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy.orm import Session

from backend.models.agente_whatsapp import (
    AgenteWhatsAppAudioArtifact,
    AgenteWhatsAppMessage,
    AgenteWhatsAppProcessingJob,
    AgenteWhatsAppSession,
)
from backend.models.order import Order


STT_ESTIMATED_USD_PER_AUDIO_MINUTE = 0.006
TTS_ESTIMATED_USD_PER_1K_CHARS = 0.015
CONVERSION_WINDOW_DAYS = 7


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _json_load(value: str | None) -> dict[str, Any]:
    if not value:
        return {}
    try:
        data = json.loads(value)
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _safe_float(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _same_or_after(value: datetime | None, start: datetime) -> bool:
    if not value:
        return False
    if value.tzinfo is None and start.tzinfo is not None:
        value = value.replace(tzinfo=timezone.utc)
    if value.tzinfo is not None and start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)
    return value >= start


def _same_or_before(value: datetime | None, end: datetime) -> bool:
    if not value:
        return False
    if value.tzinfo is None and end.tzinfo is not None:
        value = value.replace(tzinfo=timezone.utc)
    if value.tzinfo is not None and end.tzinfo is None:
        end = end.replace(tzinfo=timezone.utc)
    return value <= end


class AgenteWhatsAppAnalyticsService:
    def __init__(self, db: Session):
        self._db = db

    def audio_metrics(self, *, days: int = 7) -> dict[str, Any]:
        days = max(1, min(int(days or 7), 90))
        end = _now_utc()
        start = end - timedelta(days=days)

        inbound_audio = (
            self._db.query(AgenteWhatsAppMessage)
            .filter(
                AgenteWhatsAppMessage.message_type == "audio",
                AgenteWhatsAppMessage.direction == "inbound",
                AgenteWhatsAppMessage.created_at >= start,
            )
            .all()
        )
        outbound_audio = (
            self._db.query(AgenteWhatsAppMessage)
            .filter(
                AgenteWhatsAppMessage.message_type == "audio",
                AgenteWhatsAppMessage.direction == "outbound",
                AgenteWhatsAppMessage.created_at >= start,
            )
            .all()
        )
        tts_artifacts = (
            self._db.query(AgenteWhatsAppAudioArtifact)
            .filter(
                AgenteWhatsAppAudioArtifact.artifact_type == "tts",
                AgenteWhatsAppAudioArtifact.created_at >= start,
            )
            .all()
        )
        jobs = (
            self._db.query(AgenteWhatsAppProcessingJob)
            .filter(
                AgenteWhatsAppProcessingJob.job_type.in_(["audio_transcription", "agent_response", "tts_generation"]),
                AgenteWhatsAppProcessingJob.created_at >= start,
            )
            .all()
        )

        duration_ms = sum(int(message.media_duration_ms or 0) for message in inbound_audio)
        missing_duration = sum(1 for message in inbound_audio if not message.media_duration_ms)
        audio_minutes = round(duration_ms / 60000, 2)
        tts_chars = sum(len((message.body or "").strip()) for message in outbound_audio)
        tts_latencies = [
            int(_safe_float(_json_load(artifact.payload_json).get("latencia_ms")))
            for artifact in tts_artifacts
            if _safe_float(_json_load(artifact.payload_json).get("latencia_ms")) > 0
        ]
        stt_latencies = [
            int(_safe_float(_json_load(message.transcription_quality_json).get("latencia_ms")))
            for message in inbound_audio
            if _safe_float(_json_load(message.transcription_quality_json).get("latencia_ms")) > 0
        ]

        job_status: dict[str, dict[str, int]] = {}
        for job in jobs:
            item = job_status.setdefault(job.job_type, {"pending": 0, "processing": 0, "done": 0, "failed": 0, "dead": 0})
            item[job.status or "pending"] = item.get(job.status or "pending", 0) + 1

        stt_done = sum(1 for message in inbound_audio if message.transcription_status == "done")
        stt_low = sum(1 for message in inbound_audio if message.transcription_status == "low_confidence")
        stt_failed = sum(1 for message in inbound_audio if message.transcription_status in {"failed", "dead"})
        tts_generated = len(tts_artifacts)
        tts_failed = job_status.get("tts_generation", {}).get("failed", 0) + job_status.get("tts_generation", {}).get("dead", 0)

        estimated_stt_cost = audio_minutes * STT_ESTIMATED_USD_PER_AUDIO_MINUTE
        estimated_tts_cost = (tts_chars / 1000) * TTS_ESTIMATED_USD_PER_1K_CHARS

        return {
            "period": {
                "days": days,
                "start_at": start,
                "end_at": end,
            },
            "audio": {
                "inbound_messages": len(inbound_audio),
                "outbound_messages": len(outbound_audio),
                "audio_minutes": audio_minutes,
                "missing_duration_messages": missing_duration,
                "tts_characters": tts_chars,
            },
            "stt": {
                "done": stt_done,
                "low_confidence": stt_low,
                "failed": stt_failed,
                "success_rate": round((stt_done / len(inbound_audio)) * 100, 2) if inbound_audio else 100.0,
                "avg_latency_ms": round(sum(stt_latencies) / len(stt_latencies), 2) if stt_latencies else None,
            },
            "tts": {
                "generated": tts_generated,
                "failed": tts_failed,
                "avg_latency_ms": round(sum(tts_latencies) / len(tts_latencies), 2) if tts_latencies else None,
            },
            "jobs": job_status,
            "cost_estimate": {
                "currency": "USD",
                "stt": round(estimated_stt_cost, 4),
                "tts": round(estimated_tts_cost, 4),
                "total": round(estimated_stt_cost + estimated_tts_cost, 4),
                "pricing_note": "Estimativa operacional interna; nao substitui o billing oficial do provedor.",
            },
            "conversions": self._conversion_metrics(start=start, end=end),
            "generated_at": end,
        }

    def _conversion_metrics(self, *, start: datetime, end: datetime) -> dict[str, Any]:
        campaign_messages = (
            self._db.query(AgenteWhatsAppMessage)
            .filter(
                AgenteWhatsAppMessage.campaign_id.isnot(None),
                AgenteWhatsAppMessage.created_at >= start,
            )
            .order_by(AgenteWhatsAppMessage.created_at.asc())
            .all()
        )
        by_campaign: dict[str, dict[str, Any]] = {}
        for message in campaign_messages:
            campaign_id = str(message.campaign_id or "")
            if not campaign_id:
                continue
            item = by_campaign.setdefault(
                campaign_id,
                {
                    "campaign_id": campaign_id,
                    "messages": 0,
                    "sessions": set(),
                    "customers": set(),
                    "first_message_at": message.created_at,
                },
            )
            item["messages"] += 1
            item["sessions"].add(message.session_id)
            if message.customer_id:
                item["customers"].add(message.customer_id)
            if message.created_at and message.created_at < item["first_message_at"]:
                item["first_message_at"] = message.created_at

        orders = (
            self._db.query(Order)
            .filter(Order.created_at >= start, Order.created_at <= end + timedelta(days=CONVERSION_WINDOW_DAYS))
            .all()
        )
        total_orders = 0
        total_revenue = 0.0
        items: list[dict[str, Any]] = []

        for data in by_campaign.values():
            first_message_at = data["first_message_at"]
            window_end = first_message_at + timedelta(days=CONVERSION_WINDOW_DAYS)
            customer_ids = data["customers"]
            matched_orders = [
                order
                for order in orders
                if order.customer_id
                and order.customer_id in customer_ids
                and _same_or_after(order.created_at, first_message_at)
                and _same_or_before(order.created_at, window_end)
                and str(order.status) not in {"OrderStatus.cancelled", "OrderStatus.refunded", "cancelled", "refunded"}
            ]
            revenue = sum(float(order.total or 0) for order in matched_orders)
            total_orders += len(matched_orders)
            total_revenue += revenue
            items.append(
                {
                    "campaign_id": data["campaign_id"],
                    "messages": data["messages"],
                    "sessions": len(data["sessions"]),
                    "customers": len(customer_ids),
                    "orders": len(matched_orders),
                    "revenue": round(revenue, 2),
                    "conversion_rate": round((len(matched_orders) / len(customer_ids)) * 100, 2) if customer_ids else 0.0,
                    "attribution": f"customer_window_{CONVERSION_WINDOW_DAYS}d",
                }
            )

        return {
            "campaigns": sorted(items, key=lambda item: item["revenue"], reverse=True)[:10],
            "orders": total_orders,
            "revenue": round(total_revenue, 2),
            "attribution": f"Pedidos de clientes com campanha vinculada em ate {CONVERSION_WINDOW_DAYS} dias.",
        }
