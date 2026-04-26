"""LGPD — Privacy Policy management routes.

Public:  GET /lgpd/current
Admin:   GET/POST/PUT/DELETE /admin/lgpd/...
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.core.response import ok, created
from backend.database import get_db
from backend.models.customer import LgpdPolicy
from backend.routes.admin_auth import get_current_admin

router = APIRouter(prefix="/lgpd", tags=["lgpd"])
admin_router = APIRouter(prefix="/admin/lgpd", tags=["admin-lgpd"])

_DEFAULT_INTRO = (
    "Esta Política de Privacidade descreve como coletamos, usamos e protegemos seus dados pessoais, "
    "em conformidade com a Lei Geral de Proteção de Dados Pessoais (LGPD — Lei nº 13.709/2018)."
)
_DEFAULT_CONTROLLER = (
    "O controlador dos seus dados é a empresa responsável por esta plataforma, "
    "identificada nos termos legais desta política."
)
_DEFAULT_COLLECTED = (
    "Coletamos: nome completo, endereço de e-mail, número de telefone/WhatsApp e endereço de entrega. "
    "Esses dados são fornecidos voluntariamente por você no momento do cadastro."
)
_DEFAULT_USAGE = (
    "Seus dados são utilizados para: processar e entregar seus pedidos; enviar atualizações sobre o status do pedido; "
    "melhorar a sua experiência de uso; e, com o seu consentimento, enviar promoções e novidades."
)
_DEFAULT_RETENTION = (
    "Seus dados serão mantidos pelo prazo necessário para cumprir as finalidades descritas nesta política, "
    "ou enquanto exigido pela legislação vigente. Você pode solicitar a exclusão dos seus dados a qualquer momento."
)
_DEFAULT_RIGHTS = (
    "Nos termos da LGPD, você tem direito a: confirmar a existência de tratamento; acessar seus dados; "
    "corrigir dados incompletos ou desatualizados; solicitar anonimização, bloqueio ou eliminação de dados desnecessários; "
    "revogar o consentimento a qualquer momento; e apresentar reclamação à ANPD."
)
_DEFAULT_CONTACT = (
    "Para exercer seus direitos ou esclarecer dúvidas sobre esta política, entre em contato conosco "
    "pelo e-mail ou telefone disponíveis em nossa loja."
)


# ── Schemas ───────────────────────────────────────────────────────────────────

class LgpdPolicyOut(BaseModel):
    id: str
    version: str
    title: str
    intro_text: Optional[str] = None
    data_controller_text: Optional[str] = None
    data_collected_text: Optional[str] = None
    data_usage_text: Optional[str] = None
    data_retention_text: Optional[str] = None
    rights_text: Optional[str] = None
    contact_text: Optional[str] = None
    marketing_email_label: Optional[str] = None
    marketing_whatsapp_label: Optional[str] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class LgpdPolicyIn(BaseModel):
    version: str
    title: str = "Política de Privacidade e Proteção de Dados"
    intro_text: Optional[str] = None
    data_controller_text: Optional[str] = None
    data_collected_text: Optional[str] = None
    data_usage_text: Optional[str] = None
    data_retention_text: Optional[str] = None
    rights_text: Optional[str] = None
    contact_text: Optional[str] = None
    marketing_email_label: Optional[str] = "Desejo receber promoções e novidades por e-mail"
    marketing_whatsapp_label: Optional[str] = "Desejo receber promoções e novidades pelo WhatsApp"
    is_active: bool = False


# ── Public endpoint ───────────────────────────────────────────────────────────

@router.get("/current")
def get_current_policy(db: Session = Depends(get_db)):
    """Returns the active LGPD policy. Used by registration flow."""
    policy = db.query(LgpdPolicy).filter(LgpdPolicy.is_active == True).first()  # noqa: E712
    if not policy:
        return ok(None)
    return ok(LgpdPolicyOut.model_validate(policy))


# ── Admin endpoints ───────────────────────────────────────────────────────────

@admin_router.get("")
def list_policies(db: Session = Depends(get_db), _=Depends(get_current_admin)):
    policies = db.query(LgpdPolicy).order_by(LgpdPolicy.created_at.desc()).all()
    return ok([LgpdPolicyOut.model_validate(p) for p in policies])


@admin_router.post("")
def create_policy(body: LgpdPolicyIn, db: Session = Depends(get_db), _=Depends(get_current_admin)):
    if body.is_active:
        db.query(LgpdPolicy).update({"is_active": False})
    policy = LgpdPolicy(
        id=str(uuid.uuid4()),
        **body.model_dump(),
    )
    db.add(policy)
    db.commit()
    db.refresh(policy)
    return created(LgpdPolicyOut.model_validate(policy))


@admin_router.post("/seed-default")
def seed_default_policy(db: Session = Depends(get_db), _=Depends(get_current_admin)):
    """Creates a default policy with pre-filled texts if none exists."""
    existing = db.query(LgpdPolicy).first()
    if existing:
        return ok({"message": "Política já existe.", "id": existing.id})
    policy = LgpdPolicy(
        id=str(uuid.uuid4()),
        version="1.0",
        title="Política de Privacidade e Proteção de Dados",
        intro_text=_DEFAULT_INTRO,
        data_controller_text=_DEFAULT_CONTROLLER,
        data_collected_text=_DEFAULT_COLLECTED,
        data_usage_text=_DEFAULT_USAGE,
        data_retention_text=_DEFAULT_RETENTION,
        rights_text=_DEFAULT_RIGHTS,
        contact_text=_DEFAULT_CONTACT,
        marketing_email_label="Desejo receber promoções e novidades por e-mail",
        marketing_whatsapp_label="Desejo receber promoções e novidades pelo WhatsApp",
        is_active=True,
    )
    db.add(policy)
    db.commit()
    db.refresh(policy)
    return created(LgpdPolicyOut.model_validate(policy))


@admin_router.put("/{policy_id}")
def update_policy(
    policy_id: str, body: LgpdPolicyIn,
    db: Session = Depends(get_db), _=Depends(get_current_admin),
):
    policy = db.query(LgpdPolicy).filter(LgpdPolicy.id == policy_id).first()
    if not policy:
        raise HTTPException(status_code=404, detail="Política não encontrada.")

    if body.is_active:
        db.query(LgpdPolicy).filter(LgpdPolicy.id != policy_id).update({"is_active": False})

    for k, v in body.model_dump().items():
        setattr(policy, k, v)
    policy.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(policy)
    return ok(LgpdPolicyOut.model_validate(policy))


@admin_router.delete("/{policy_id}")
def delete_policy(policy_id: str, db: Session = Depends(get_db), _=Depends(get_current_admin)):
    policy = db.query(LgpdPolicy).filter(LgpdPolicy.id == policy_id).first()
    if not policy:
        raise HTTPException(status_code=404, detail="Política não encontrada.")
    if policy.is_active:
        raise HTTPException(status_code=400, detail="Não é possível excluir a política ativa.")
    db.delete(policy)
    db.commit()
    return ok({"deleted": True})


@admin_router.post("/{policy_id}/activate")
def activate_policy(policy_id: str, db: Session = Depends(get_db), _=Depends(get_current_admin)):
    db.query(LgpdPolicy).update({"is_active": False})
    policy = db.query(LgpdPolicy).filter(LgpdPolicy.id == policy_id).first()
    if not policy:
        raise HTTPException(status_code=404, detail="Política não encontrada.")
    policy.is_active = True
    policy.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(policy)
    return ok(LgpdPolicyOut.model_validate(policy))
