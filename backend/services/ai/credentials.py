from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from sqlalchemy.orm import Session

from backend.config import get_ai_api_key
from backend.models.ai_credentials import TenantAICredential

ProviderName = Literal["openai", "claude"]


@dataclass(frozen=True)
class ResolvedAICredential:
    provider: str
    api_key: str
    source: str

    @property
    def configured(self) -> bool:
        return bool(self.api_key)


def mask_ai_key(value: str | None) -> str | None:
    key = (value or "").strip()
    if not key:
        return None
    if len(key) <= 10:
        return "configurada"
    return f"{key[:4]}...{key[-4:]}"


def get_tenant_ai_credential(db: Session, tenant_id: str) -> TenantAICredential | None:
    return db.query(TenantAICredential).filter(TenantAICredential.tenant_id == tenant_id).first()


def resolve_ai_credential(
    db: Session | None,
    tenant_id: str | None,
    provider: ProviderName,
    *,
    legacy_key: str | None = None,
) -> ResolvedAICredential:
    """Resolve the shared credential, preserving env/legacy compatibility.

    Once a tenant has a centralized credential, a provider mismatch fails
    closed instead of silently using a second module-specific credential.
    Before migration/configuration, the existing environment and legacy
    module values remain read-only fallbacks.
    """
    if db is not None and tenant_id:
        central = get_tenant_ai_credential(db, tenant_id)
        if central is not None:
            if central.provider != provider:
                return ResolvedAICredential(provider=provider, api_key="", source="central-mismatch")
            return ResolvedAICredential(provider=provider, api_key=(central.api_key or "").strip(), source="central")

    env_name = "OPENAI_API_KEY" if provider == "openai" else "ANTHROPIC_API_KEY"
    env_key = get_ai_api_key(env_name)
    if env_key:
        return ResolvedAICredential(provider=provider, api_key=env_key.strip(), source="environment")
    if legacy_key and legacy_key.strip():
        return ResolvedAICredential(provider=provider, api_key=legacy_key.strip(), source="legacy")
    return ResolvedAICredential(provider=provider, api_key="", source="none")


def upsert_tenant_ai_credential(db: Session, tenant_id: str, provider: ProviderName, api_key: str) -> TenantAICredential:
    value = api_key.strip()
    if not value:
        raise ValueError("Informe uma chave de IA.")
    row = get_tenant_ai_credential(db, tenant_id)
    if row is None:
        row = TenantAICredential(tenant_id=tenant_id, provider=provider, api_key=value)
        db.add(row)
    else:
        row.provider = provider
        row.api_key = value
    db.flush()
    return row


def serialize_tenant_ai_credential(db: Session, tenant_id: str) -> dict[str, object]:
    row = get_tenant_ai_credential(db, tenant_id)
    return {
        "provider": row.provider if row else None,
        "configured": bool(row and (row.api_key or "").strip()),
        "key_preview": mask_ai_key(row.api_key if row else None),
        "source": "central" if row else "none",
        "centralized": True,
    }
