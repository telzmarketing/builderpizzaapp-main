from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import re
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from backend.core.exceptions import GatewayError, GatewayNotConfigured

_logger = logging.getLogger(__name__)
PAGARME_SANDBOX_BASE_URL = "https://sdx-api.pagar.me/core/v5"
PAGARME_PRODUCTION_BASE_URL = "https://api.pagar.me/core/v5"
_SENSITIVE = {"secretkey", "cardtoken", "token", "number", "cvv", "cvc", "securitycode"}


def pagarme_base_url(environment: str | None) -> str:
    return PAGARME_PRODUCTION_BASE_URL if (environment or "").lower() == "production" else PAGARME_SANDBOX_BASE_URL


def sanitize_pagarme_payload(value: Any) -> Any:
    if isinstance(value, dict):
        result = {}
        for key, item in value.items():
            normalized = "".join(ch for ch in str(key).lower() if ch.isalnum())
            result[key] = "***" if normalized in _SENSITIVE or normalized.endswith("secret") else sanitize_pagarme_payload(item)
        return result
    if isinstance(value, list):
        return [sanitize_pagarme_payload(item) for item in value]
    return value


def sanitize_pagarme_text(value: str) -> str:
    value = re.sub(r"\b\d{12,19}\b", "***", value or "")
    return re.sub(r'("?(?:cvv|cvc|card_token|token)"?\s*:\s*)"?[^",}\s]+"?', r'\1"***"', value, flags=re.I)


def verify_pagarme_signature(raw_body: bytes, signature: str | None, secret: str | None) -> bool:
    received = (signature or "").strip()
    if received.startswith("sha1="):
        received = received[5:]
    key = (secret or "").strip()
    if not key or not received:
        return False
    expected = hmac.new(key.encode(), raw_body, hashlib.sha1).hexdigest()
    return hmac.compare_digest(expected, received)


class PagarmeClient:
    def __init__(self, secret_key: str | None, *, environment: str = "sandbox", timeout: int = 30):
        self.secret_key = (secret_key or "").strip()
        self.base_url = pagarme_base_url(environment)
        self.timeout = timeout

    def create_order(self, payload: dict[str, Any], *, idempotency_key: str) -> dict[str, Any]:
        return self.request("POST", "/orders", body=payload, idempotency_key=idempotency_key)

    def get_order(self, order_id: str) -> dict[str, Any]:
        return self.request("GET", f"/orders/{order_id}")

    def cancel_charge(self, charge_id: str, *, amount_cents: int | None = None) -> dict[str, Any]:
        body = {"amount": amount_cents} if amount_cents is not None else None
        return self.request("DELETE", f"/charges/{charge_id}", body=body)

    def request(self, method: str, path: str, *, body: dict[str, Any] | None = None, idempotency_key: str | None = None) -> dict[str, Any]:
        if not self.secret_key:
            raise GatewayNotConfigured("pagarme", "pagarme_secret_key")
        auth = base64.b64encode(f"{self.secret_key}:".encode()).decode()
        headers = {"Accept": "application/json", "Content-Type": "application/json", "Authorization": f"Basic {auth}"}
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key
        request = Request(
            f"{self.base_url}{path}",
            data=json.dumps(body).encode() if body is not None else None,
            method=method,
            headers=headers,
        )
        try:
            with urlopen(request, timeout=self.timeout) as response:
                raw = response.read().decode("utf-8")
                return json.loads(raw) if raw else {}
        except HTTPError as exc:
            detail = sanitize_pagarme_text(exc.read().decode("utf-8", errors="replace"))
            _logger.error("Pagar.me HTTP %s %s -> %s: %s", method, path, exc.code, detail[:500])
            raise GatewayError("pagarme", detail or f"HTTP {exc.code}") from exc
        except URLError as exc:
            _logger.error("Pagar.me network error %s %s: %s", method, path, exc.reason)
            raise GatewayError("pagarme", str(exc.reason)) from exc
