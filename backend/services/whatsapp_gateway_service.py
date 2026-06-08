from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib import error, request

from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.models.whatsapp_gateway import (
    WhatsAppGatewayInstance,
    WhatsAppGatewayLog,
    WhatsAppGatewaySchedulerSettings,
    WhatsAppGatewayUpdateLog,
)
from backend.schemas.whatsapp_gateway import WhatsAppGatewayInstanceCreate
from backend.services.whatsapp_gateway_baileys_provider import BaileysProvider
from backend.services.whatsapp_gateway_provider import WhatsAppProviderResult

BAILEYS_PACKAGE = "@whiskeysockets/baileys"
BAILEYS_REGISTRY_URL = "https://registry.npmjs.org/@whiskeysockets%2Fbaileys"


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _json_dump(value: dict[str, Any] | None) -> str:
    return json.dumps(value or {}, ensure_ascii=False, default=str)


def _json_load(value: str | None) -> dict[str, Any]:
    if not value:
        return {}
    try:
        data = json.loads(value)
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _parse_datetime(value: Any) -> datetime | None:
    if not value or not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _version_parts(value: str | None) -> tuple[int, int, int, str]:
    raw = (value or "").strip().lstrip("^~v")
    base, _, prerelease = raw.partition("-")
    parts = []
    for part in base.split(".")[:3]:
        try:
            parts.append(int("".join(ch for ch in part if ch.isdigit()) or "0"))
        except ValueError:
            parts.append(0)
    while len(parts) < 3:
        parts.append(0)
    return parts[0], parts[1], parts[2], prerelease


def _compare_versions(current: str | None, available: str | None) -> int:
    current_parts = _version_parts(current)
    available_parts = _version_parts(available)
    if current_parts[:3] != available_parts[:3]:
        return 1 if available_parts[:3] > current_parts[:3] else -1
    current_pre = current_parts[3]
    available_pre = available_parts[3]
    if current_pre == available_pre:
        return 0
    if current_pre and not available_pre:
        return 1
    if available_pre and not current_pre:
        return -1
    return 1 if available_pre > current_pre else -1


def _classify_update(current: str | None, available: str | None) -> tuple[str | None, str | None]:
    if not current or not available or _compare_versions(current, available) <= 0:
        return None, None
    current_major, current_minor, current_patch, _ = _version_parts(current)
    available_major, available_minor, available_patch, available_pre = _version_parts(available)
    if available_major > current_major:
        return "major", "high"
    if available_minor > current_minor:
        return "minor", "medium"
    if available_patch > current_patch:
        return "patch", "low"
    if available_pre:
        return "prerelease", "medium"
    return "stable", "low"


class WhatsAppGatewayService:
    def __init__(self, db: Session):
        self._db = db

    def overview(self) -> dict[str, Any]:
        scheduler = self.get_scheduler_settings()
        provider = self.provider_status()
        counts = {
            status: count
            for status, count in (
                self._db.query(WhatsAppGatewayInstance.status, func.count(WhatsAppGatewayInstance.id))
                .group_by(WhatsAppGatewayInstance.status)
                .all()
            )
        }
        total = self._db.query(func.count(WhatsAppGatewayInstance.id)).scalar() or 0
        return {
            "total_instances": int(total),
            "connected_instances": int(counts.get("connected", 0)),
            "disconnected_instances": int(counts.get("disconnected", 0)),
            "qr_required_instances": int(counts.get("qr_required", 0)),
            "failed_instances": int(counts.get("error", 0)),
            "provider": provider,
            "scheduler": self.serialize_scheduler_settings(scheduler),
            "recent_logs": [self.serialize_log(log) for log in self.list_logs(limit=8)],
        }

    def list_instances(self) -> list[WhatsAppGatewayInstance]:
        return (
            self._db.query(WhatsAppGatewayInstance)
            .order_by(WhatsAppGatewayInstance.created_at.desc())
            .all()
        )

    def get_instance(self, instance_id: str) -> WhatsAppGatewayInstance | None:
        return (
            self._db.query(WhatsAppGatewayInstance)
            .filter(WhatsAppGatewayInstance.id == instance_id)
            .first()
        )

    def create_instance(self, payload: WhatsAppGatewayInstanceCreate) -> WhatsAppGatewayInstance:
        provider_name = payload.provider.strip().lower()
        if provider_name != "baileys":
            raise ValueError("Provider do Gateway invalido. Use baileys.")

        now = _now_utc()
        instance = WhatsAppGatewayInstance(
            id=str(uuid.uuid4()),
            tenant_id=payload.tenant_id or "default",
            company_id=payload.company_id or "default",
            name=payload.name.strip(),
            phone_number=(payload.phone_number or "").strip() or None,
            provider=provider_name,
            status="created",
            session_key=None,
            metadata_json=_json_dump(payload.metadata),
            created_at=now,
            updated_at=now,
        )
        self._db.add(instance)
        self._db.flush()

        provider = self._provider(provider_name)
        result = provider.create_instance(instance_id=instance.id, name=instance.name)
        self.add_log(
            action="instance_created",
            status="success" if result.ok else "warning",
            message=result.message,
            instance_id=instance.id,
            tenant_id=instance.tenant_id,
            company_id=instance.company_id,
            metadata=result.data,
        )
        self._db.flush()
        return instance

    def list_logs(self, *, instance_id: str | None = None, limit: int = 50) -> list[WhatsAppGatewayLog]:
        q = self._db.query(WhatsAppGatewayLog)
        if instance_id:
            q = q.filter(WhatsAppGatewayLog.instance_id == instance_id)
        return q.order_by(WhatsAppGatewayLog.created_at.desc()).limit(limit).all()

    def connect_instance(self, instance_id: str) -> dict[str, Any]:
        instance = self._require_instance(instance_id)
        result = self._provider(instance.provider).connect_instance(instance_id=instance.id)
        self._apply_runtime_result(instance, result, fallback_status="connecting")
        self._log_runtime_result(instance, "instance_connect", result)
        self._db.flush()
        return self.serialize_runtime_result(instance, result)

    def get_qr_code(self, instance_id: str) -> dict[str, Any]:
        instance = self._require_instance(instance_id)
        result = self._provider(instance.provider).get_qr_code(instance_id=instance.id)
        self._apply_runtime_result(instance, result, fallback_status=instance.status)
        self._db.flush()
        return self.serialize_runtime_result(instance, result)

    def get_instance_status(self, instance_id: str) -> dict[str, Any]:
        instance = self._require_instance(instance_id)
        result = self._provider(instance.provider).get_status(instance_id=instance.id)
        self._apply_runtime_result(instance, result, fallback_status=instance.status)
        self._db.flush()
        return self.serialize_runtime_result(instance, result)

    def disconnect_instance(self, instance_id: str) -> dict[str, Any]:
        instance = self._require_instance(instance_id)
        result = self._provider(instance.provider).disconnect_instance(instance_id=instance.id)
        self._apply_runtime_result(instance, result, fallback_status="disconnected")
        self._log_runtime_result(instance, "instance_disconnect", result)
        self._db.flush()
        return self.serialize_runtime_result(instance, result)

    def restart_instance(self, instance_id: str) -> dict[str, Any]:
        instance = self._require_instance(instance_id)
        result = self._provider(instance.provider).restart_instance(instance_id=instance.id)
        self._apply_runtime_result(instance, result, fallback_status="connecting")
        self._log_runtime_result(instance, "instance_restart", result)
        self._db.flush()
        return self.serialize_runtime_result(instance, result)

    def send_text_message(
        self,
        *,
        phone: str,
        text: str,
        instance_id: str | None = None,
    ) -> WhatsAppProviderResult:
        instance = self._select_send_instance(instance_id)
        if not instance:
            return WhatsAppProviderResult(
                ok=False,
                status="no_connected_instance",
                message="Nenhuma instancia Baileys conectada no WhatsApp Gateway.",
                data={"provider": "baileys"},
            )

        result = self._provider(instance.provider).send_text_message(
            instance_id=instance.id,
            phone=phone,
            text=text,
        )
        self._record_send_result(instance, "message_send_text", result)
        self._db.flush()
        return result

    def send_media_message(
        self,
        *,
        phone: str,
        media_url: str,
        caption: str | None = None,
        media_type: str | None = None,
        mimetype: str | None = None,
        file_name: str | None = None,
        instance_id: str | None = None,
    ) -> WhatsAppProviderResult:
        instance = self._select_send_instance(instance_id)
        if not instance:
            return WhatsAppProviderResult(
                ok=False,
                status="no_connected_instance",
                message="Nenhuma instancia Baileys conectada no WhatsApp Gateway.",
                data={"provider": "baileys"},
            )

        result = self._provider(instance.provider).send_media_message(
            instance_id=instance.id,
            phone=phone,
            media_url=media_url,
            caption=caption,
            media_type=media_type,
            mimetype=mimetype,
            file_name=file_name,
        )
        self._record_send_result(instance, "message_send_media", result)
        self._db.flush()
        return result

    def process_runtime_event(self, payload: dict[str, Any]) -> dict[str, Any]:
        event_type = str(payload.get("event_type") or "")
        instance_id = str(payload.get("instance_id") or "")
        instance = self.get_instance(instance_id) if instance_id else None
        now = _now_utc()
        if instance:
            instance.last_seen_at = now
            instance.updated_at = now

        if event_type != "message_received":
            self.add_log(
                action="runtime_event_ignored",
                status="warning",
                message=f"Evento do runtime ignorado: {event_type or 'sem tipo'}.",
                instance_id=instance.id if instance else None,
                tenant_id=instance.tenant_id if instance else "default",
                company_id=instance.company_id if instance else "default",
                metadata=payload,
            )
            self._db.flush()
            return {"ok": True, "received": 0, "duplicates": 0, "ignored": 1, "message": "Evento ignorado."}

        from backend.services.agente_whatsapp_service import AgenteWhatsAppService

        result = AgenteWhatsAppService(self._db).process_baileys_runtime_event(payload)
        self.add_log(
            action="runtime_message_received",
            status="success" if result.get("received") else "info",
            message="Mensagem inbound Baileys processada pelo AGENTE WHATSAPP.",
            instance_id=instance.id if instance else None,
            tenant_id=instance.tenant_id if instance else "default",
            company_id=instance.company_id if instance else "default",
            metadata={"event": payload, "result": result},
        )
        self._db.flush()
        return {
            "ok": True,
            "received": int(result.get("received") or 0),
            "duplicates": int(result.get("duplicates") or 0),
            "ignored": int(result.get("ignored") or 0),
            "message": "Evento Baileys processado.",
        }

    def add_log(
        self,
        *,
        action: str,
        status: str,
        message: str,
        instance_id: str | None = None,
        tenant_id: str = "default",
        company_id: str = "default",
        metadata: dict[str, Any] | None = None,
    ) -> WhatsAppGatewayLog:
        now = _now_utc()
        log = WhatsAppGatewayLog(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            company_id=company_id,
            instance_id=instance_id,
            action=action,
            status=status,
            message=message,
            metadata_json=_json_dump(metadata),
            created_at=now,
            updated_at=now,
        )
        self._db.add(log)
        return log

    def provider_status(self) -> dict[str, Any]:
        installed_version = self.installed_baileys_version()
        scheduler = self.get_scheduler_settings()
        health = self._provider("baileys").health_check() if installed_version else None
        return {
            "provider": "baileys",
            "package_name": BAILEYS_PACKAGE,
            "installed": bool(installed_version),
            "installed_version": installed_version,
            "runtime_status": health.status if health else "package_missing",
            "production_auto_update_enabled": bool(scheduler.auto_update_production_enabled),
            "update_requires_confirmation": True,
        }

    def update_status(self) -> dict[str, Any]:
        installed_version = self.installed_baileys_version()
        scheduler = self.get_scheduler_settings()
        last_check = self._latest_update_log(action="check")
        available_version = last_check.available_version if last_check else None
        update_type = last_check.update_type if last_check else None
        risk_level = last_check.risk_level if last_check else None
        confirmation_available = bool(
            last_check
            and last_check.status == "confirmation_required"
            and available_version
            and installed_version
            and _compare_versions(installed_version, available_version) > 0
        )
        return {
            "package_name": BAILEYS_PACKAGE,
            "installed": bool(installed_version),
            "installed_version": installed_version,
            "available_version": available_version,
            "update_type": update_type,
            "risk_level": risk_level,
            "check_id": last_check.id if last_check else None,
            "last_checked_at": last_check.finished_at if last_check else None,
            "confirmation_required": True,
            "confirmation_available": confirmation_available,
            "production_auto_update_enabled": bool(scheduler.auto_update_production_enabled),
            "message": self._update_status_message(installed_version, last_check),
        }

    def check_update(self) -> dict[str, Any]:
        installed_version = self.installed_baileys_version()
        scheduler = self.get_scheduler_settings()
        now = _now_utc()
        log = WhatsAppGatewayUpdateLog(
            id=str(uuid.uuid4()),
            tenant_id="default",
            company_id="default",
            package_name=BAILEYS_PACKAGE,
            current_version=installed_version,
            environment="production",
            action="check",
            status="checking",
            started_at=now,
            created_at=now,
            updated_at=now,
        )
        self._db.add(log)
        self._db.flush()

        try:
            available_version = self._fetch_latest_baileys_version()
            update_type, risk_level = _classify_update(installed_version, available_version)
            has_update = bool(update_type)
            log.available_version = available_version
            log.update_type = update_type
            log.risk_level = risk_level
            log.status = "confirmation_required" if has_update else "up_to_date"
            log.finished_at = _now_utc()
            log.updated_at = log.finished_at
            log.error_message = None
        except Exception as exc:
            log.status = "failed"
            log.finished_at = _now_utc()
            log.updated_at = log.finished_at
            log.error_message = str(exc)
            available_version = None
            update_type = None
            risk_level = None

        confirmation_available = log.status == "confirmation_required"
        return {
            "package_name": BAILEYS_PACKAGE,
            "installed": bool(installed_version),
            "installed_version": installed_version,
            "available_version": available_version,
            "update_type": update_type,
            "risk_level": risk_level,
            "check_id": log.id,
            "last_checked_at": log.finished_at,
            "confirmation_required": True,
            "confirmation_available": confirmation_available,
            "production_auto_update_enabled": bool(scheduler.auto_update_production_enabled),
            "message": self._update_status_message(installed_version, log),
        }

    def confirm_update(self, *, check_id: str, target_version: str, confirm: bool) -> dict[str, Any]:
        if not confirm:
            raise ValueError("Confirmacao explicita obrigatoria para atualizar Baileys.")

        check = (
            self._db.query(WhatsAppGatewayUpdateLog)
            .filter(
                WhatsAppGatewayUpdateLog.id == check_id,
                WhatsAppGatewayUpdateLog.action == "check",
            )
            .first()
        )
        if not check:
            raise ValueError("Verificacao de atualizacao nao encontrada.")
        if check.status != "confirmation_required":
            raise ValueError("Esta verificacao nao possui atualizacao pendente de confirmacao.")
        if check.available_version != target_version:
            raise ValueError("Versao confirmada diferente da versao disponivel na verificacao.")

        now = _now_utc()
        check.status = "confirmed"
        check.updated_at = now
        confirmation = WhatsAppGatewayUpdateLog(
            id=str(uuid.uuid4()),
            tenant_id=check.tenant_id,
            company_id=check.company_id,
            package_name=BAILEYS_PACKAGE,
            current_version=check.current_version,
            available_version=check.available_version,
            update_type=check.update_type,
            risk_level=check.risk_level,
            environment="production",
            action="confirm",
            status="confirmed",
            started_at=now,
            finished_at=now,
            rollback_version=check.current_version,
            created_at=now,
            updated_at=now,
        )
        self._db.add(confirmation)
        self.add_log(
            action="update_confirmed",
            status="warning",
            message=f"Atualizacao Baileys confirmada manualmente para {target_version}. Aplicacao exige deploy controlado.",
            metadata={
                "check_id": check_id,
                "confirmation_id": confirmation.id,
                "current_version": check.current_version,
                "target_version": target_version,
                "risk_level": check.risk_level,
            },
        )
        self._db.flush()
        return {
            "ok": True,
            "check_id": check_id,
            "target_version": target_version,
            "status": "confirmed",
            "message": "Confirmacao registrada. A atualizacao deve ser aplicada por deploy controlado, nao automaticamente em producao.",
        }

    def get_scheduler_settings(self) -> WhatsAppGatewaySchedulerSettings:
        settings = (
            self._db.query(WhatsAppGatewaySchedulerSettings)
            .filter(WhatsAppGatewaySchedulerSettings.id == "default")
            .first()
        )
        if settings:
            return settings
        now = _now_utc()
        settings = WhatsAppGatewaySchedulerSettings(
            id="default",
            tenant_id="default",
            company_id="default",
            auto_health_check_enabled=True,
            morning_check_time="06:00",
            evening_check_time="18:00",
            auto_update_check_enabled=True,
            auto_update_staging_enabled=False,
            auto_update_production_enabled=False,
            notify_admin_enabled=True,
            created_at=now,
            updated_at=now,
        )
        self._db.add(settings)
        self._db.flush()
        return settings

    def installed_baileys_version(self) -> str | None:
        package_json = Path(__file__).resolve().parents[2] / "package.json"
        try:
            data = json.loads(package_json.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        deps = data.get("dependencies") or {}
        dev_deps = data.get("devDependencies") or {}
        version = deps.get(BAILEYS_PACKAGE) or dev_deps.get(BAILEYS_PACKAGE)
        return str(version).lstrip("^~") if version else None

    def _fetch_latest_baileys_version(self) -> str:
        req = request.Request(BAILEYS_REGISTRY_URL, headers={"Accept": "application/json"})
        try:
            with request.urlopen(req, timeout=8) as response:
                data = json.loads(response.read().decode("utf-8"))
        except error.URLError as exc:
            raise RuntimeError(f"Falha ao consultar npm registry: {exc}") from exc
        except json.JSONDecodeError as exc:
            raise RuntimeError("npm registry retornou JSON invalido.") from exc

        latest = ((data.get("dist-tags") or {}).get("latest") or "").strip()
        if not latest:
            raise RuntimeError("npm registry nao informou dist-tag latest.")
        return latest

    def _latest_update_log(self, *, action: str) -> WhatsAppGatewayUpdateLog | None:
        return (
            self._db.query(WhatsAppGatewayUpdateLog)
            .filter(WhatsAppGatewayUpdateLog.package_name == BAILEYS_PACKAGE, WhatsAppGatewayUpdateLog.action == action)
            .order_by(WhatsAppGatewayUpdateLog.created_at.desc())
            .first()
        )

    def _update_status_message(self, installed_version: str | None, log: WhatsAppGatewayUpdateLog | None) -> str:
        if not installed_version:
            return "Baileys nao instalada."
        if not log:
            return "Baileys instalada. Execute a verificacao para consultar atualizacoes disponiveis."
        if log.status == "failed":
            return f"Falha ao verificar atualizacao: {log.error_message or 'erro desconhecido'}"
        if log.status == "up_to_date":
            return "Baileys esta atualizada conforme ultima verificacao."
        if log.status == "confirmation_required":
            return (
                f"Atualizacao disponivel para {log.available_version}. "
                "Confirmacao manual obrigatoria antes de qualquer deploy em producao."
            )
        if log.status == "confirmed":
            return f"Atualizacao para {log.available_version} ja confirmada para deploy controlado."
        return "Status de atualizacao registrado."

    def serialize_instance(self, instance: WhatsAppGatewayInstance) -> dict[str, Any]:
        return {
            "id": instance.id,
            "tenant_id": instance.tenant_id,
            "company_id": instance.company_id,
            "name": instance.name,
            "phone_number": instance.phone_number,
            "provider": instance.provider,
            "status": instance.status,
            "qr_code": instance.qr_code,
            "connected_at": instance.connected_at,
            "disconnected_at": instance.disconnected_at,
            "last_seen_at": instance.last_seen_at,
            "metadata": _json_load(instance.metadata_json),
            "created_at": instance.created_at,
            "updated_at": instance.updated_at,
        }

    def serialize_runtime_result(self, instance: WhatsAppGatewayInstance, result) -> dict[str, Any]:
        data = result.data or {}
        return {
            "ok": result.ok,
            "message": result.message,
            "instance": self.serialize_instance(instance),
            "runtime": data,
            "qr_code": data.get("qr_code"),
            "qr_code_data_url": data.get("qr_code_data_url"),
        }

    def serialize_log(self, log: WhatsAppGatewayLog) -> dict[str, Any]:
        return {
            "id": log.id,
            "tenant_id": log.tenant_id,
            "company_id": log.company_id,
            "instance_id": log.instance_id,
            "action": log.action,
            "status": log.status,
            "message": log.message,
            "metadata": _json_load(log.metadata_json),
            "created_at": log.created_at,
        }

    def serialize_scheduler_settings(self, settings: WhatsAppGatewaySchedulerSettings) -> dict[str, Any]:
        return {
            "id": settings.id,
            "tenant_id": settings.tenant_id,
            "company_id": settings.company_id,
            "auto_health_check_enabled": settings.auto_health_check_enabled,
            "morning_check_time": settings.morning_check_time,
            "evening_check_time": settings.evening_check_time,
            "auto_update_check_enabled": settings.auto_update_check_enabled,
            "auto_update_staging_enabled": settings.auto_update_staging_enabled,
            "auto_update_production_enabled": settings.auto_update_production_enabled,
            "notify_admin_enabled": settings.notify_admin_enabled,
        }

    def _provider(self, provider_name: str) -> BaileysProvider:
        if provider_name != "baileys":
            raise ValueError("Provider do Gateway invalido.")
        return BaileysProvider(package_version=self.installed_baileys_version())

    def _require_instance(self, instance_id: str) -> WhatsAppGatewayInstance:
        instance = self.get_instance(instance_id)
        if not instance:
            raise ValueError("Instancia do WhatsApp Gateway nao encontrada.")
        return instance

    def _select_send_instance(self, instance_id: str | None) -> WhatsAppGatewayInstance | None:
        if instance_id:
            instance = self.get_instance(instance_id)
            if instance and instance.provider == "baileys" and instance.status == "connected":
                return instance
            return None

        return (
            self._db.query(WhatsAppGatewayInstance)
            .filter(
                WhatsAppGatewayInstance.provider == "baileys",
                WhatsAppGatewayInstance.status == "connected",
            )
            .order_by(WhatsAppGatewayInstance.last_seen_at.desc().nullslast(), WhatsAppGatewayInstance.created_at.asc())
            .first()
        )

    def _apply_runtime_result(
        self,
        instance: WhatsAppGatewayInstance,
        result,
        *,
        fallback_status: str,
    ) -> None:
        data = result.data or {}
        now = _now_utc()
        status = data.get("status") or result.status or fallback_status
        if status == "ok":
            status = fallback_status

        instance.status = str(status)
        instance.qr_code = data.get("qr_code") if isinstance(data.get("qr_code"), str) else instance.qr_code
        if instance.status == "connected":
            instance.qr_code = None
            instance.connected_at = _parse_datetime(data.get("connected_at")) or now
            instance.disconnected_at = None
        if instance.status in {"disconnected", "logged_out", "runtime_offline", "error"}:
            instance.disconnected_at = _parse_datetime(data.get("disconnected_at")) or now
        phone = data.get("phone_number")
        if isinstance(phone, str) and phone.strip():
            instance.phone_number = phone.strip()
        instance.last_seen_at = _parse_datetime(data.get("last_seen_at")) or now
        instance.updated_at = now

    def _log_runtime_result(self, instance: WhatsAppGatewayInstance, action: str, result) -> None:
        self.add_log(
            action=action,
            status="success" if result.ok else "warning",
            message=result.message,
            instance_id=instance.id,
            tenant_id=instance.tenant_id,
            company_id=instance.company_id,
            metadata=result.data,
        )

    def _record_send_result(self, instance: WhatsAppGatewayInstance, action: str, result: WhatsAppProviderResult) -> None:
        now = _now_utc()
        instance.last_seen_at = now
        instance.updated_at = now
        data = dict(result.data or {})
        data["provider_message_id"] = result.provider_message_id
        self.add_log(
            action=action,
            status="success" if result.ok else "warning",
            message=result.message,
            instance_id=instance.id,
            tenant_id=instance.tenant_id,
            company_id=instance.company_id,
            metadata=data,
        )
