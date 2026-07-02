from __future__ import annotations

import re
import unicodedata
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy.orm import Session

from backend.config import get_ai_api_key
from backend.models.agente_whatsapp import (
    AgenteWhatsAppAISettings,
    AgenteWhatsAppContext,
    AgenteWhatsAppMessage,
    AgenteWhatsAppSession,
)
from backend.services.ai.base import AIMessage
from backend.services.ai.claude_provider import ClaudeProvider
from backend.services.ai.openai_provider import OpenAIProvider
from backend.services.agente_whatsapp_campaign_context_service import AgenteWhatsAppCampaignContextService
from backend.services.agente_whatsapp_outbox_service import AgenteWhatsAppOutboxService
from backend.services.agente_whatsapp_service import AgenteWhatsAppService
from backend.services.agente_whatsapp_tools import AgenteWhatsAppToolService


def _normalize_text(value: str | None) -> str:
    raw = value or ""
    normalized = unicodedata.normalize("NFKD", raw)
    ascii_text = "".join(char for char in normalized if not unicodedata.combining(char))
    return ascii_text.lower().strip()


def _money(value: Any) -> str:
    try:
        amount = float(value or 0)
    except (TypeError, ValueError):
        amount = 0.0
    return f"R$ {amount:.2f}".replace(".", ",")


def _first_name(value: str | None) -> str:
    name = (value or "").strip()
    return name.split()[0] if name else ""


def _json_load(value: str | None) -> dict[str, Any]:
    if not value:
        return {}
    try:
        import json

        data = json.loads(value)
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _json_dump(value: dict[str, Any] | None) -> str:
    import json

    return json.dumps(value or {}, ensure_ascii=False)


def _mask_key(value: str | None) -> str | None:
    key = (value or "").strip()
    if not key:
        return None
    if len(key) <= 10:
        return f"{key[:2]}***"
    return f"{key[:6]}...{key[-4:]}"


class AgenteWhatsAppAIService:
    """Deterministic sales runtime for AGENTE WHATSAPP.

    This layer does not invent commercial data. It plans and executes only
    registered tools, then composes short replies from tool outputs.
    """

    def __init__(self, db: Session):
        self._db = db
        self._service = AgenteWhatsAppService(db)
        self._tools = AgenteWhatsAppToolService(db)

    def get_settings(self) -> AgenteWhatsAppAISettings:
        settings = self._db.query(AgenteWhatsAppAISettings).filter(AgenteWhatsAppAISettings.id == "default").first()
        if not settings:
            settings = AgenteWhatsAppAISettings(
                id="default",
                prompt_base=(
                    "Voce e o AGENTE WHATSAPP oficial da loja. Atenda com objetividade, "
                    "venda com naturalidade e use somente dados vindos das ferramentas reais."
                ),
                business_rules=(
                    "Nunca invente preco, promocao, status de pedido, frete, cupom ou forma de pagamento. "
                    "Para criar pedido ou pagamento real, exija confirmacao explicita do cliente."
                ),
                tone_of_voice="Humano, cordial, direto e comercial, sem textos longos.",
                objective="Vender, atender, recuperar vendas e acompanhar pedidos pelo WhatsApp.",
                transfer_instructions="Transferir para humano quando houver reclamacao grave, pagamento divergente ou pedido fora das regras.",
                forbidden_topics="Nao prometer prazo, desconto, brinde ou disponibilidade sem ferramenta real.",
                allowed_tools_json=_json_dump({"mode": "all_registered_tools"}),
            )
            self._db.add(settings)
            self._db.flush()
        return settings

    def serialize_settings(self, settings: AgenteWhatsAppAISettings | None = None) -> dict[str, Any]:
        row = settings or self.get_settings()
        return {
            "id": row.id,
            "enabled": bool(row.enabled),
            "provider": row.provider,
            "model": row.model,
            "temperature": row.temperature,
            "max_tokens": row.max_tokens,
            "prompt_base": row.prompt_base or "",
            "business_rules": row.business_rules or "",
            "tone_of_voice": row.tone_of_voice or "",
            "objective": row.objective or "",
            "transfer_instructions": row.transfer_instructions or "",
            "forbidden_topics": row.forbidden_topics or "",
            "allowed_tools": _json_load(row.allowed_tools_json),
            "openai_key_preview": _mask_key(row.openai_api_key) or _mask_key(get_ai_api_key("OPENAI_API_KEY")),
            "anthropic_key_preview": _mask_key(row.anthropic_api_key) or _mask_key(get_ai_api_key("ANTHROPIC_API_KEY")),
            "updated_at": row.updated_at,
        }

    def update_settings(self, data: dict[str, Any]) -> dict[str, Any]:
        settings = self.get_settings()
        allowed_tools = data.pop("allowed_tools", None)
        for key, value in data.items():
            if value is not None and hasattr(settings, key):
                setattr(settings, key, value)
        if allowed_tools is not None:
            settings.allowed_tools_json = _json_dump(allowed_tools if isinstance(allowed_tools, dict) else {})
        settings.updated_at = datetime.now(timezone.utc)
        self._db.flush()
        return self.serialize_settings(settings)

    def update_ai_keys(self, *, openai_api_key: str | None = None, anthropic_api_key: str | None = None) -> dict[str, Any]:
        if not openai_api_key and not anthropic_api_key:
            raise ValueError("Informe pelo menos uma chave de API.")
        settings = self.get_settings()
        if openai_api_key:
            settings.openai_api_key = openai_api_key.strip()
        if anthropic_api_key:
            settings.anthropic_api_key = anthropic_api_key.strip()
        settings.updated_at = datetime.now(timezone.utc)
        self._db.flush()
        return self.provider_status(settings)

    def provider_status(self, settings: AgenteWhatsAppAISettings | None = None) -> dict[str, Any]:
        row = settings or self.get_settings()
        openai_key = (row.openai_api_key or "").strip() or get_ai_api_key("OPENAI_API_KEY")
        anthropic_key = (row.anthropic_api_key or "").strip() or get_ai_api_key("ANTHROPIC_API_KEY")
        selected_key = anthropic_key if row.provider == "claude" else openai_key if row.provider == "openai" else "internal"
        return {
            "provider": row.provider,
            "model": row.model,
            "internal": True,
            "openai": bool(openai_key),
            "claude": bool(anthropic_key),
            "active": row.provider == "internal" or bool(selected_key),
            "openai_key_preview": _mask_key(openai_key),
            "anthropic_key_preview": _mask_key(anthropic_key),
        }

    def build_system_prompt(self, settings: AgenteWhatsAppAISettings | None = None) -> str:
        row = settings or self.get_settings()
        parts = [
            row.prompt_base,
            f"Objetivo: {row.objective}" if row.objective else "",
            f"Tom de voz: {row.tone_of_voice}" if row.tone_of_voice else "",
            f"Regras comerciais: {row.business_rules}" if row.business_rules else "",
            f"Transferencia humana: {row.transfer_instructions}" if row.transfer_instructions else "",
            f"Limitacoes e proibicoes: {row.forbidden_topics}" if row.forbidden_topics else "",
            "Use as ferramentas reais do AGENTE WHATSAPP para consultar dados antes de afirmar qualquer informacao operacional.",
            "Quando houver contexto de campanha, use somente o snapshot resolvido como evidencia. Se houver ambiguidade, pergunte de qual oferta o cliente esta falando antes de citar valores, cupons ou beneficios.",
        ]
        return "\n\n".join(part.strip() for part in parts if part and part.strip())

    def test_ai_connection(self, message: str | None = None) -> dict[str, Any]:
        settings = self.get_settings()
        status = self.provider_status(settings)
        prompt = self.build_system_prompt(settings)
        test_message = (message or "Responda apenas: OK AGENTE WHATSAPP").strip()

        if settings.provider == "internal":
            return {
                "provider": "internal",
                "model": settings.model,
                "configured": True,
                "response": "OK AGENTE WHATSAPP",
                "latency_ms": 0,
                "tokens_input": 0,
                "tokens_output": 0,
                "prompt_preview": prompt[:1200],
            }

        provider = self._provider_instance(settings)
        if not provider.is_configured():
            raise ValueError(f"Chave de API do provedor '{settings.provider}' nao configurada.")
        response = provider.generate(
            system_prompt=prompt,
            messages=[AIMessage(role="user", content=test_message)],
            temperatura=settings.temperature,
            max_tokens=min(max(settings.max_tokens, 1), 200),
        )
        if response.error_reason:
            raise RuntimeError(response.error_reason)
        return {
            "provider": response.provider or settings.provider,
            "model": response.model or settings.model,
            "configured": status["active"],
            "response": response.content,
            "latency_ms": response.latencia_ms,
            "tokens_input": response.tokens_input,
            "tokens_output": response.tokens_output,
            "prompt_preview": prompt[:1200],
        }

    def _provider_instance(self, settings: AgenteWhatsAppAISettings):
        if settings.provider == "openai":
            return OpenAIProvider(model=settings.model or "gpt-4o-mini", api_key=settings.openai_api_key or "")
        return ClaudeProvider(model=settings.model or "claude-sonnet-4-20250514", api_key=settings.anthropic_api_key or "")

    def respond(
        self,
        *,
        session_id: str,
        message: str,
        auto_queue: bool = False,
        record_inbound: bool = False,
        source_message_id: str | None = None,
    ) -> dict[str, Any]:
        session = self._service.get_session(session_id)
        if not session:
            raise ValueError("Sessao do AGENTE WHATSAPP nao encontrada.")
        ai_settings = self.get_settings()
        if auto_queue and not ai_settings.enabled:
            raise ValueError("IA do AGENTE WHATSAPP desativada nas configuracoes.")

        clean_message = (message or "").strip()
        if not clean_message:
            raise ValueError("Informe a mensagem do cliente.")

        source_message = None
        if source_message_id:
            source_message = (
                self._db.query(AgenteWhatsAppMessage)
                .filter(
                    AgenteWhatsAppMessage.id == source_message_id,
                    AgenteWhatsAppMessage.session_id == session.id,
                )
                .first()
            )
            if not source_message:
                raise ValueError("Mensagem de origem nao encontrada nesta sessao.")
            existing_response = self._existing_response_to(source_message.id)
            if existing_response:
                payload = _json_load(existing_response.raw_payload_json)
                guardrails = self.guardrails(session_id=session.id)
                return {
                    "session_id": session.id,
                    "intent": payload.get("intent") or "atendimento",
                    "response": existing_response.body or "",
                    "needs_human": existing_response.provider_status in {"blocked_review", "failed"},
                    "auto_queued": existing_response.provider_status == "queued",
                    "message": self._service.serialize_message(existing_response),
                    "tool_calls": payload.get("tool_calls") if isinstance(payload.get("tool_calls"), list) else [],
                    "enqueued": 0,
                    "guardrails": guardrails,
                    "manager_review": payload.get("manager_review") if isinstance(payload.get("manager_review"), dict) else {},
                    "campaign_context": payload.get("campaign_context") if isinstance(payload.get("campaign_context"), dict) else {},
                    "ai_settings": {
                        "enabled": bool(ai_settings.enabled),
                        "provider": ai_settings.provider,
                        "model": ai_settings.model,
                    },
                }

        inbound_message = None
        if record_inbound:
            inbound_message = self._service.add_message(
                session,
                direction="inbound",
                sender_type="customer",
                message_type="text",
                body=clean_message,
                raw_payload={"source": "agente_whatsapp_ai_runtime"},
            )
            source_message_id = source_message_id or inbound_message.id
            source_message = source_message or inbound_message
        campaign_context = (
            AgenteWhatsAppCampaignContextService(self._db).resolve_message(source_message, persist=True)
            if source_message
            else AgenteWhatsAppCampaignContextService(self._db).resolve_latest_for_session(session.id, persist=True)
        )

        guardrails = self.guardrails(session_id=session.id)
        if auto_queue and not guardrails["allowed_auto_queue"]:
            reason = "; ".join(guardrails["reasons"]) or "Resposta automatica bloqueada pelos guardrails."
            self._service.add_event(
                event_type="agente_whatsapp_ai_response_blocked",
                session_id=session.id,
                customer_id=session.customer_id,
                source="agente_whatsapp_ai",
                payload={"reason": reason, "guardrails": guardrails},
                flush=False,
            )
            self._db.flush()
            raise ValueError(reason)

        intent = self._detect_intent(clean_message)
        trace: list[dict[str, Any]] = []
        customer_result = self._call_tool(
            trace,
            "buscar_cliente_por_telefone",
            {"phone": session.phone},
            session=session,
        )
        customer = self._extract_customer(customer_result) or {}
        customer_id = customer.get("id") or session.customer_id
        plan = self._plan_tools(clean_message, intent, customer_id)
        results: dict[str, dict[str, Any]] = {"buscar_cliente_por_telefone": customer_result}

        for step in plan:
            tool_name = step["tool_name"]
            results[tool_name] = self._call_tool(
                trace,
                tool_name,
                step.get("arguments") or {},
                session=session,
                customer_id=customer_id,
            )

        response, needs_human = self._compose_response(
            intent=intent,
            message=clean_message,
            session=session,
            customer=customer,
            results=results,
            campaign_context=campaign_context,
        )
        manager_review = self._manager_review_response(
            message=clean_message,
            response=response,
            intent=intent,
            session=session,
            trace=trace,
            needs_human=needs_human,
            campaign_context=campaign_context,
        )
        needs_human = bool(needs_human or manager_review["requires_human_review"])

        outbound_message = None
        enqueue_result = {"enqueued": 0, "skipped": 0}
        if auto_queue and manager_review["approved_for_auto_queue"]:
            outbound_message = self._service.add_message(
                session,
                direction="outbound",
                sender_type="ai",
                message_type="text",
                body=response,
                response_to_message_id=source_message_id,
                provider_status="queued",
                raw_payload={
                    "source": "agente_whatsapp_ai_runtime",
                    "intent": intent,
                    "tool_calls": trace,
                    "manager_review": manager_review,
                    "campaign_context": campaign_context,
                    "source_message_id": source_message_id,
                },
            )
            enqueue_result = AgenteWhatsAppOutboxService(self._db).enqueue_queued_messages(limit=20)
        elif auto_queue:
            outbound_message = self._service.add_message(
                session,
                direction="outbound",
                sender_type="ai",
                message_type="text",
                body=response,
                response_to_message_id=source_message_id,
                provider_status="blocked_review",
                raw_payload={
                    "source": "agente_whatsapp_ai_runtime",
                    "intent": intent,
                    "tool_calls": trace,
                    "manager_review": manager_review,
                    "campaign_context": campaign_context,
                    "source_message_id": source_message_id,
                },
            )
            if session.status not in {"human", "closed"}:
                session.status = "waiting_human"
            if manager_review["decision"] == "block":
                session.automation_blocked = True
            self._service.add_event(
                event_type="agente_whatsapp_manager_review_blocked",
                session_id=session.id,
                customer_id=customer_id,
                source="agente_whatsapp_manager",
                payload={
                    "intent": intent,
                    "response": response,
                    "manager_review": manager_review,
                    "message_id": outbound_message.id,
                },
                flush=False,
            )

        self._sync_context(
            session,
            intent=intent,
            message=clean_message,
            response=response,
            needs_human=needs_human,
            campaign_context=campaign_context,
        )
        self._service.add_event(
            event_type="agente_whatsapp_ai_response_generated",
            session_id=session.id,
            customer_id=customer_id,
            source="agente_whatsapp_ai",
            payload={
                "intent": intent,
                "auto_queue": auto_queue,
                "needs_human": needs_human,
                "tools": [item["tool_name"] for item in trace],
                "enqueued": enqueue_result.get("enqueued", 0),
                "guardrails": guardrails,
                "manager_review": manager_review,
                "campaign_context": campaign_context,
            },
            flush=False,
        )
        self._db.flush()
        return {
            "session_id": session.id,
            "intent": intent,
            "response": response,
            "needs_human": needs_human,
            "auto_queued": bool(auto_queue and manager_review["approved_for_auto_queue"]),
            "message": self._service.serialize_message(outbound_message) if outbound_message else None,
            "tool_calls": trace,
            "enqueued": enqueue_result.get("enqueued", 0),
            "guardrails": guardrails,
            "manager_review": manager_review,
            "campaign_context": campaign_context,
            "ai_settings": {
                "enabled": bool(ai_settings.enabled),
                "provider": ai_settings.provider,
                "model": ai_settings.model,
            },
        }

    def guardrails(self, *, session_id: str) -> dict[str, Any]:
        session = self._service.get_session(session_id)
        if not session:
            raise ValueError("Sessao do AGENTE WHATSAPP nao encontrada.")

        now = datetime.now(timezone.utc)
        window_start = now - timedelta(minutes=10)
        recent_ai_responses = (
            self._db.query(AgenteWhatsAppMessage)
            .filter(
                AgenteWhatsAppMessage.session_id == session.id,
                AgenteWhatsAppMessage.direction == "outbound",
                AgenteWhatsAppMessage.sender_type == "ai",
                AgenteWhatsAppMessage.created_at >= window_start,
            )
            .count()
        )
        latest_messages = (
            self._db.query(AgenteWhatsAppMessage)
            .filter(AgenteWhatsAppMessage.session_id == session.id)
            .order_by(AgenteWhatsAppMessage.created_at.desc())
            .limit(20)
            .all()
        )

        last_inbound_at = None
        last_ai_outbound_at = None
        consecutive_ai_outbound = 0
        for index, message in enumerate(latest_messages):
            if message.direction == "inbound" and last_inbound_at is None:
                last_inbound_at = message.created_at
            if message.direction == "outbound" and message.sender_type == "ai" and last_ai_outbound_at is None:
                last_ai_outbound_at = message.created_at
            if index == consecutive_ai_outbound and message.direction == "outbound" and message.sender_type == "ai":
                consecutive_ai_outbound += 1

        reasons: list[str] = []
        warnings: list[str] = []
        if not session.ai_enabled:
            reasons.append("IA desativada para esta conversa.")
        if session.automation_blocked:
            reasons.append("Automacoes bloqueadas para esta conversa.")
        if session.status in {"human", "ai_paused", "closed"}:
            reasons.append(f"Conversa em status {session.status}.")
        if not (session.phone or "").strip():
            reasons.append("Sessao sem telefone para envio.")
        if latest_messages and latest_messages[0].direction == "outbound" and latest_messages[0].sender_type == "ai":
            reasons.append("Aguardando nova mensagem do cliente antes de responder novamente.")
        if consecutive_ai_outbound >= 2:
            reasons.append("Limite de respostas consecutivas da IA atingido.")
        if recent_ai_responses >= 5:
            reasons.append("Limite de 5 respostas da IA em 10 minutos atingido.")
        if recent_ai_responses >= 3:
            warnings.append("Volume alto de respostas da IA nesta conversa.")

        return {
            "allowed_auto_queue": len(reasons) == 0,
            "safe_for_suggestion": True,
            "status": "blocked" if reasons else ("warning" if warnings else "allowed"),
            "reasons": reasons,
            "warnings": warnings,
            "recent_ai_responses": recent_ai_responses,
            "recent_window_seconds": 600,
            "consecutive_ai_outbound": consecutive_ai_outbound,
            "last_inbound_at": last_inbound_at,
            "last_ai_outbound_at": last_ai_outbound_at,
            "session_status": session.status,
            "ai_enabled": bool(session.ai_enabled),
            "automation_blocked": bool(session.automation_blocked),
        }

    def _existing_response_to(self, message_id: str) -> AgenteWhatsAppMessage | None:
        return (
            self._db.query(AgenteWhatsAppMessage)
            .filter(
                AgenteWhatsAppMessage.direction == "outbound",
                AgenteWhatsAppMessage.response_to_message_id == message_id,
            )
            .order_by(AgenteWhatsAppMessage.created_at.asc())
            .first()
        )

    def _manager_review_response(
        self,
        *,
        message: str,
        response: str,
        intent: str,
        session: AgenteWhatsAppSession,
        trace: list[dict[str, Any]],
        needs_human: bool,
        campaign_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        text = _normalize_text(f"{message}\n{response}")
        successful_tools = [item["tool_name"] for item in trace if item.get("success")]
        matched_categories: list[str] = []
        reasons: list[str] = []
        warnings: list[str] = []
        risk_level = "low"

        risk_rules = [
            (
                "pagamento_financeiro",
                "high",
                [
                    "pix nao caiu",
                    "pix errado",
                    "cobranca errada",
                    "pagamento divergente",
                    "estorno",
                    "reembolso",
                    "chargeback",
                    "cartao recusado",
                ],
            ),
            (
                "reclamacao_qualidade",
                "high",
                [
                    "reclamacao",
                    "veio errado",
                    "pedido errado",
                    "pizza fria",
                    "comida fria",
                    "produto estragado",
                    "intoxicacao",
                    "alergia",
                ],
            ),
            (
                "juridico_reputacao",
                "high",
                ["procon", "processo", "advogado", "denunciar", "policia", "vigilancia sanitaria"],
            ),
            (
                "cancelamento",
                "medium",
                ["cancelar", "cancela", "desistir", "nao quero mais", "cancelamento"],
            ),
            (
                "atendimento_humano",
                "medium",
                ["atendente", "humano", "pessoa", "gerente", "responsavel", "falar com alguem"],
            ),
            (
                "alteracao_pedido",
                "medium",
                ["alterar pedido", "mudar pedido", "trocar endereco", "trocar sabor", "adicionar item"],
            ),
        ]

        for category, level, terms in risk_rules:
            if any(term in text for term in terms):
                matched_categories.append(category)
                reasons.append(f"Detectado tema de risco: {category}.")
                if level == "high":
                    risk_level = "high"
                elif risk_level == "low":
                    risk_level = "medium"

        if needs_human:
            reasons.append("A propria resposta do Agente indicou necessidade de revisao humana.")
            if risk_level == "low":
                risk_level = "medium"

        evidence_tools = {
            "buscar_produtos",
            "buscar_promocoes",
            "validar_cupom",
            "calcular_frete",
            "consultar_status_pedido",
            "buscar_ultimo_pedido",
            "buscar_fidelidade",
        }
        response_mentions_money = bool(re.search(r"(?:r\$|\b\d+[,.]\d{2}\b)", response, flags=re.IGNORECASE))
        campaign_context_resolved = bool(
            campaign_context
            and campaign_context.get("status") == "resolved"
            and campaign_context.get("selected")
            and not campaign_context.get("ambiguous")
        )
        if response_mentions_money and not any(tool in evidence_tools for tool in successful_tools) and not campaign_context_resolved:
            reasons.append("Resposta menciona valor sem evidencia de ferramenta aprovada.")
            risk_level = "high"

        if intent == "consultar_status" and not any(tool in successful_tools for tool in ["consultar_status_pedido", "buscar_ultimo_pedido"]):
            warnings.append("Consulta de status sem pedido encontrado; manter resposta apenas solicitando identificacao.")

        if session.status in {"human", "ai_paused", "closed"} or session.automation_blocked:
            reasons.append("Sessao nao permite resposta automatica neste momento.")
            if risk_level == "low":
                risk_level = "medium"

        if risk_level == "high":
            decision = "block"
        elif reasons:
            decision = "revise"
        else:
            decision = "approve"

        return {
            "reviewer": "internal_manager_rules_v1",
            "decision": decision,
            "risk_level": risk_level,
            "approved_for_auto_queue": decision == "approve",
            "requires_human_review": decision != "approve",
            "reasons": reasons,
            "warnings": warnings,
            "matched_categories": matched_categories,
            "evidence_tools": successful_tools + (["campaign_context_snapshot"] if campaign_context_resolved else []),
            "safe_response": "Vou encaminhar para um atendente verificar com seguranca." if decision == "block" else None,
        }

    def _call_tool(
        self,
        trace: list[dict[str, Any]],
        tool_name: str,
        arguments: dict[str, Any],
        *,
        session: AgenteWhatsAppSession,
        customer_id: str | None = None,
    ) -> dict[str, Any]:
        result = self._tools.execute_tool(
            tool_name=tool_name,
            arguments=arguments,
            session_id=session.id,
            customer_id=customer_id,
        )
        trace.append(
            {
                "tool_name": result["tool_name"],
                "success": bool(result["success"]),
                "error": result.get("error"),
                "latency_ms": result.get("latency_ms") or 0,
                "arguments": arguments,
                "data": result.get("data"),
            }
        )
        return result

    def _detect_intent(self, message: str) -> str:
        text = _normalize_text(message)
        if any(word in text for word in ["status", "acompanhar", "andamento", "entrega", "chegou", "pedido #"]):
            return "consultar_status"
        if any(word in text for word in ["cupom", "desconto", "promocode", "codigo"]):
            return "validar_cupom"
        if any(word in text for word in ["frete", "entrega", "bairro", "retirada", "delivery"]):
            return "calcular_frete"
        if any(word in text for word in ["fidelidade", "ponto", "pontos", "beneficio", "beneficios"]):
            return "fidelidade"
        if any(word in text for word in ["ultimo pedido", "pedir de novo", "repetir", "mesmo pedido"]):
            return "recompra"
        if any(word in text for word in ["promocao", "promocoes", "oferta", "combo"]):
            return "promocoes"
        if any(word in text for word in ["cardapio", "menu", "pizza", "bebida", "quero", "pedir"]):
            return "venda_cardapio"
        return "atendimento"

    def _plan_tools(self, message: str, intent: str, customer_id: str | None) -> list[dict[str, Any]]:
        text = _normalize_text(message)
        plan: list[dict[str, Any]] = []
        if intent == "consultar_status":
            order_ref = self._extract_order_ref(message)
            if order_ref:
                plan.append({"tool_name": "consultar_status_pedido", "arguments": {"order_id": order_ref}})
            elif customer_id:
                plan.append({"tool_name": "buscar_ultimo_pedido", "arguments": {"customer_id": customer_id}})
        elif intent == "validar_cupom":
            code = self._extract_coupon_code(message)
            subtotal = self._extract_money(message)
            if code and subtotal:
                plan.append({"tool_name": "validar_cupom", "arguments": {"code": code, "order_subtotal": subtotal}})
            else:
                plan.append({"tool_name": "buscar_promocoes", "arguments": {"limit": 5}})
        elif intent == "calcular_frete":
            neighborhood = self._extract_after_label(text, ["bairro", "para"])
            city = self._extract_after_label(text, ["cidade"])
            subtotal = self._extract_money(message) or 0
            if city:
                plan.append(
                    {
                        "tool_name": "calcular_frete",
                        "arguments": {"city": city.title(), "neighborhood": neighborhood.title() if neighborhood else None, "order_subtotal": subtotal},
                    }
                )
        elif intent == "fidelidade" and customer_id:
            plan.append({"tool_name": "buscar_fidelidade", "arguments": {"customer_id": customer_id}})
        elif intent == "recompra" and customer_id:
            plan.append({"tool_name": "buscar_ultimo_pedido", "arguments": {"customer_id": customer_id}})
        elif intent == "promocoes":
            plan.append({"tool_name": "buscar_promocoes", "arguments": {"limit": 6}})
        elif intent == "venda_cardapio":
            search = self._extract_product_search(message)
            plan.append({"tool_name": "buscar_produtos", "arguments": {"search": search, "limit": 8, "active_only": True}})
            plan.append({"tool_name": "buscar_promocoes", "arguments": {"limit": 3}})
        else:
            plan.append({"tool_name": "buscar_produtos", "arguments": {"limit": 5, "active_only": True}})
        return plan

    def _compose_response(
        self,
        *,
        intent: str,
        message: str,
        session: AgenteWhatsAppSession,
        customer: dict[str, Any],
        results: dict[str, dict[str, Any]],
        campaign_context: dict[str, Any] | None = None,
    ) -> tuple[str, bool]:
        session_customer_name = session.customer.name if session.customer else None
        name = _first_name(customer.get("name") or session_customer_name)
        greeting = f"{name}, " if name else ""
        campaign_response = self._campaign_context_response(greeting, campaign_context)
        if campaign_response and intent in {"promocoes", "venda_cardapio", "atendimento", "validar_cupom"}:
            return campaign_response

        if intent == "consultar_status":
            status_result = results.get("consultar_status_pedido")
            last_result = results.get("buscar_ultimo_pedido")
            order = self._tool_data(status_result) or (self._tool_data(last_result) or {}).get("order")
            if order:
                return (
                    f"{greeting}seu pedido {order.get('order_code') or order.get('id')} esta com status {order.get('status')}. "
                    f"Total {_money(order.get('total'))}. Tempo estimado: {order.get('estimated_time') or 'em atualizacao'}.",
                    False,
                )
            return ("Consigo verificar seu pedido, mas preciso do numero do pedido ou que ele esteja vinculado a este telefone.", False)

        if intent == "validar_cupom":
            coupon_data = self._tool_data(results.get("validar_cupom"))
            if coupon_data:
                if coupon_data.get("valid"):
                    benefits = ", ".join(coupon_data.get("benefits") or [])
                    return (
                        f"{greeting}cupom {coupon_data.get('coupon_code')} validado. "
                        f"Desconto {_money(coupon_data.get('discount_amount'))}"
                        f"{f' e {benefits}' if benefits else ''}.",
                        False,
                    )
                return (f"{greeting}esse cupom nao passou na validacao: {coupon_data.get('message') or 'verifique as regras do cupom'}.", False)
            return ("Me envie o codigo do cupom e o valor aproximado do pedido para eu validar certinho.", False)

        if intent == "calcular_frete":
            freight_data = self._tool_data(results.get("calcular_frete"))
            if freight_data:
                if freight_data.get("available"):
                    return (
                        f"{greeting}o frete ficou {_money(freight_data.get('shipping_price'))}. "
                        f"Prazo estimado: {freight_data.get('estimated_time') or 'em atualizacao'}.",
                        False,
                    )
                return (f"{greeting}para esse endereco a entrega nao esta disponivel agora: {freight_data.get('message') or 'regiao indisponivel'}.", True)
            return ("Me diga cidade e bairro para eu calcular o frete com a regra real da loja.", False)

        if intent == "fidelidade":
            loyalty = self._tool_data(results.get("buscar_fidelidade"))
            if loyalty and loyalty.get("found"):
                account = loyalty.get("account") or {}
                benefits = loyalty.get("benefits") or []
                benefit_text = f" Beneficios disponiveis: {', '.join(item.get('label') for item in benefits[:3] if item.get('label'))}." if benefits else ""
                return (
                    f"{greeting}voce tem {account.get('total_points') or 0} pontos"
                    f"{f' no nivel {account.get('level_name')}' if account.get('level_name') else ''}.{benefit_text}",
                    False,
                )
            return ("Ainda nao encontrei pontos de fidelidade vinculados a este telefone.", False)

        if intent == "recompra":
            last_order = self._tool_data(results.get("buscar_ultimo_pedido"))
            order = (last_order or {}).get("order")
            if order:
                items = ", ".join(
                    f"{item.get('quantity')}x {item.get('product_name') or 'item'}"
                    for item in (order.get("items") or [])[:4]
                )
                return (
                    f"{greeting}seu ultimo pedido foi {items or 'um pedido salvo'} no total de {_money(order.get('total'))}. "
                    "Quer que eu monte igual para voce confirmar?",
                    False,
                )
            return ("Ainda nao encontrei pedido anterior neste telefone. Posso te mandar o cardapio para escolher agora.", False)

        if intent in {"promocoes", "venda_cardapio", "atendimento"}:
            product_text = self._format_products(results.get("buscar_produtos"))
            promo_text = self._format_promotions(results.get("buscar_promocoes"))
            if product_text and promo_text:
                return (f"{greeting}tenho estas opcoes reais do cardapio:\n{product_text}\n\nPromocoes ativas:\n{promo_text}\n\nQual delas voce quer pedir?", False)
            if product_text:
                return (f"{greeting}tenho estas opcoes reais do cardapio:\n{product_text}\n\nQual voce quer pedir?", False)
            if promo_text:
                return (f"{greeting}estas promocoes estao ativas agora:\n{promo_text}\n\nQuer que eu veja os produtos para montar o pedido?", False)
            return ("Nao encontrei item ativo para essa busca. Me diga o sabor ou tipo de produto que voce quer.", False)

        return ("Posso te ajudar com cardapio, promocoes, frete, cupom, pedido ou fidelidade. O que voce quer fazer agora?", False)

    def _campaign_context_response(self, greeting: str, campaign_context: dict[str, Any] | None) -> tuple[str, bool] | None:
        if not campaign_context:
            return None
        if campaign_context.get("ambiguous"):
            candidates = campaign_context.get("candidates") or []
            labels = [
                item.get("campaign_name") or item.get("template_name") or "oferta recente"
                for item in candidates[:3]
            ]
            label_text = ", ".join(label for label in labels if label)
            return (
                f"{greeting}vi mais de uma campanha recente{f': {label_text}' if label_text else ''}. "
                "Para eu nao te passar uma oferta errada, me diga de qual delas voce esta falando?",
                False,
            )
        selected = campaign_context.get("selected") or {}
        if campaign_context.get("status") != "resolved" or not selected:
            return None
        campaign_name = selected.get("campaign_name") or selected.get("template_name") or "essa oferta"
        snapshot = selected.get("message_text") or selected.get("caption")
        if not snapshot:
            return (
                f"{greeting}achei o disparo da campanha {campaign_name}, mas ele nao tem snapshot comercial suficiente. "
                "Vou conferir pelo cardapio real antes de confirmar valores ou disponibilidade.",
                False,
            )
        return (
            f"{greeting}sobre {campaign_name}, o texto enviado foi:\n{snapshot}\n\n"
            "Posso te ajudar a montar o pedido com base nessa oferta. Se quiser preco, cupom ou disponibilidade, eu confirmo pelo sistema antes de fechar.",
            False,
        )

    def _format_products(self, result: dict[str, Any] | None) -> str:
        data = self._tool_data(result) or {}
        items = data.get("items") or []
        lines = []
        for item in items[:6]:
            price = item.get("current_price") if item.get("current_price") is not None else item.get("price")
            suffix = f" - {_money(price)}" if price is not None else ""
            lines.append(f"- {item.get('name')}{suffix}")
        return "\n".join(lines)

    def _format_promotions(self, result: dict[str, Any] | None) -> str:
        data = self._tool_data(result) or {}
        lines = []
        for promo in (data.get("product_promotions") or [])[:4]:
            label = promo.get("product_name") or promo.get("name")
            discount = promo.get("default_value")
            extra = f" ({promo.get('discount_type')} {discount})" if discount is not None else ""
            lines.append(f"- {label}{extra}")
        for promo in (data.get("promotions") or [])[:3]:
            lines.append(f"- {promo.get('title')}{f': {promo.get('description')}' if promo.get('description') else ''}")
        return "\n".join(line for line in lines if line and line != "- None")

    @staticmethod
    def _tool_data(result: dict[str, Any] | None) -> dict[str, Any] | None:
        if not result or not result.get("success"):
            return None
        data = result.get("data")
        return data if isinstance(data, dict) else None

    @staticmethod
    def _extract_customer(result: dict[str, Any] | None) -> dict[str, Any] | None:
        data = AgenteWhatsAppAIService._tool_data(result) or {}
        customer = data.get("customer")
        return customer if isinstance(customer, dict) else None

    @staticmethod
    def _extract_order_ref(message: str) -> str | None:
        uuid_match = re.search(r"\b[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}\b", message)
        if uuid_match:
            return uuid_match.group(0)
        code_match = re.search(r"(?:pedido|#)\s*([A-Za-z0-9-]{4,30})", message, flags=re.IGNORECASE)
        return code_match.group(1) if code_match else None

    @staticmethod
    def _extract_coupon_code(message: str) -> str | None:
        match = re.search(r"(?:cupom|codigo|code)\s*[:#-]?\s*([A-Za-z0-9_-]{3,30})", message, flags=re.IGNORECASE)
        return match.group(1).upper() if match else None

    @staticmethod
    def _extract_money(message: str) -> float | None:
        match = re.search(r"(?:r\$\s*)?(\d{1,5}(?:[,.]\d{1,2})?)", message, flags=re.IGNORECASE)
        if not match:
            return None
        try:
            return float(match.group(1).replace(",", "."))
        except ValueError:
            return None

    @staticmethod
    def _extract_after_label(text: str, labels: list[str]) -> str | None:
        for label in labels:
            match = re.search(rf"{label}\s+([a-z0-9\s-]{{3,40}})", text)
            if match:
                return match.group(1).strip(" .,-")
        return None

    @staticmethod
    def _extract_product_search(message: str) -> str:
        text = _normalize_text(message)
        for token in ["pizza de ", "quero ", "pedir ", "tem "]:
            if token in text:
                value = text.split(token, 1)[1].strip()
                return value[:80]
        return ""

    def _sync_context(
        self,
        session: AgenteWhatsAppSession,
        *,
        intent: str,
        message: str,
        response: str,
        needs_human: bool,
        campaign_context: dict[str, Any] | None = None,
    ) -> None:
        context = session.context
        if not context:
            context = AgenteWhatsAppContext(
                id=str(uuid.uuid4()),
                session_id=session.id,
                customer_id=session.customer_id,
            )
            self._db.add(context)
        context.last_intent = intent
        context.sentiment = "needs_human" if needs_human else "neutral"
        short_context = _json_load(context.short_context_json)
        short_context["last_customer_message"] = message
        short_context["last_ai_response"] = response
        if campaign_context:
            short_context["campaign_context"] = campaign_context
        context.short_context_json = _json_dump(short_context)
        context.updated_at = datetime.now(timezone.utc)
        session.current_intent = intent
        session.updated_at = datetime.now(timezone.utc)

    @staticmethod
    def _safe_json_string(value: str) -> str:
        import json

        return json.dumps(value or "", ensure_ascii=False)
