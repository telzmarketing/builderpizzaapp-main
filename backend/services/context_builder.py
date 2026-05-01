"""
Montagem do prompt em 3 camadas para cada chamada à IA.

Camada 1 — Prompt base (chatbot_settings): fixo por conversa.
Camada 2 — Contexto dinâmico: loja, promoções, produtos, FAQ relevante, página atual.
Camada 3 — Estado da conversa: intenção detectada, dados coletados, histórico recente.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.models.chatbot import (
    ChatbotConversation, ChatbotFAQ, ChatbotKnowledgeDoc,
    ChatbotMessage, ChatbotSettings, MessageSender,
)
from backend.models.customer import Customer
from backend.models.order import Order, OrderStatus
from backend.models.product import Product
from backend.models.promotion import Promotion
from backend.services.ai.base import AIMessage

_MAX_HISTORY_MSGS   = 20   # após esse limite usa o resumo
_MAX_FAQ_RESULTS    = 5
_MAX_PRODUCTS_CONTEXT = 8

_ACTIVE_ORDER_STATUSES = {
    OrderStatus.pending, OrderStatus.waiting_payment, OrderStatus.paid,
    OrderStatus.aguardando_pagamento, OrderStatus.pago,
    OrderStatus.preparing, OrderStatus.ready_for_pickup, OrderStatus.on_the_way,
}

_STATUS_LABEL = {
    "pending": "aguardando confirmação",
    "waiting_payment": "aguardando pagamento",
    "paid": "pago",
    "aguardando_pagamento": "aguardando pagamento",
    "pago": "pago",
    "preparing": "em preparação",
    "ready_for_pickup": "pronto para retirada",
    "on_the_way": "saiu para entrega",
}


class ContextBuilder:
    def __init__(self, db: Session):
        self._db = db

    # ── Ponto de entrada ─────────────────────────────────────────────────────

    def build(
        self,
        settings: ChatbotSettings,
        conversation: ChatbotConversation,
        user_message: str,
        page_url: Optional[str] = None,
        customer_id: Optional[str] = None,
    ) -> tuple[str, list[AIMessage]]:
        """
        Retorna (system_prompt, messages[]).
        O system_prompt inclui as 3 camadas.
        messages[] contém o histórico formatado para a API.
        """
        layer1 = self._layer1(settings)
        layer2 = self._layer2(user_message, page_url, customer_id)
        layer3 = self._layer3(conversation)

        system_prompt = "\n\n---\n\n".join(filter(None, [layer1, layer2, layer3]))
        messages      = self._build_history(conversation, user_message)

        return system_prompt, messages

    def build_snapshot(
        self,
        settings: ChatbotSettings,
        conversation: ChatbotConversation,
        user_message: str,
        page_url: Optional[str] = None,
        customer_id: Optional[str] = None,
    ) -> str:
        """Retorna JSON string do contexto completo — salvo em chatbot_messages.contexto_usado."""
        layer1 = self._layer1(settings)
        layer2 = self._layer2(user_message, page_url, customer_id)
        layer3 = self._layer3(conversation)
        return json.dumps(
            {"layer1": layer1, "layer2": layer2, "layer3": layer3},
            ensure_ascii=False,
        )

    # ── Camada 1 — Prompt base ───────────────────────────────────────────────

    def _layer1(self, s: ChatbotSettings) -> str:
        parts = []
        if s.prompt_base:
            parts.append(s.prompt_base.strip())
        if s.tom_de_voz:
            parts.append(f"Tom de voz: {s.tom_de_voz.strip()}")
        if s.objetivo:
            parts.append(f"Objetivo: {s.objetivo.strip()}")
        if s.regras_fixas:
            parts.append(f"Regras obrigatórias:\n{s.regras_fixas.strip()}")
        if s.limitacoes_proibicoes:
            parts.append(f"Proibições / limitações:\n{s.limitacoes_proibicoes.strip()}")
        if s.instrucoes_transferencia:
            parts.append(f"Instruções para transferência ao humano:\n{s.instrucoes_transferencia.strip()}")
        return "\n\n".join(parts)

    # ── Camada 2 — Contexto dinâmico ─────────────────────────────────────────

    def _layer2(self, user_message: str, page_url: Optional[str], customer_id: Optional[str] = None) -> str:
        parts: list[str] = ["## Contexto da loja (atualizado em tempo real)"]

        # Dados do cliente logado + pedidos em andamento
        if customer_id:
            customer_ctx = self._customer_context(customer_id)
            if customer_ctx:
                parts.append(customer_ctx)
            orders_ctx = self._orders_context(customer_id)
            if orders_ctx:
                parts.append(orders_ctx)

        # Produtos em destaque / produto da página atual
        product_ctx = self._product_context(page_url)
        if product_ctx:
            parts.append(product_ctx)

        # Promoções ativas
        promo_ctx = self._promotions_context()
        if promo_ctx:
            parts.append(promo_ctx)

        # FAQ relevante (full-text search)
        faq_ctx = self._faq_context(user_message)
        if faq_ctx:
            parts.append(faq_ctx)

        # Documentos de conhecimento relevantes
        doc_ctx = self._docs_context(user_message)
        if doc_ctx:
            parts.append(doc_ctx)

        # Página atual
        if page_url:
            parts.append(f"Página atual do visitante: {page_url}")

        return "\n\n".join(parts)

    def _customer_context(self, customer_id: str) -> str:
        try:
            customer = self._db.query(Customer).filter(Customer.id == customer_id).first()
            if not customer:
                return ""
            parts = [f"Cliente logado: {customer.name}"]
            if customer.phone:
                parts.append(f"Telefone: {customer.phone}")
            return "\n".join(parts)
        except Exception:
            return ""

    def _orders_context(self, customer_id: str) -> str:
        try:
            orders = (
                self._db.query(Order)
                .filter(
                    Order.customer_id == customer_id,
                    Order.status.in_(_ACTIVE_ORDER_STATUSES),
                )
                .order_by(Order.created_at.desc())
                .limit(3)
                .all()
            )
            if not orders:
                return ""
            lines = []
            for o in orders:
                status_label = _STATUS_LABEL.get(o.status.value if hasattr(o.status, "value") else o.status, o.status)
                created = o.created_at.strftime("%d/%m %H:%M") if o.created_at else "?"
                lines.append(f"- Pedido #{o.id[-6:]}: {status_label} — R$ {o.total:.2f} (criado em {created})")
            return "Pedidos em andamento do cliente:\n" + "\n".join(lines)
        except Exception:
            return ""

    def _product_context(self, page_url: Optional[str]) -> str:
        # Se o visitante está em /product/:id, prioriza esse produto
        if page_url:
            match = re.search(r"/product/([^/?#]+)", page_url)
            if match:
                prod = self._db.query(Product).filter(
                    Product.id == match.group(1), Product.active == True  # noqa: E712
                ).first()
                if prod:
                    return (
                        f"Produto visualizado pelo visitante:\n"
                        f"- {prod.name}: R$ {prod.price:.2f} — {prod.description}"
                    )

        products = (
            self._db.query(Product)
            .filter(Product.active == True)  # noqa: E712
            .order_by(Product.rating.desc())
            .limit(_MAX_PRODUCTS_CONTEXT)
            .all()
        )
        if not products:
            return ""
        lines = [f"- {p.name}: R$ {p.price:.2f} — {p.description}" for p in products]
        return "Produtos em destaque:\n" + "\n".join(lines)

    def _promotions_context(self) -> str:
        now = datetime.now(timezone.utc)
        promos = (
            self._db.query(Promotion)
            .filter(Promotion.active == True)  # noqa: E712
            .limit(5)
            .all()
        )
        if not promos:
            return ""
        lines = [f"- {p.title}: {p.subtitle or ''}" for p in promos]
        return "Promoções ativas:\n" + "\n".join(lines)

    def _faq_context(self, user_message: str) -> str:
        try:
            # Limpa a query: remove pontuação, une palavras com ' & '
            words = re.sub(r"[^\w\s]", " ", user_message).split()
            if not words:
                return ""
            tsquery = " & ".join(words[:6])  # max 6 termos

            results = (
                self._db.query(ChatbotFAQ)
                .filter(
                    ChatbotFAQ.ativo == True,  # noqa: E712
                    ChatbotFAQ.busca_vetor.op("@@")(
                        func.to_tsquery("portuguese", tsquery)
                    ),
                )
                .order_by(ChatbotFAQ.prioridade.desc())
                .limit(_MAX_FAQ_RESULTS)
                .all()
            )
        except Exception:
            # Fallback sem full-text (tabela sem vetor ainda populado)
            results = (
                self._db.query(ChatbotFAQ)
                .filter(ChatbotFAQ.ativo == True)  # noqa: E712
                .order_by(ChatbotFAQ.prioridade.desc())
                .limit(3)
                .all()
            )

        if not results:
            return ""
        parts = [f"P: {f.pergunta}\nR: {f.resposta}" for f in results]
        return "Perguntas frequentes relevantes:\n\n" + "\n\n".join(parts)

    def _docs_context(self, user_message: str) -> str:
        try:
            words = re.sub(r"[^\w\s]", " ", user_message).split()
            if not words:
                return ""
            tsquery = " & ".join(words[:6])
            docs = (
                self._db.query(ChatbotKnowledgeDoc)
                .filter(
                    ChatbotKnowledgeDoc.ativo == True,  # noqa: E712
                    ChatbotKnowledgeDoc.busca_vetor.op("@@")(
                        func.to_tsquery("portuguese", tsquery)
                    ),
                )
                .limit(2)
                .all()
            )
        except Exception:
            return ""

        if not docs:
            return ""
        parts = [f"### {d.titulo}\n{d.conteudo[:800]}" for d in docs]
        return "Documentos de conhecimento relevantes:\n\n" + "\n\n".join(parts)

    # ── Camada 3 — Estado da conversa ────────────────────────────────────────

    def _layer3(self, conv: ChatbotConversation) -> str:
        parts: list[str] = ["## Estado da conversa"]

        if conv.intencao_detectada:
            parts.append(f"Intenção detectada: {conv.intencao_detectada}")

        if conv.resumo_conversa:
            parts.append(f"Resumo das mensagens anteriores:\n{conv.resumo_conversa}")

        return "\n\n".join(parts) if len(parts) > 1 else ""

    # ── Histórico de mensagens ────────────────────────────────────────────────

    def _build_history(
        self, conv: ChatbotConversation, current_user_message: str
    ) -> list[AIMessage]:
        msgs = (
            self._db.query(ChatbotMessage)
            .filter(ChatbotMessage.conversation_id == conv.id)
            .order_by(ChatbotMessage.timestamp.desc())
            .limit(_MAX_HISTORY_MSGS)
            .all()
        )
        msgs = list(reversed(msgs))

        history: list[AIMessage] = []
        for m in msgs:
            if m.sender == MessageSender.visitor:
                history.append(AIMessage(role="user", content=m.mensagem))
            elif m.sender in (MessageSender.bot, MessageSender.human):
                history.append(AIMessage(role="assistant", content=m.mensagem))

        history.append(AIMessage(role="user", content=current_user_message))
        return history
