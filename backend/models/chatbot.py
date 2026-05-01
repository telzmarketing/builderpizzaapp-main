from __future__ import annotations

import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean, Column, DateTime, Enum as SAEnum,
    Float, ForeignKey, Index, Integer, String, Text,
)
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlalchemy.orm import relationship

from backend.database import Base


def _uid(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


# ── Enums ─────────────────────────────────────────────────────────────────────

class WidgetPosition(str, enum.Enum):
    bottom_right = "bottom-right"
    bottom_left  = "bottom-left"


class AIProviderEnum(str, enum.Enum):
    claude = "claude"
    openai = "openai"


class ConversationStatus(str, enum.Enum):
    aberta    = "aberta"
    em_humano = "em_humano"
    encerrada = "encerrada"


class MessageSender(str, enum.Enum):
    visitor = "visitor"
    bot     = "bot"
    human   = "human"


class MessageType(str, enum.Enum):
    text   = "text"
    action = "action"
    system = "system"


class AutomationTrigger(str, enum.Enum):
    tempo_na_pagina    = "tempo_na_pagina"
    pagina_especifica  = "pagina_especifica"
    carrinho_abandonado = "carrinho_abandonado"
    produto_visualizado = "produto_visualizado"


# ── Models ────────────────────────────────────────────────────────────────────

class ChatbotSettings(Base):
    """Singleton — apenas uma linha com id='default'."""
    __tablename__ = "chatbot_settings"

    id                      = Column(String, primary_key=True, default="default")
    ativo                   = Column(Boolean, default=True)
    ia_ativo                = Column(Boolean, default=True)
    nome_bot                = Column(String(100), default="Assistente")
    mensagem_inicial        = Column(Text, default="Olá! Como posso ajudar?")
    cor_primaria            = Column(String(20), default="#f97316")
    posicao_widget          = Column(SAEnum(WidgetPosition), default=WidgetPosition.bottom_right)
    horario_funcionamento   = Column(Text, nullable=True)           # JSON string
    mensagem_fora_horario   = Column(Text, default="Estamos fora do horário de atendimento.")
    tempo_disparo_auto      = Column(Integer, default=0)            # 0 = desativado
    fallback_humano_ativo   = Column(Boolean, default=True)
    provedor_ia             = Column(SAEnum(AIProviderEnum), default=AIProviderEnum.claude)
    modelo_ia               = Column(String(100), default="claude-sonnet-4-20250514")
    temperatura             = Column(Float, default=0.7)
    max_tokens              = Column(Integer, default=1024)
    prompt_base             = Column(Text, default="")
    regras_fixas            = Column(Text, default="")
    tom_de_voz              = Column(Text, default="")
    objetivo                = Column(Text, default="")
    instrucoes_transferencia = Column(Text, default="")
    limitacoes_proibicoes   = Column(Text, default="")
    anthropic_api_key       = Column(Text, nullable=True)   # stored in DB, never exposed to frontend
    openai_api_key          = Column(Text, nullable=True)   # stored in DB, never exposed to frontend
    updated_at              = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class ChatbotFAQ(Base):
    __tablename__ = "chatbot_faq"

    id                 = Column(String, primary_key=True, default=lambda: _uid("faq"))
    pergunta           = Column(Text, nullable=False)
    resposta           = Column(Text, nullable=False)
    categoria          = Column(String(100), default="geral")
    prioridade         = Column(Integer, default=0)
    ativo              = Column(Boolean, default=True)
    vinculo_produto_id = Column(
        String, ForeignKey("products.id", ondelete="SET NULL"), nullable=True
    )
    busca_vetor        = Column(TSVECTOR, nullable=True)
    created_at         = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at         = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        Index("ix_chatbot_faq_busca_vetor", "busca_vetor", postgresql_using="gin"),
    )


class ChatbotConversation(Base):
    __tablename__ = "chatbot_conversations"

    id                   = Column(String, primary_key=True, default=lambda: _uid("conv"))
    session_id           = Column(String, unique=True, nullable=False, index=True)
    cliente_id           = Column(
        String, ForeignKey("customers.id", ondelete="SET NULL"), nullable=True
    )
    visitor_fingerprint  = Column(String(100), nullable=True)
    pagina_origem        = Column(String(500), nullable=True)
    user_agent           = Column(Text, nullable=True)
    ip_hash              = Column(String(64), nullable=True)         # SHA-256 — LGPD
    status               = Column(
        SAEnum(ConversationStatus),
        default=ConversationStatus.aberta,
        index=True,
    )
    tags                 = Column(Text, nullable=True)               # JSON string
    iniciada_em          = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    encerrada_em         = Column(DateTime(timezone=True), nullable=True)
    assumida_por_user_id = Column(
        String, ForeignKey("admin_users.id", ondelete="SET NULL"), nullable=True
    )
    intencao_detectada   = Column(String(200), nullable=True)
    resumo_conversa      = Column(Text, nullable=True)

    messages  = relationship(
        "ChatbotMessage", back_populates="conversation",
        order_by="ChatbotMessage.timestamp",
    )
    handoffs  = relationship("ChatbotHandoff", back_populates="conversation")

    __table_args__ = (
        Index("ix_chatbot_conv_status_iniciada", "status", "iniciada_em"),
    )


class ChatbotMessage(Base):
    __tablename__ = "chatbot_messages"

    id                = Column(String, primary_key=True, default=lambda: _uid("msg"))
    conversation_id   = Column(
        String,
        ForeignKey("chatbot_conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sender            = Column(SAEnum(MessageSender), nullable=False)
    mensagem          = Column(Text, nullable=False)
    tipo              = Column(SAEnum(MessageType), default=MessageType.text)
    tokens_consumidos = Column(Integer, nullable=True)
    provedor_usado    = Column(String(50), nullable=True)
    latencia_ms       = Column(Integer, nullable=True)
    contexto_usado    = Column(Text, nullable=True)                  # JSON snapshot para debug
    timestamp         = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )

    conversation = relationship("ChatbotConversation", back_populates="messages")


class ChatbotAutomation(Base):
    __tablename__ = "chatbot_automations"

    id         = Column(String, primary_key=True, default=lambda: _uid("auto"))
    nome       = Column(String(200), nullable=False)
    gatilho    = Column(SAEnum(AutomationTrigger), nullable=False)
    condicao   = Column(Text, default="{}")                          # JSON string
    mensagem   = Column(Text, nullable=False)
    ativo      = Column(Boolean, default=True)
    prioridade = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class ChatbotHandoff(Base):
    __tablename__ = "chatbot_handoffs"

    id              = Column(String, primary_key=True, default=lambda: _uid("hdff"))
    conversation_id = Column(
        String,
        ForeignKey("chatbot_conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    operador_id     = Column(
        String, ForeignKey("admin_users.id", ondelete="SET NULL"), nullable=True
    )
    assumido_em     = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    encerrado_em    = Column(DateTime(timezone=True), nullable=True)
    motivo          = Column(String(500), nullable=True)

    conversation = relationship("ChatbotConversation", back_populates="handoffs")


class ChatbotKnowledgeDoc(Base):
    __tablename__ = "chatbot_knowledge_docs"

    id          = Column(String, primary_key=True, default=lambda: _uid("kdoc"))
    titulo      = Column(String(300), nullable=False)
    conteudo    = Column(Text, nullable=False)
    tipo        = Column(String(50), default="geral")               # politica|menu|geral|faq
    ativo       = Column(Boolean, default=True)
    busca_vetor = Column(TSVECTOR, nullable=True)
    created_at  = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at  = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        Index("ix_chatbot_kdoc_busca_vetor", "busca_vetor", postgresql_using="gin"),
    )
