"""
Endpoints administrativos do chatbot — protegidos por JWT.

Prefixo: /admin/chatbot
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.core.response import ok, created, err_msg
from backend.database import get_db
from backend.models.chatbot import (
    ChatbotAutomation, ChatbotConversation, ChatbotFAQ,
    ChatbotKnowledgeDoc, ChatbotMessage, ChatbotSettings,
    ConversationStatus, MessageSender,
)
from backend.models.customer import Customer
from backend.routes.admin_auth import get_current_admin
from backend.schemas.chatbot import (
    AdminReplyIn, ChatbotAIKeysUpdate, ChatbotAnalyticsOut,
    ChatbotAutomationCreate, ChatbotAutomationOut, ChatbotAutomationUpdate,
    ChatbotConversationDetailOut, ChatbotConversationOut,
    ChatbotFAQCreate, ChatbotFAQOut, ChatbotFAQUpdate,
    ChatbotKnowledgeDocCreate, ChatbotKnowledgeDocOut, ChatbotKnowledgeDocUpdate,
    ChatbotMessageOut, ChatbotSettingsOut, ChatbotSettingsUpdate,
    ConversationTagIn, TakeoverIn,
)
from backend.services.ai.factory import check_provider_status
from backend.services.chatbot_service import ChatbotService

router = APIRouter(prefix="/admin/chatbot", tags=["admin-chatbot"])

# ── Settings ──────────────────────────────────────────────────────────────────

@router.get("/settings", response_model=None)
def get_settings(
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    svc = ChatbotService(db)
    s = svc.get_settings()
    return ok(ChatbotSettingsOut.model_validate(s))


@router.put("/settings", response_model=None)
def update_settings(
    body: ChatbotSettingsUpdate,
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    svc = ChatbotService(db)
    s = svc.update_settings(body.model_dump(exclude_none=True))
    return ok(ChatbotSettingsOut.model_validate(s))


@router.get("/settings/ai-status", response_model=None)
def ai_provider_status(
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    """Retorna status das chaves (configurada / não) — sem expor os valores."""
    svc = ChatbotService(db)
    settings = svc.get_settings()
    return ok(check_provider_status(settings))


@router.put("/settings/ai-keys", response_model=None)
def update_ai_keys(
    body: ChatbotAIKeysUpdate,
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    """Salva chaves de IA no banco de dados (coluna chatbot_settings)."""
    if not body.openai_api_key and not body.anthropic_api_key:
        return err_msg("Informe pelo menos uma chave de API.", status_code=400)

    svc = ChatbotService(db)
    settings = svc.get_settings()

    if body.anthropic_api_key:
        settings.anthropic_api_key = body.anthropic_api_key.strip()
    if body.openai_api_key:
        settings.openai_api_key = body.openai_api_key.strip()

    db.commit()
    db.refresh(settings)
    return ok(check_provider_status(settings), "Chaves salvas com sucesso.")


@router.post("/settings/test-ai", response_model=None)
def test_ai_connection(
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    """Testa a conexão com o provedor de IA atual com uma mensagem simples."""
    from backend.services.ai.factory import get_ai_provider
    from backend.services.ai.base import AIMessage

    svc = ChatbotService(db)
    settings = svc.get_settings()
    provider = get_ai_provider(settings)

    if not provider.is_configured():
        return err_msg(f"Chave de API do provedor '{settings.provedor_ia.value}' não configurada.", status_code=400)

    resp = provider.generate(
        system_prompt="Você é um assistente de teste.",
        messages=[AIMessage(role="user", content="Responda apenas: OK")],
        temperatura=0.0,
        max_tokens=10,
    )
    if resp.error_reason:
        return err_msg(
            f"Falha ao chamar IA ({resp.provider}): {resp.error_reason}",
            code="AIProviderError",
            status_code=502,
        )
    return ok({"resposta": resp.content, "latencia_ms": resp.latencia_ms, "tokens": resp.tokens_output})


# ── FAQ ───────────────────────────────────────────────────────────────────────

@router.get("/faq", response_model=None)
def list_faq(
    ativo: Optional[bool] = None,
    categoria: Optional[str] = None,
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    q = db.query(ChatbotFAQ)
    if ativo is not None:
        q = q.filter(ChatbotFAQ.ativo == ativo)
    if categoria:
        q = q.filter(ChatbotFAQ.categoria == categoria)
    items = q.order_by(ChatbotFAQ.prioridade.desc(), ChatbotFAQ.created_at).all()
    return ok([ChatbotFAQOut.model_validate(i) for i in items])


@router.post("/faq", response_model=None, status_code=201)
def create_faq(
    body: ChatbotFAQCreate,
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    faq = ChatbotFAQ(**body.model_dump())
    db.add(faq)
    db.flush()
    _update_faq_vector(db, faq)
    db.commit()
    db.refresh(faq)
    return created(ChatbotFAQOut.model_validate(faq))


@router.put("/faq/{faq_id}", response_model=None)
def update_faq(
    faq_id: str,
    body: ChatbotFAQUpdate,
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    faq = db.query(ChatbotFAQ).filter(ChatbotFAQ.id == faq_id).first()
    if not faq:
        return err_msg("FAQ não encontrado.", status_code=404)
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(faq, k, v)
    _update_faq_vector(db, faq)
    db.commit()
    db.refresh(faq)
    return ok(ChatbotFAQOut.model_validate(faq))


@router.delete("/faq/{faq_id}", response_model=None)
def delete_faq(
    faq_id: str,
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    faq = db.query(ChatbotFAQ).filter(ChatbotFAQ.id == faq_id).first()
    if not faq:
        return err_msg("FAQ não encontrado.", status_code=404)
    db.delete(faq)
    db.commit()
    return ok(None, "FAQ removido.")


# ── Automações ────────────────────────────────────────────────────────────────

@router.get("/automations", response_model=None)
def list_automations(
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    items = db.query(ChatbotAutomation).order_by(ChatbotAutomation.prioridade.desc()).all()
    return ok([ChatbotAutomationOut.model_validate(i) for i in items])


@router.post("/automations", response_model=None, status_code=201)
def create_automation(
    body: ChatbotAutomationCreate,
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    item = ChatbotAutomation(**body.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return created(ChatbotAutomationOut.model_validate(item))


@router.put("/automations/{item_id}", response_model=None)
def update_automation(
    item_id: str,
    body: ChatbotAutomationUpdate,
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    item = db.query(ChatbotAutomation).filter(ChatbotAutomation.id == item_id).first()
    if not item:
        return err_msg("Automação não encontrada.", status_code=404)
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(item, k, v)
    db.commit()
    db.refresh(item)
    return ok(ChatbotAutomationOut.model_validate(item))


@router.delete("/automations/{item_id}", response_model=None)
def delete_automation(
    item_id: str,
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    item = db.query(ChatbotAutomation).filter(ChatbotAutomation.id == item_id).first()
    if not item:
        return err_msg("Automação não encontrada.", status_code=404)
    db.delete(item)
    db.commit()
    return ok(None, "Automação removida.")


# ── Knowledge Docs ────────────────────────────────────────────────────────────

@router.get("/knowledge", response_model=None)
def list_knowledge(
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    items = db.query(ChatbotKnowledgeDoc).order_by(ChatbotKnowledgeDoc.created_at.desc()).all()
    return ok([ChatbotKnowledgeDocOut.model_validate(i) for i in items])


@router.post("/knowledge", response_model=None, status_code=201)
def create_knowledge(
    body: ChatbotKnowledgeDocCreate,
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    doc = ChatbotKnowledgeDoc(**body.model_dump())
    db.add(doc)
    db.flush()
    _update_doc_vector(db, doc)
    db.commit()
    db.refresh(doc)
    return created(ChatbotKnowledgeDocOut.model_validate(doc))


@router.put("/knowledge/{doc_id}", response_model=None)
def update_knowledge(
    doc_id: str,
    body: ChatbotKnowledgeDocUpdate,
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    doc = db.query(ChatbotKnowledgeDoc).filter(ChatbotKnowledgeDoc.id == doc_id).first()
    if not doc:
        return err_msg("Documento não encontrado.", status_code=404)
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(doc, k, v)
    _update_doc_vector(db, doc)
    db.commit()
    db.refresh(doc)
    return ok(ChatbotKnowledgeDocOut.model_validate(doc))


@router.delete("/knowledge/{doc_id}", response_model=None)
def delete_knowledge(
    doc_id: str,
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    doc = db.query(ChatbotKnowledgeDoc).filter(ChatbotKnowledgeDoc.id == doc_id).first()
    if not doc:
        return err_msg("Documento não encontrado.", status_code=404)
    db.delete(doc)
    db.commit()
    return ok(None, "Documento removido.")


# ── Conversas ─────────────────────────────────────────────────────────────────

def _resolve_customer_names(db: Session, convs: list) -> dict[str, str]:
    ids = [c.cliente_id for c in convs if c.cliente_id]
    if not ids:
        return {}
    return {c.id: c.name for c in db.query(Customer).filter(Customer.id.in_(ids)).all()}


def _conv_dict(conv, nome_cliente: Optional[str]) -> dict:
    d = ChatbotConversationOut.model_validate(conv).model_dump()
    d["nome_cliente"] = nome_cliente
    return d


@router.get("/conversations", response_model=None)
def list_conversations(
    status: Optional[str]   = Query(default=None),
    page: int               = Query(default=1, ge=1),
    page_size: int          = Query(default=30, ge=1, le=100),
    db: Session             = Depends(get_db),
    _                       = Depends(get_current_admin),
):
    q = db.query(ChatbotConversation).order_by(ChatbotConversation.iniciada_em.desc())
    if status:
        try:
            q = q.filter(ChatbotConversation.status == ConversationStatus(status))
        except ValueError:
            return err_msg(f"Status inválido: {status}", status_code=400)

    total = q.count()
    items = q.offset((page - 1) * page_size).limit(page_size).all()
    names = _resolve_customer_names(db, items)
    return ok({
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [_conv_dict(c, names.get(c.cliente_id)) for c in items],
    })


@router.get("/conversations/{conv_id}", response_model=None)
def get_conversation(
    conv_id: str,
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    conv = db.query(ChatbotConversation).filter(ChatbotConversation.id == conv_id).first()
    if not conv:
        return err_msg("Conversa não encontrada.", status_code=404)
    nome_cliente = None
    if conv.cliente_id:
        c = db.query(Customer).filter(Customer.id == conv.cliente_id).first()
        nome_cliente = c.name if c else None
    detail = ChatbotConversationDetailOut.model_validate(conv).model_dump()
    detail["nome_cliente"] = nome_cliente
    return ok(detail)


@router.post("/conversations/{conv_id}/takeover", response_model=None)
def takeover(
    conv_id: str,
    body: TakeoverIn,
    db: Session = Depends(get_db),
    admin=Depends(get_current_admin),
):
    svc = ChatbotService(db)
    try:
        conv = svc.takeover(conv_id, admin.id, body.motivo)
    except ValueError as e:
        return err_msg(str(e), status_code=404)
    return ok(ChatbotConversationOut.model_validate(conv), "Conversa assumida.")


@router.post("/conversations/{conv_id}/reply", response_model=None)
def admin_reply(
    conv_id: str,
    body: AdminReplyIn,
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    svc = ChatbotService(db)
    try:
        msg = svc.admin_reply(conv_id, body.mensagem)
    except ValueError as e:
        return err_msg(str(e), status_code=404)
    return ok(ChatbotMessageOut.model_validate(msg))


@router.post("/conversations/{conv_id}/close", response_model=None)
def close_conversation(
    conv_id: str,
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    svc = ChatbotService(db)
    try:
        conv = svc.close_by_admin(conv_id)
    except ValueError as e:
        return err_msg(str(e), status_code=404)
    return ok(ChatbotConversationOut.model_validate(conv), "Conversa encerrada.")


@router.post("/conversations/{conv_id}/return-to-bot", response_model=None)
def return_to_bot(
    conv_id: str,
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    svc = ChatbotService(db)
    try:
        conv = svc.return_to_bot(conv_id)
    except ValueError as e:
        return err_msg(str(e), status_code=404)
    return ok(ChatbotConversationOut.model_validate(conv), "Conversa devolvida ao bot.")


@router.patch("/conversations/{conv_id}/tags", response_model=None)
def update_tags(
    conv_id: str,
    body: ConversationTagIn,
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    import json as _json
    conv = db.query(ChatbotConversation).filter(ChatbotConversation.id == conv_id).first()
    if not conv:
        return err_msg("Conversa não encontrada.", status_code=404)
    conv.tags = _json.dumps(body.tags, ensure_ascii=False)
    db.commit()
    return ok(None, "Tags atualizadas.")


# ── Analytics ─────────────────────────────────────────────────────────────────

@router.get("/analytics", response_model=None)
def get_analytics(
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    svc = ChatbotService(db)
    return ok(svc.get_analytics())


# ── Helpers internos ──────────────────────────────────────────────────────────

def _update_faq_vector(db: Session, faq: ChatbotFAQ) -> None:
    """Atualiza o tsvector do FAQ com pergunta + resposta."""
    try:
        from sqlalchemy import text
        db.execute(
            text(
                "UPDATE chatbot_faq SET busca_vetor = "
                "to_tsvector('portuguese', :text) WHERE id = :id"
            ),
            {"text": f"{faq.pergunta} {faq.resposta}", "id": faq.id},
        )
    except Exception:
        pass   # non-fatal — busca full-text degradada até próximo update


def _update_doc_vector(db: Session, doc: ChatbotKnowledgeDoc) -> None:
    """Atualiza o tsvector do documento de conhecimento."""
    try:
        from sqlalchemy import text
        db.execute(
            text(
                "UPDATE chatbot_knowledge_docs SET busca_vetor = "
                "to_tsvector('portuguese', :text) WHERE id = :id"
            ),
            {"text": f"{doc.titulo} {doc.conteudo}", "id": doc.id},
        )
    except Exception:
        pass
