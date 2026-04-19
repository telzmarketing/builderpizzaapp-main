"""
Endpoints públicos do chatbot — consumidos pelo widget no site.

Prefixo: /chatbot
"""
from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Header, Request
from sqlalchemy.orm import Session

from backend.core.response import ok, err_msg
from backend.database import get_db
from backend.models.chatbot import ChatbotMessage, MessageSender
from backend.schemas.chatbot import (
    SendMessageIn, SendMessageOut, StartSessionIn, StartSessionOut,
    ChatbotMessageOut, ChatbotPublicConfigOut,
)
from backend.services.chatbot_service import ChatbotService

router = APIRouter(prefix="/chatbot", tags=["chatbot"])


# ── Config pública do widget ──────────────────────────────────────────────────

@router.get("/config", response_model=None)
def get_widget_config(db: Session = Depends(get_db)):
    """Retorna configurações públicas do widget (cor, posição, mensagem inicial, status)."""
    svc = ChatbotService(db)
    settings = svc.get_settings()
    config = ChatbotPublicConfigOut.model_validate(settings)
    return ok(config)


# ── Iniciar sessão ────────────────────────────────────────────────────────────

@router.post("/session", response_model=None)
def start_session(
    body: StartSessionIn,
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Inicia ou recupera uma sessão de chat.
    Se session_id não vier no body, gera um novo UUID.
    """
    session_id = getattr(body, "session_id", None) or str(uuid.uuid4())
    ip = request.client.host if request.client else None

    svc = ChatbotService(db)
    result = svc.start_session(
        session_id=session_id,
        visitor_fingerprint=body.visitor_fingerprint,
        pagina_origem=body.pagina_origem,
        user_agent=body.user_agent,
        ip=ip,
    )
    return ok(result)


# ── Enviar mensagem ───────────────────────────────────────────────────────────

@router.post("/message", response_model=None)
def send_message(body: SendMessageIn, db: Session = Depends(get_db)):
    """Processa mensagem do visitante e retorna resposta do bot (ou flag awaiting_human)."""
    svc = ChatbotService(db)
    result = svc.process_message(
        session_id=body.session_id,
        user_message=body.mensagem,
        page_url=body.page_url,
        visitor_fingerprint=body.visitor_fingerprint,
    )
    return ok(result)


# ── Histórico da sessão ───────────────────────────────────────────────────────

@router.get("/history/{session_id}", response_model=None)
def get_history(session_id: str, db: Session = Depends(get_db)):
    """Retorna todas as mensagens da sessão (visitante faz polling a cada 3s quando em_humano)."""
    svc = ChatbotService(db)
    conv = svc.get_conversation(session_id)
    if not conv:
        return err_msg("Sessão não encontrada.", code="SessionNotFound", status_code=404)

    msgs = (
        db.query(ChatbotMessage)
        .filter(ChatbotMessage.conversation_id == conv.id)
        .order_by(ChatbotMessage.timestamp)
        .all()
    )
    out = [ChatbotMessageOut.model_validate(m) for m in msgs]
    return ok({
        "session_id": session_id,
        "status": conv.status.value,
        "messages": [m.model_dump() for m in out],
    })


# ── Encerrar conversa ─────────────────────────────────────────────────────────

@router.post("/close", response_model=None)
def close_conversation(
    body: dict,
    db: Session = Depends(get_db),
):
    """Visitante encerra a conversa."""
    session_id = body.get("session_id", "")
    if not session_id:
        return err_msg("session_id obrigatório.", status_code=400)
    ChatbotService(db).close_conversation(session_id)
    return ok(None, "Conversa encerrada.")
