from __future__ import annotations

import json
from typing import Any
from urllib import error, request

from backend.config import get_settings
from backend.services.whatsapp_gateway_provider import WhatsAppProviderResult


class WhatsAppGatewayRuntimeClient:
    def __init__(self):
        settings = get_settings()
        self._base_url = settings.WHATSAPP_GATEWAY_RUNTIME_URL.rstrip("/")
        self._token = settings.WHATSAPP_GATEWAY_RUNTIME_TOKEN.strip()
        self._timeout = settings.WHATSAPP_GATEWAY_RUNTIME_TIMEOUT_SECONDS

    def health(self) -> WhatsAppProviderResult:
        return self._request("GET", "/health")

    def connect_instance(self, *, instance_id: str, name: str | None = None) -> WhatsAppProviderResult:
        return self._request("POST", f"/instances/{instance_id}/connect", {"name": name})

    def get_qr_code(self, *, instance_id: str) -> WhatsAppProviderResult:
        return self._request("GET", f"/instances/{instance_id}/qrcode")

    def request_pairing_code(self, *, instance_id: str, phone_number: str) -> WhatsAppProviderResult:
        return self._request("POST", f"/instances/{instance_id}/pairing-code", {"phone_number": phone_number})

    def get_status(self, *, instance_id: str) -> WhatsAppProviderResult:
        return self._request("GET", f"/instances/{instance_id}/status")

    def disconnect_instance(self, *, instance_id: str) -> WhatsAppProviderResult:
        return self._request("POST", f"/instances/{instance_id}/disconnect")

    def restart_instance(self, *, instance_id: str, name: str | None = None) -> WhatsAppProviderResult:
        return self._request("POST", f"/instances/{instance_id}/restart", {"name": name})

    def send_text_message(self, *, instance_id: str, phone: str, text: str) -> WhatsAppProviderResult:
        return self._request(
            "POST",
            f"/instances/{instance_id}/messages/text",
            {"phone": phone, "text": text},
        )

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
    ) -> WhatsAppProviderResult:
        return self._request(
            "POST",
            f"/instances/{instance_id}/messages/media",
            {
                "phone": phone,
                "media_url": media_url,
                "caption": caption,
                "media_type": media_type,
                "mimetype": mimetype,
                "file_name": file_name,
            },
        )

    def _request(self, method: str, path: str, payload: dict[str, Any] | None = None) -> WhatsAppProviderResult:
        body = None
        headers = {"Accept": "application/json"}
        if payload is not None:
            body = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"

        req = request.Request(f"{self._base_url}{path}", data=body, headers=headers, method=method)
        try:
            with request.urlopen(req, timeout=self._timeout) as response:
                raw = response.read().decode("utf-8")
                data = json.loads(raw) if raw else {}
        except error.HTTPError as exc:
            return self._error_result("runtime_http_error", exc)
        except (error.URLError, TimeoutError, OSError) as exc:
            return WhatsAppProviderResult(
                ok=False,
                status="runtime_offline",
                message="Runtime Baileys local indisponivel.",
                data={"error": str(exc), "runtime_url": self._base_url},
            )
        except json.JSONDecodeError as exc:
            return WhatsAppProviderResult(
                ok=False,
                status="runtime_invalid_response",
                message="Runtime Baileys retornou resposta invalida.",
                data={"error": str(exc), "runtime_url": self._base_url},
            )

        return WhatsAppProviderResult(
            ok=bool(data.get("ok")),
            status=str(data.get("status") or (data.get("data") or {}).get("status") or "ok"),
            message=str(data.get("message") or "Operacao executada."),
            provider_message_id=(data.get("data") or {}).get("provider_message_id") if isinstance(data.get("data"), dict) else None,
            data=data.get("data") if isinstance(data.get("data"), dict) else data,
        )

    def _error_result(self, status: str, exc: error.HTTPError) -> WhatsAppProviderResult:
        try:
            raw = exc.read().decode("utf-8")
            data = json.loads(raw) if raw else {}
        except (OSError, json.JSONDecodeError):
            data = {}
        return WhatsAppProviderResult(
            ok=False,
            status=str(data.get("status") or status),
            message=str(data.get("message") or f"Runtime Baileys retornou HTTP {exc.code}."),
            data={"http_status": exc.code, "runtime_url": self._base_url, **(data.get("data") or {})},
        )
