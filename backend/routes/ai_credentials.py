"""Central tenant AI credential administration.

Only the Configurações permission can write this resource. AI modules consume
it but do not expose a write endpoint for provider credentials.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.core.rbac_authorization import AuthorizedTenantActor, require_rbac_permission
from backend.database import get_db
from backend.schemas.ai_credentials import TenantAICredentialOut, TenantAICredentialUpdate
from backend.services.ai.credentials import serialize_tenant_ai_credential, upsert_tenant_ai_credential

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
