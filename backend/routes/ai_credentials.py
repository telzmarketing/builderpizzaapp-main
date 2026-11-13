"""Central tenant AI credential administration.

Only the Configurações permission can write this resource. AI modules consume
it but do not expose a write endpoint for provider credentials.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.core.rbac_authorization import AuthorizedTenantActor, require_rbac_permission
from backend.database import get_db
from backend.schemas.ai_credentials import TenantAICredentialOut, TenantAICredentialUpdate
from backend.schemas.ai_models import AIModelsOut
from backend.services.ai.credentials import get_tenant_ai_credential, serialize_tenant_ai_credential, upsert_tenant_ai_credential
from backend.services.ai.model_catalog import AIModelCatalogError, list_provider_models

router = APIRouter(prefix="/ai/credentials", tags=["ai-credentials"])
view = require_rbac_permission("configuracoes", "view")
edit = require_rbac_permission("configuracoes", "edit")


@router.get("/central", response_model=TenantAICredentialOut)
def get_central_credential(
    db: Session = Depends(get_db),
    actor: AuthorizedTenantActor = Depends(view),
):
    return serialize_tenant_ai_credential(db, actor.tenant_id)


@router.put("/central", response_model=TenantAICredentialOut)
def update_central_credential(
    body: TenantAICredentialUpdate,
    db: Session = Depends(get_db),
    actor: AuthorizedTenantActor = Depends(edit),
):
    upsert_tenant_ai_credential(db, actor.tenant_id, body.provider, body.api_key)
    db.commit()
    return serialize_tenant_ai_credential(db, actor.tenant_id)


@router.get("/central/models", response_model=AIModelsOut)
def list_central_models(
    provider: str | None = Query(default=None, pattern="^(openai|claude)$"),
    db: Session = Depends(get_db),
    actor: AuthorizedTenantActor = Depends(view),
):
    """Return the live model catalog for this tenant's central credential."""
    credential = get_tenant_ai_credential(db, actor.tenant_id)
    if credential is None or not (credential.api_key or "").strip():
        raise HTTPException(status_code=409, detail="Configure a credencial central antes de listar modelos.")
    if provider is not None and credential.provider != provider:
        raise HTTPException(status_code=409, detail="O provider solicitado nao e o provider central configurado.")
    try:
        models = list_provider_models(credential)
    except AIModelCatalogError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {"provider": credential.provider, "models": models, "credential_source": "central"}
