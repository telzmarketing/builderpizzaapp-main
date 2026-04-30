"""
Serviço principal do chatbot.

Responsabilidades:
  - Gerenciar sessões (criar / recuperar ChatbotConversation)
  - Processar mensagens do visitante (IA ou humano)
  - Controlar handoff (takeover / reply / close)
  - Construir respostas com contexto de 3 camadas
  - Persistir todas as mensagens + snapshot de contexto
"""
from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, time, timezone
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.models.chatbot import (
    ChatbotConversation, ChatbotHandoff, ChatbotMessage,
    ChatbotSettings, ConversationStatus, MessageSender, MessageType,
)
from backend.schemas.chatbot import (
    ChatbotAnalyticsOut, SendMessageOut, StartSessionOut,
    ChatbotPublicConfigOut,
)
from backend.services.ai.factory import get_ai_provider
from backend.services.context_builder import ContextBuilder

log = logging.getLogger("chatbot.service")

_SUMMARY_THRESHOLD = 20   # mensagens antes de gerar resumo
_DAY_KEYS = ["seg", "ter", "qua", "qui", "sex", "sab", "dom"]


class ChatbotService:
    def __init__(self, db: Session):
        self._db = db

    # ── Settings (singleton) ─────────────────────────────────────────────────

    def get_settings(self) -> ChatbotSettings:
        s = self._db.query(ChatbotSettings).filter(ChatbotSettings.id == "default").first()
        if not s:
            s = ChatbotSettings(id="default")
            self._db.add(s)
            self._db.commit()
            self._db.refresh(s)
        return s

    def update_settings(self, data: dict) -> ChatbotSettings:
        s = self.get_settings()
        for k, v in data.items():
            if v is not None:
                setattr(s, k, v)
        self._db.commit()
        self._db.refresh(s)
        return s

    # ── Sessão / conversa ────────────────────────────────────────────────────

    def start_session(
        self,
        session_id: str,
        visitor_fingerprint: Optional[str],
        pagina_origem: Optional[str],
        user_agent: Optional[str],
        ip: Optional[str] = None,
    ) -> StartSessionOut:
        settings = self.get_settings()
        conv = self._db.query(ChatbotConversation).filter(
            ChatbotConversation.session_id == session_id,
        ).first()

        if not conv:
            conv = ChatbotConversation(
                session_id=session_id,
                visitor_fingerprint=visitor_fingerprint,
                pagina_origem=pagina_origem,
                user_agent=user_agent,
                ip_hash=_hash_ip(ip) if ip else None,
            )
            self._db.add(conv)
            self._db.commit()

        config = ChatbotPublicConfigOut.model_validate(settings)
        return StartSessionOut(session_id=session_id, config=config)

    def get_conversation(self, session_id: str) -> Optional[ChatbotConversation]:
        return self._db.query(ChatbotConversation).filter(
            ChatbotConversation.session_id == session_id,
        ).first()

    def close_conversation(self, session_id: str) -> None:
        conv = self.get_conversation(session_id)
        if conv and conv.status != ConversationStatus.encerrada:
            conv.status = ConversationStatus.encerrada
            conv.encerrada_em = datetime.now(timezone.utc)
            self._db.commit()

    # ── Processar mensagem do visitante ──────────────────────────────────────

    def process_message(
        self,
        session_id: str,
        user_message: str,
        page_url: Optional[str] = None,
        visitor_fingerprint: Optional[str] = None,
    ) -> SendMessageOut:
        settings = self.get_settings()
        conv = self.get_conversation(session_id)

        # Conversa não existe — cria on-the-fly
        if not conv:
            conv = ChatbotConversation(
                session_id=session_id,
                visitor_fingerprint=visitor_fingerprint,
                pagina_origem=page_url,
            )
            self._db.add(conv)
            self._db.commit()
            self._db.refresh(conv)

        # Salva mensagem do visitante
        self._save_message(conv.id, MessageSender.visitor, user_message)

        # Conversa assumida por humano → não chamar IA
        if conv.status == ConversationStatus.em_humano:
            self._db.commit()
            return SendMessageOut(
                session_id=session_id,
                resposta="",
                awaiting_human=True,
            )

        # Conversa encerrada → reabre
        if conv.status == ConversationStatus.encerrada:
            conv.status = ConversationStatus.aberta
            conv.encerrada_em = None
            self._db.commit()

        # Fora do horário de funcionamento
        if not _is_within_hours(settings.horario_funcionamento):
            bot_msg = settings.mensagem_fora_horario or "Estamos fora do horário de atendimento."
            self._save_message(conv.id, MessageSender.bot, bot_msg)
            self._db.commit()
            return SendMessageOut(
                session_id=session_id,
                resposta=bot_msg,
                fora_do_horario=True,
            )

        # Monta contexto e chama IA
        builder = ContextBuilder(self._db)
        system_prompt, messages = builder.build(settings, conv, user_message, page_url)
        context_snapshot = builder.build_snapshot(settings, conv, user_message, page_url)

        provider = get_ai_provider(settings)
        ai_resp = provider.generate(
            system_prompt=system_prompt,
            messages=messages,
            temperatura=settings.temperatura,
            max_tokens=settings.max_tokens,
        )
        context_snapshot = _with_ai_diagnostics(context_snapshot, ai_resp)

        # Persiste resposta do bot
        self._save_message(
            conv.id,
            MessageSender.bot,
            ai_resp.content,
            tokens=ai_resp.tokens_input + ai_resp.tokens_output,
            provedor=ai_resp.provider or settings.provedor_ia.value,
            latencia=ai_resp.latencia_ms,
            contexto=context_snapshot,
        )

        # Verifica se deve gerar resumo
        self._maybe_summarize(conv, settings)
        self._db.commit()

        return SendMessageOut(
            session_id=session_id,
            resposta=ai_resp.content,
        )

    # ── Admin: takeover / reply / close ──────────────────────────────────────

    def takeover(self, conversation_id: str, operador_id: str, motivo: Optional[str]) -> ChatbotConversation:
        conv = self._db.query(ChatbotConversation).filter(
            ChatbotConversation.id == conversation_id
        ).first()
        if not conv:
            raise ValueError("Conversa não encontrada.")

        conv.status = ConversationStatus.em_humano
        conv.assumida_por_user_id = operador_id

        handoff = ChatbotHandoff(
            conversation_id=conv.id,
            operador_id=operador_id,
            motivo=motivo,
        )
        self._db.add(handoff)
        self._save_message(
            conv.id, MessageSender.human,
            "Atendimento assumido por operador humano.",
            tipo=MessageType.system,
        )
        self._db.commit()
        self._db.refresh(conv)
        return conv

    def admin_reply(self, conversation_id: str, mensagem: str) -> ChatbotMessage:
        conv = self._db.query(ChatbotConversation).filter(
            ChatbotConversation.id == conversation_id
        ).first()
        if not conv:
            raise ValueError("Conversa não encontrada.")
        msg = self._save_message(conv.id, MessageSender.human, mensagem)
        self._db.commit()
        return msg

    def close_by_admin(self, conversation_id: str) -> ChatbotConversation:
        conv = self._db.query(ChatbotConversation).filter(
            ChatbotConversation.id == conversation_id
        ).first()
        if not conv:
            raise ValueError("Conversa não encontrada.")

        # Fecha handoff aberto se existir
        open_handoff = self._db.query(ChatbotHandoff).filter(
            ChatbotHandoff.conversation_id == conv.id,
            ChatbotHandoff.encerrado_em.is_(None),
        ).first()
        if open_handoff:
            open_handoff.encerrado_em = datetime.now(timezone.utc)

        conv.status = ConversationStatus.encerrada
        conv.encerrada_em = datetime.now(timezone.utc)
        self._save_message(conv.id, MessageSender.human, "Conversa encerrada.", tipo=MessageType.system)
        self._db.commit()
        self._db.refresh(conv)
        return conv

    def return_to_bot(self, conversation_id: str) -> ChatbotConversation:
        conv = self._db.query(ChatbotConversation).filter(
            ChatbotConversation.id == conversation_id
        ).first()
        if not conv:
            raise ValueError("Conversa não encontrada.")

        open_handoff = self._db.query(ChatbotHandoff).filter(
            ChatbotHandoff.conversation_id == conv.id,
            ChatbotHandoff.encerrado_em.is_(None),
        ).first()
        if open_handoff:
            open_handoff.encerrado_em = datetime.now(timezone.utc)

        conv.status = ConversationStatus.aberta
        conv.assumida_por_user_id = None
        self._save_message(
            conv.id, MessageSender.human,
            "Conversa devolvida ao bot.",
            tipo=MessageType.system,
        )
        self._db.commit()
        self._db.refresh(conv)
        return conv

    # ── Analytics ────────────────────────────────────────────────────────────

    def get_analytics(self) -> ChatbotAnalyticsOut:
        from datetime import timedelta

        now   = datetime.now(timezone.utc)
        hoje  = now.replace(hour=0, minute=0, second=0, microsecond=0)
        semana = hoje - timedelta(days=7)
        mes    = hoje - timedelta(days=30)

        q = self._db.query(ChatbotConversation)

        total_hoje   = q.filter(ChatbotConversation.iniciada_em >= hoje).count()
        total_semana = q.filter(ChatbotConversation.iniciada_em >= semana).count()
        total_mes    = q.filter(ChatbotConversation.iniciada_em >= mes).count()
        abertas      = q.filter(ChatbotConversation.status == ConversationStatus.aberta).count()
        em_humano    = q.filter(ChatbotConversation.status == ConversationStatus.em_humano).count()
        encerradas   = q.filter(ChatbotConversation.status == ConversationStatus.encerrada).count()

        # Tempo médio de primeira resposta (latência da 1ª msg bot no mês)
        avg_lat = self._db.query(func.avg(ChatbotMessage.latencia_ms)).filter(
            ChatbotMessage.sender == MessageSender.bot,
            ChatbotMessage.timestamp >= mes,
            ChatbotMessage.latencia_ms.isnot(None),
        ).scalar()

        # Tokens no mês
        tokens_mes = self._db.query(func.coalesce(func.sum(ChatbotMessage.tokens_consumidos), 0)).filter(
            ChatbotMessage.timestamp >= mes,
            ChatbotMessage.tokens_consumidos.isnot(None),
        ).scalar() or 0

        # Custo estimado (claude-sonnet ~$3/M input + $15/M output — estimativa conservadora $9/M)
        custo = (tokens_mes / 1_000_000) * 9.0

        return ChatbotAnalyticsOut(
            total_hoje=total_hoje,
            total_semana=total_semana,
            total_mes=total_mes,
            abertas=abertas,
            em_humano=em_humano,
            encerradas=encerradas,
            tempo_medio_resposta_ms=round(avg_lat, 1) if avg_lat else None,
            tokens_total_mes=tokens_mes,
            custo_estimado_mes=round(custo, 4),
        )

    # ── Helpers privados ─────────────────────────────────────────────────────

    def _save_message(
        self,
        conversation_id: str,
        sender: MessageSender,
        mensagem: str,
        *,
        tokens: int = 0,
        provedor: str = "",
        latencia: int = 0,
        contexto: Optional[str] = None,
        tipo: MessageType = MessageType.text,
    ) -> ChatbotMessage:
        msg = ChatbotMessage(
            conversation_id=conversation_id,
            sender=sender,
            mensagem=mensagem,
            tipo=tipo,
            tokens_consumidos=tokens or None,
            provedor_usado=provedor or None,
            latencia_ms=latencia or None,
            contexto_usado=contexto,
        )
        self._db.add(msg)
        self._db.flush()
        return msg

    def _maybe_summarize(self, conv: ChatbotConversation, settings: ChatbotSettings) -> None:
        """Gera resumo quando o histórico excede o threshold."""
        count = self._db.query(ChatbotMessage).filter(
            ChatbotMessage.conversation_id == conv.id
        ).count()

        if count < _SUMMARY_THRESHOLD or conv.resumo_conversa:
            return

        msgs = (
            self._db.query(ChatbotMessage)
            .filter(ChatbotMessage.conversation_id == conv.id)
            .order_by(ChatbotMessage.timestamp)
            .limit(_SUMMARY_THRESHOLD)
            .all()
        )
        history_text = "\n".join(
            f"{m.sender.value}: {m.mensagem}" for m in msgs
        )
        from backend.services.ai.base import AIMessage as _AIMsg
        provider = get_ai_provider(settings)
        resp = provider.generate(
            system_prompt="Resuma a conversa abaixo em 3 a 5 linhas, destacando o problema do cliente e o que foi resolvido.",
            messages=[_AIMsg(role="user", content=history_text)],
            temperatura=0.3,
            max_tokens=300,
        )
        conv.resumo_conversa = resp.content
        self._db.commit()


# ── Utilitários ───────────────────────────────────────────────────────────────

def _hash_ip(ip: str) -> str:
    return hashlib.sha256(ip.encode()).hexdigest()


def _with_ai_diagnostics(context_snapshot: str, ai_resp) -> str:
    try:
        data = json.loads(context_snapshot) if context_snapshot else {}
        data["ai"] = {
            "provider": ai_resp.provider,
            "model": ai_resp.model,
            "fallback": bool(ai_resp.error_reason),
            "error_reason": ai_resp.error_reason or None,
        }
        return json.dumps(data, ensure_ascii=False)
    except Exception:
        return context_snapshot


def _is_within_hours(horario_json: Optional[str]) -> bool:
    """Retorna True se estiver dentro do horário configurado (None = sempre aberto)."""
    if not horario_json:
        return True
    try:
        horario = json.loads(horario_json)
        now = datetime.now()
        day_key = _DAY_KEYS[now.weekday()]
        hours = horario.get(day_key)
        if not hours or len(hours) < 2:
            return False
        start_h, start_m = map(int, hours[0].split(":"))
        end_h,   end_m   = map(int, hours[1].split(":"))
        current = time(now.hour, now.minute)
        return time(start_h, start_m) <= current <= time(end_h, end_m)
    except Exception:
        return True   # em caso de erro de parse, considera aberto
