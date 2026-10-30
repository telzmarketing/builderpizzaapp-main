"""Signed, non-PII QR payloads used by operational labels."""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from typing import Any

from backend.config import get_settings


QR_VERSION = "TELZQR1"


def _secret() -> bytes:
    secret = get_settings().JWT_SECRET_KEY
    if not secret or len(secret) < 32:
        raise RuntimeError("JWT_SECRET_KEY deve ter ao menos 32 caracteres para QR operacional")
    return secret.encode("utf-8")


def _encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def create_qr_payload(
    *,
    tenant_id: str,
    order_id: str,
    kind: str,
    version_id: str,
    volume_id: str | None = None,
    order_item_id: str | None = None,
    expires_at: int | None = None,
) -> str:
    if kind not in {"receipt", "item", "supply"}:
        raise ValueError("QR operacional invalido")
    claims: dict[str, Any] = {
        "v": QR_VERSION,
        "tenant_id": tenant_id,
        "order_id": order_id,
        "kind": kind,
        "version_id": version_id,
        "exp": expires_at or int(time.time()) + 30 * 24 * 60 * 60,
    }
    if volume_id:
        claims["volume_id"] = volume_id
    if order_item_id:
        claims["order_item_id"] = order_item_id
    encoded = _encode(json.dumps(claims, sort_keys=True, separators=(",", ":")).encode("utf-8"))
    signature = _encode(hmac.new(_secret(), f"{QR_VERSION}.{encoded}".encode("ascii"), hashlib.sha256).digest())
    return f"{QR_VERSION}.{encoded}.{signature}"


def verify_qr_payload(payload: str) -> dict[str, Any]:
    try:
        version, encoded, signature = payload.split(".", 2)
        if version != QR_VERSION:
            raise ValueError("versao")
        expected = _encode(hmac.new(_secret(), f"{version}.{encoded}".encode("ascii"), hashlib.sha256).digest())
        if not hmac.compare_digest(signature, expected):
            raise ValueError("assinatura")
        claims = json.loads(_decode(encoded).decode("utf-8"))
        if claims.get("v") != QR_VERSION or int(claims.get("exp", 0)) < int(time.time()):
            raise ValueError("expirado")
        if claims.get("kind") not in {"receipt", "item", "supply"}:
            raise ValueError("tipo")
        return claims
    except (ValueError, TypeError, KeyError, json.JSONDecodeError, UnicodeDecodeError, base64.binascii.Error) as exc:
        raise ValueError("QR operacional invalido ou expirado") from exc


def qr_token_hash(payload: str) -> str:
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
