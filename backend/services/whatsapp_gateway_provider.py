from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass
class WhatsAppProviderResult:
    ok: bool
    status: str
    message: str
    provider_message_id: str | None = None
    data: dict[str, Any] | None = None


class WhatsAppProviderInterface(Protocol):
    provider_name: str

    def create_instance(self, *, instance_id: str, name: str) -> WhatsAppProviderResult:
        ...

    def connect_instance(self, *, instance_id: str) -> WhatsAppProviderResult:
        ...

    def get_qr_code(self, *, instance_id: str) -> WhatsAppProviderResult:
        ...

    def request_pairing_code(self, *, instance_id: str, phone_number: str) -> WhatsAppProviderResult:
        ...

    def get_status(self, *, instance_id: str) -> WhatsAppProviderResult:
        ...

    def disconnect_instance(self, *, instance_id: str) -> WhatsAppProviderResult:
        ...

    def delete_instance(self, *, instance_id: str) -> WhatsAppProviderResult:
        ...

    def restart_instance(self, *, instance_id: str) -> WhatsAppProviderResult:
        ...

    def send_text_message(self, *, instance_id: str, phone: str, text: str) -> WhatsAppProviderResult:
        ...

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
        ...

    def receive_message(self, *, payload: dict[str, Any]) -> WhatsAppProviderResult:
        ...

    def receive_webhook(self, *, payload: dict[str, Any]) -> WhatsAppProviderResult:
        ...

    def health_check(self) -> WhatsAppProviderResult:
        ...

    def get_logs(self, *, instance_id: str | None = None) -> WhatsAppProviderResult:
        ...
