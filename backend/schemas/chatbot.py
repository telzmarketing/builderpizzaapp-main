from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

from backend.models.chatbot import (
    AIProviderEnum, AutomationTrigger, ConversationStatus,
    MessageSender, MessageType, WidgetPosition,
)


# ── Settings ──────────────────────────────────────────────────────────────────

class ChatbotSettingsUpdate(BaseModel):
    ativo:                   Optional[bool]             = None
    nome_bot:                Optional[str]              = None
    mensagem_inicial:        Optional[str]              = None
    cor_primaria:            Optional[str]              = None
    posicao_widget:          Optional[WidgetPosition]   = None
    horario_funcionamento:   Optional[str]              = None   # JSON string
    mensagem_fora_horario:   Optional[str]              = None
    tempo_disparo_auto:      Optional[int]              = None
    fallback_humano_ativo:   Optional[bool]             = None
    provedor_ia:             Optional[AIProviderEnum]   = None
    modelo_ia:               Optional[str]              = None
    temperatura:             Optional[float]            = Field(default=None, ge=0.0, le=2.0)
    max_tokens:              Optional[int]              = Field(default=None, ge=1, le=8192)
    prompt_base:             Optional[str]              = None
    regras_fixas:            Optional[str]              = None
    tom_de_voz:              Optional[str]              = None
    objetivo:                Optional[str]              = None
    instrucoes_transferencia: Optional[str]             = None
    limitacoes_proibicoes:   Optional[str]              = None


class ChatbotSettingsOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id:                      str
    ativo:                   bool
    nome_bot:                str
    mensagem_inicial:        str
    cor_primaria:            str
    posicao_widget:          WidgetPosition
    horario_funcionamento:   Optional[str]
    mensagem_fora_horario:   str
    tempo_disparo_auto:      int
    fallback_humano_ativo:   bool
    provedor_ia:             AIProviderEnum
    modelo_ia:               str
    temperatura:             float
    max_tokens:              int
    prompt_base:             str
    regras_fixas:            str
    tom_de_voz:              str
    objetivo:                str
    instrucoes_transferencia: str
    limitacoes_proibicoes:   str
    updated_at:              Optional[datetime]


class ChatbotPublicConfigOut(BaseModel):
    """Config exposta ao widget — sem dados sensíveis de IA."""
    model_config = ConfigDict(from_attributes=True)

    ativo:                 bool
    nome_bot:              str
    mensagem_inicial:      str
    cor_primaria:          str
    posicao_widget:        WidgetPosition
    horario_funcionamento: Optional[str]
    mensagem_fora_horario: str
    tempo_disparo_auto:    int
    fallback_humano_ativo: bool


# ── FAQ ───────────────────────────────────────────────────────────────────────

class ChatbotFAQCreate(BaseModel):
    pergunta:           str
    resposta:           str
    categoria:          str   = "geral"
    prioridade:         int   = 0
    ativo:              bool  = True
    vinculo_produto_id: Optional[str] = None


class ChatbotFAQUpdate(BaseModel):
    pergunta:           Optional[str]  = None
    resposta:           Optional[str]  = None
    categoria:          Optional[str]  = None
    prioridade:         Optional[int]  = None
    ativo:              Optional[bool] = None
    vinculo_produto_id: Optional[str]  = None


class ChatbotFAQOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id:                 str
    pergunta:           str
    resposta:           str
    categoria:          str
    prioridade:         int
    ativo:              bool
    vinculo_produto_id: Optional[str]
    created_at:         datetime
    updated_at:         datetime


# ── Automation ────────────────────────────────────────────────────────────────

class ChatbotAutomationCreate(BaseModel):
    nome:      str
    gatilho:   AutomationTrigger
    condicao:  str  = "{}"   # JSON string
    mensagem:  str
    ativo:     bool = True
    prioridade: int = 0


class ChatbotAutomationUpdate(BaseModel):
    nome:      Optional[str]               = None
    gatilho:   Optional[AutomationTrigger] = None
    condicao:  Optional[str]               = None
    mensagem:  Optional[str]               = None
    ativo:     Optional[bool]              = None
    prioridade: Optional[int]              = None


class ChatbotAutomationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id:         str
    nome:       str
    gatilho:    AutomationTrigger
    condicao:   str
    mensagem:   str
    ativo:      bool
    prioridade: int
    created_at: datetime
    updated_at: datetime


# ── Knowledge Docs ────────────────────────────────────────────────────────────

class ChatbotKnowledgeDocCreate(BaseModel):
    titulo:   str
    conteudo: str
    tipo:     str  = "geral"
    ativo:    bool = True


class ChatbotKnowledgeDocUpdate(BaseModel):
    titulo:   Optional[str]  = None
    conteudo: Optional[str]  = None
    tipo:     Optional[str]  = None
    ativo:    Optional[bool] = None


class ChatbotKnowledgeDocOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id:         str
    titulo:     str
    conteudo:   str
    tipo:       str
    ativo:      bool
    created_at: datetime
    updated_at: datetime


# ── Conversation & Messages ───────────────────────────────────────────────────

class ChatbotMessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id:                str
    conversation_id:   str
    sender:            MessageSender
    mensagem:          str
    tipo:              MessageType
    tokens_consumidos: Optional[int]
    provedor_usado:    Optional[str]
    latencia_ms:       Optional[int]
    contexto_usado:    Optional[str]
    timestamp:         datetime


class ChatbotConversationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id:                   str
    session_id:           str
    cliente_id:           Optional[str]
    pagina_origem:        Optional[str]
    status:               ConversationStatus
    tags:                 Optional[str]
    iniciada_em:          datetime
    encerrada_em:         Optional[datetime]
    assumida_por_user_id: Optional[str]
    intencao_detectada:   Optional[str]
    resumo_conversa:      Optional[str]


class ChatbotConversationDetailOut(ChatbotConversationOut):
    messages: list[ChatbotMessageOut] = []


# ── Widget public API ─────────────────────────────────────────────────────────

class StartSessionIn(BaseModel):
    session_id:          Optional[str] = None   # se None, backend gera novo UUID
    visitor_fingerprint: Optional[str] = None
    pagina_origem:       Optional[str] = None
    user_agent:          Optional[str] = None


class StartSessionOut(BaseModel):
    session_id: str
    config:     ChatbotPublicConfigOut


class SendMessageIn(BaseModel):
    session_id:          str
    mensagem:            str = Field(..., min_length=1, max_length=2000)
    page_url:            Optional[str] = None
    visitor_fingerprint: Optional[str] = None


class SendMessageOut(BaseModel):
    session_id:        str
    resposta:          str
    sender:            str  = "bot"
    awaiting_human:    bool = False
    fora_do_horario:   bool = False


# ── Admin: takeover / reply / close ──────────────────────────────────────────

class TakeoverIn(BaseModel):
    motivo: Optional[str] = None


class AdminReplyIn(BaseModel):
    mensagem: str = Field(..., min_length=1, max_length=2000)


class ConversationTagIn(BaseModel):
    tags: list[str]


# ── Analytics ─────────────────────────────────────────────────────────────────

class ChatbotAnalyticsOut(BaseModel):
    total_hoje:              int
    total_semana:            int
    total_mes:               int
    abertas:                 int
    em_humano:               int
    encerradas:              int
    tempo_medio_resposta_ms: Optional[float]
    tokens_total_mes:        int
    custo_estimado_mes:      float   # USD estimado
