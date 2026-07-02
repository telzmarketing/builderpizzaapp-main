from __future__ import annotations

from typing import Any

from backend.services.whatsapp_gateway_provider import WhatsAppProviderResult
from backend.services.whatsapp_gateway_runtime_client import WhatsAppGatewayRuntimeClient


class BaileysProvider:
    provider_name = "baileys"

    def __init__(self, *, package_version: str | None, runtime: WhatsAppGatewayRuntimeClient | None = None):
        self._package_version = package_version
        self._runtime = runtime or WhatsAppGatewayRuntimeClient()

    def _runtime_pending(self, action: str) -> WhatsAppProviderResult:
        installed = bool(self._package_version)
        return WhatsAppProviderResult(
            ok=False,
            status="runtime_pending" if installed else "package_missing",
            message=(
                "Baileys instalada; runtime de conexao sera ativado na Fase 2."
                if installed
                else "Pacote @whiskeysockets/baileys nao instalado."
            ),
            data={"action": action, "installed_version": self._package_version},
        )

    def create_instance(self, *, instance_id: str, name: str) -> WhatsAppProviderResult:
        return WhatsAppProviderResult(
            ok=True,
            status="created",
            message="Instancia registrada para uso com Baileys.",
            data={"instance_id": instance_id, "name": name, "installed_version": self._package_version},
        )

    def connect_instance(self, *, instance_id: str) -> WhatsAppProviderResult:
        if not self._package_version:
            return self._runtime_pending("connect_instance")
        return self._runtime.connect_instance(instance_id=instance_id)

    def get_qr_code(self, *, instance_id: str) -> WhatsAppProviderResult:
        if not self._package_version:
            return self._runtime_pending("get_qr_code")
        return self._runtime.get_qr_code(instance_id=instance_id)

    def request_pairing_code(self, *, instance_id: str, phone_number: str) -> WhatsAppProviderResult:
        if not self._package_version:
            return self._runtime_pending("request_pairing_code")
        return self._runtime.request_pairing_code(instance_id=instance_id, phone_number=phone_number)

    def get_status(self, *, instance_id: str) -> WhatsAppProviderResult:
        if not self._package_version:
            return self._runtime_pending("get_status")
        return self._runtime.get_status(instance_id=instance_id)

    def disconnect_instance(self, *, instance_id: str) -> WhatsAppProviderResult:
        if not self._package_version:
            return self._runtime_pending("disconnect_instance")
        return self._runtime.disconnect_instance(instance_id=instance_id)

    def delete_instance(self, *, instance_id: str) -> WhatsAppProviderResult:
        if not self._package_version:
            return self._runtime_pending("delete_instance")
        return self._runtime.delete_instance(instance_id=instance_id)

    def restart_instance(self, *, instance_id: str) -> WhatsAppProviderResult:
        if not self._package_version:
            return self._runtime_pending("restart_instance")
        return self._runtime.restart_instance(instance_id=instance_id)

    def send_text_message(self, *, instance_id: str, phone: str, text: str) -> WhatsAppProviderResult:
        if not self._package_version:
            return self._runtime_pending("send_text_message")
        return self._runtime.send_text_message(instance_id=instance_id, phone=phone, text=text)

    def send_media_message(
        self,
        *,
        instance_id: str,
        phone: str,
        media_url: str,
        caption: str | None = None,
        media_type: str | None = None,
        mimetype: str | None = None,
        file_name: str | None = None,
        ptt: bool | None = None,
    ) -> WhatsAppProviderResult:
        if not self._package_version:
            return self._runtime_pending("send_media_message")
        return self._runtime.send_media_message(
            instance_id=instance_id,
            phone=phone,
            media_url=media_url,
            caption=caption,
            media_type=media_type,
            mimetype=mimetype,
            file_name=file_name,
            ptt=ptt,
        )

    def receive_message(self, *, payload: dict[str, Any]) -> WhatsAppProviderResult:
        return self._runtime_pending("receive_message")

    def receive_webhook(self, *, payload: dict[str, Any]) -> WhatsAppProviderResult:
        return self._runtime_pending("receive_webhook")

    def health_check(self) -> WhatsAppProviderResult:
        installed = bool(self._package_version)
        if not installed:
            return WhatsAppProviderResult(
                ok=False,
                status="package_missing",
                message="@whiskeysockets/baileys nao encontrada.",
                data={"installed_version": self._package_version},
            )

        result = self._runtime.health()
        data = result.data or {}
        data["installed_version"] = self._package_version
        return WhatsAppProviderResult(
            ok=result.ok,
            status=result.status,
            message=result.message,
            data=data,
        )

    def get_logs(self, *, instance_id: str | None = None) -> WhatsAppProviderResult:
        return self._runtime_pending("get_logs")
