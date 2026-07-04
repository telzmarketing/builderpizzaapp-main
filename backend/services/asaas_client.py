from __future__ import annotations

import json
import logging
import re
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from backend.core.exceptions import GatewayError, GatewayNotConfigured

_logger = logging.getLogger(__name__)

ASAAS_SANDBOX_BASE_URL = "https://api-sandbox.asaas.com/v3"
ASAAS_PRODUCTION_BASE_URL = "https://api.asaas.com/v3"
SENSITIVE_KEYS = {
    "access_token",
    "api_key",
    "apikey",
    "token",
    "password",
    "secret",
    "creditcard",
    "creditcardholderinfo",
    "card",
    "number",
    "ccv",
    "cvv",
    "cvc",
    "securitycode",
    "holdername",
    "expirationmonth",
    "expirationyear",
    "expirymonth",
    "expiryyear",
}


def asaas_base_url(environment: str | None) -> str:
    return ASAAS_PRODUCTION_BASE_URL if (environment or "").strip().lower() == "production" else ASAAS_SANDBOX_BASE_URL


def sanitize_asaas_payload(value: Any) -> Any:
    if isinstance(value, dict):
        sanitized: dict[str, Any] = {}
        for key, item in value.items():
            normalized = "".join(ch for ch in str(key).lower() if ch.isalnum())
            if normalized in SENSITIVE_KEYS or normalized.endswith("token") or normalized.endswith("key"):
                sanitized[key] = "***"
            else:
                sanitized[key] = sanitize_asaas_payload(item)
        return sanitized
    if isinstance(value, list):
        return [sanitize_asaas_payload(item) for item in value]
    return value


def sanitize_asaas_text(value: str) -> str:
    sanitized = re.sub(r"\b\d{12,19}\b", "***", value or "")
    sanitized = re.sub(r'("?(?:ccv|cvv|cvc|securityCode)"?\s*:\s*)"?[^",}\s]+"?', r'\1"***"', sanitized, flags=re.IGNORECASE)
    return sanitized


class AsaasClient:
    def __init__(self, api_key: str | None, *, environment: str | None = "sandbox", timeout: int = 60):
        self.api_key = (api_key or "").strip()
        self.environment = environment or "sandbox"
        self.base_url = asaas_base_url(self.environment)
        self.timeout = timeout

    def list_customers(
        self,
        *,
        external_reference: str | None = None,
        cpf_cnpj: str | None = None,
        email: str | None = None,
        limit: int = 10,
    ) -> dict[str, Any]:
        query: dict[str, Any] = {"limit": max(1, min(limit, 100))}
        if external_reference:
            query["externalReference"] = external_reference
        if cpf_cnpj:
            query["cpfCnpj"] = cpf_cnpj
        if email:
            query["email"] = email
        return self.request("GET", "/customers", query=query)

    def create_customer(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self.request("POST", "/customers", body=payload)

    def list_payments(
        self,
        *,
        external_reference: str | None = None,
        customer: str | None = None,
        billing_type: str | None = None,
        limit: int = 10,
    ) -> dict[str, Any]:
        query: dict[str, Any] = {"limit": max(1, min(limit, 100))}
        if external_reference:
            query["externalReference"] = external_reference
        if customer:
            query["customer"] = customer
        if billing_type:
            query["billingType"] = billing_type
        return self.request("GET", "/payments", query=query)

    def create_payment(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self.request("POST", "/payments", body=payload)

    def get_pix_qr_code(self, payment_id: str) -> dict[str, Any]:
        return self.request("GET", f"/payments/{payment_id}/pixQrCode")

    def get_payment(self, payment_id: str) -> dict[str, Any]:
        return self.request("GET", f"/payments/{payment_id}")

    def delete_payment(self, payment_id: str) -> dict[str, Any]:
        return self.request("DELETE", f"/payments/{payment_id}")

    def refund_payment(
        self,
        payment_id: str,
        *,
        value: float | None = None,
        description: str | None = None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {}
        if value is not None:
            body["value"] = round(float(value), 2)
        if description:
            body["description"] = description
        return self.request("POST", f"/payments/{payment_id}/refund", body=body or None)

    def request(
        self,
        method: str,
        path: str,
        *,
        query: dict[str, Any] | None = None,
        body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if not self.api_key:
            raise GatewayNotConfigured("asaas", "ASAAS_API_KEY")

        url = f"{self.base_url}{path}"
        if query:
            compact_query = {key: value for key, value in query.items() if value not in (None, "")}
            if compact_query:
                url = f"{url}?{urlencode(compact_query)}"

        data = json.dumps(body).encode("utf-8") if body is not None else None
        req = Request(
            url,
            data=data,
            method=method,
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                "access_token": self.api_key,
            },
        )

        try:
            with urlopen(req, timeout=self.timeout) as response:
                payload = response.read().decode("utf-8")
                return json.loads(payload) if payload else {}
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            sanitized_detail = sanitize_asaas_text(detail)
            _logger.error(
                "ASAAS HTTP error %s %s -> %s: %s",
                method,
                path,
                exc.code,
                json.dumps(sanitize_asaas_payload({"detail": sanitized_detail}), ensure_ascii=False)[:500],
            )
            raise GatewayError("asaas", sanitized_detail or f"HTTP {exc.code}") from exc
        except URLError as exc:
            _logger.error("ASAAS network error %s %s: %s", method, path, exc.reason)
            raise GatewayError("asaas", str(exc.reason)) from exc
