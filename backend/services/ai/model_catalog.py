from __future__ import annotations

from typing import Any, Literal

import httpx

from backend.models.ai_credentials import TenantAICredential

ProviderName = Literal["openai", "claude"]


class AIModelCatalogError(RuntimeError):
    """A provider model catalog could not be read safely."""


def _provider_url(provider: ProviderName) -> str:
    return "https://api.openai.com/v1/models" if provider == "openai" else "https://api.anthropic.com/v1/models"


def _headers(provider: ProviderName, api_key: str) -> dict[str, str]:
    if provider == "openai":
        return {"Authorization": f"Bearer {api_key}"}
    return {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
    }


def _normalized_model(provider: ProviderName, item: dict[str, Any]) -> dict[str, Any] | None:
    model_id = str(item.get("id") or "").strip()
    if not model_id:
        return None
    return {
        "id": model_id,
        "name": str(item.get("display_name") or item.get("name") or model_id).strip(),
        "provider": provider,
        "owned_by": str(item.get("owned_by") or "").strip() or None,
        "created_at": str(item.get("created_at") or item.get("created") or "").strip() or None,
    }


def list_provider_models(credential: TenantAICredential, *, timeout: float = 15.0) -> list[dict[str, Any]]:
    """List models with the already-resolved tenant credential.

    The credential is accepted only from the tenant-scoped ORM row. It is
    never serialized, returned, or interpolated into an exception message.
    """
    provider = credential.provider
    if provider not in {"openai", "claude"} or not (credential.api_key or "").strip():
        raise AIModelCatalogError("Credencial central de IA nao configurada para este provider.")

    try:
        response = httpx.get(
            _provider_url(provider),
            headers=_headers(provider, credential.api_key.strip()),
            timeout=timeout,
        )
        if response.status_code >= 400:
            raise AIModelCatalogError("Provider recusou a consulta do catalogo de modelos.")
        payload = response.json()
    except AIModelCatalogError:
        raise
    except (httpx.HTTPError, ValueError) as exc:
        raise AIModelCatalogError("Nao foi possivel consultar os modelos do provider configurado.") from exc

    raw_models = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(raw_models, list):
        raise AIModelCatalogError("Resposta invalida do catalogo de modelos do provider.")

    models = [_normalized_model(provider, item) for item in raw_models if isinstance(item, dict)]
    return sorted((model for model in models if model is not None), key=lambda model: model["id"])
