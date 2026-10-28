"""Business rules for the tenant-scoped Gestor administrative foundation."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from datetime import date
from decimal import Decimal
import base64
import binascii
import hashlib
import hmac
import json
import re
import secrets
import os
import time
import requests
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Callable
from uuid import uuid4
from fastapi.encoders import jsonable_encoder
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy import or_, text, update

from backend.core.exceptions import DomainError
from backend.models.gestor import (
    GestorAISettings, GestorAuthorizedContact, GestorOperation,
    GestorWhatsAppChannel, GestorWhatsAppMessage, GestorWhatsAppOutbox,
    GestorMultimodalArtifact, GestorMultimodalAudit, GestorAutomation,
    GestorAutomationRun, GestorAutomationAudit,
)
from backend.models.membership import TenantMembership
from backend.models.admin import AdminUser
from backend.models.upload_asset import TenantUploadAsset
from backend.models.rbac import RbacModule, RbacPermission, Role, RolePermission, UserPermission
from backend.schemas.gestor import (
    GestorBIDashboardArguments, GestorContactCreate, GestorContactUpdate,
    GestorFinanceOverviewArguments, GestorInventoryOverviewArguments,
    GestorInventoryApproveReceiptArguments, GestorInventoryApproveReceiptResult,
    GestorOperationPreviewIn, GestorOperationsSummaryArguments,
    GestorToolCatalogItem, GestorToolExecuteIn,
    GestorAIPlanIn, GestorAIPlanOut, GestorAIProposedTool, GestorAISettingsUpdate,
    GestorAIUsage,
    GestorAIProviderPlan,
    GestorWhatsAppChannelUpdate,
    GestorWhatsAppMessageOut,
    GestorFiscalOverviewArguments, GestorLogisticsSummaryArguments,
    GestorProductsCatalogArguments, GestorCRMSummaryArguments,
    GestorProductUpdatePriceArguments, GestorFinanceCreateExpenseArguments,
    GestorCRMCreateTaskArguments, GestorInventoryManualEntryArguments,
    GestorOrderStatusUpdateArguments, GestorToolResult,
    GestorWhatsAppSendMessageArguments,
    GestorMultimodalIn, GestorMultimodalReviewIn,
    GestorAutomationCreate, GestorAutomationUpdate, GestorAutomationSimulateIn,
)
from backend.config import PROJECT_ROOT
from backend.core.tenant_context import TenantSource, trusted_process_context
from backend.core.tenant_execution import tenant_upload_path
from backend.services.tenant_upload_service import TenantUploadService
from backend.services.fiscal_receipt_xml import parse_receipt_xml, ReceiptXmlError
from backend.services.automation_registry import TRIGGERS, conditions_match, validate_definition
from backend.schemas.automation_core import AutomationDefinitionInput


@dataclass(frozen=True)
class _ToolSpec:
    name: str
    description: str
    module: str
    arguments_model: type
    handler: Callable[["GestorService", Any], dict[str, Any]]
    risk_level: str = "low"
    mutates_data: bool = False
    requires_confirmation: bool = False
    evidence_required: tuple[str, ...] = ()
    reauth_required: bool = False
    permission: str = "view"
    result_model: type = GestorToolResult
    available: bool = True
    unavailable_reason: str | None = None


def _tool_specs() -> dict[str, _ToolSpec]:
    return {
        "gestor.bi.dashboard": _ToolSpec(
            "gestor.bi.dashboard", "Indicadores de vendas e BI do tenant.", "bi",
            GestorBIDashboardArguments, GestorService._execute_bi_dashboard,
        ),
        "gestor.inventory.overview": _ToolSpec(
            "gestor.inventory.overview", "Visao geral de estoque, compras e movimentacoes.", "inventory",
            GestorInventoryOverviewArguments, GestorService._execute_inventory_overview,
        ),
        "gestor.finance.overview": _ToolSpec(
            "gestor.finance.overview", "Visao geral financeira, contas e transacoes.", "finance",
            GestorFinanceOverviewArguments, GestorService._execute_finance_overview,
        ),
        "gestor.operations.summary": _ToolSpec(
            "gestor.operations.summary", "Resumo operacional de pedidos, cozinha e expedicao.", "pedidos",
            GestorOperationsSummaryArguments, GestorService._execute_operations_summary,
        ),
        "gestor.products.catalog": _ToolSpec(
            "gestor.products.catalog", "Catalogo real de produtos e precos por canal.", "cardapio",
            GestorProductsCatalogArguments, GestorService._execute_products_catalog,
        ),
        "gestor.crm.summary": _ToolSpec(
            "gestor.crm.summary", "Resumo real de clientes, pipeline e tarefas do CRM.", "clientes",
            GestorCRMSummaryArguments, GestorService._execute_crm_summary,
        ),
        "gestor.fiscal.overview": _ToolSpec(
            "gestor.fiscal.overview", "Visao geral fiscal real do tenant.", "fiscal",
            GestorFiscalOverviewArguments, GestorService._execute_fiscal_overview,
        ),
        "gestor.logistics.summary": _ToolSpec(
            "gestor.logistics.summary", "Resumo real de expedicao, entregas e KDS.", "entregas",
            GestorLogisticsSummaryArguments, GestorService._execute_logistics_summary,
        ),
        "gestor.products.update_price": _ToolSpec(
            "gestor.products.update_price", "Atualizar preco de um produto existente.", "cardapio",
            GestorProductUpdatePriceArguments, GestorService._execute_products_update_price,
            risk_level="high", mutates_data=True, requires_confirmation=True,
            evidence_required=("product_id", "current_price", "new_price"), reauth_required=True, permission="edit",
        ),
        "gestor.finance.create_expense": _ToolSpec(
            "gestor.finance.create_expense", "Criar uma despesa financeira.", "finance",
            GestorFinanceCreateExpenseArguments, GestorService._execute_finance_create_expense,
            risk_level="high", mutates_data=True, requires_confirmation=True,
            evidence_required=("description", "amount", "competence_date"), reauth_required=True, permission="create",
        ),
        "gestor.inventory.create_manual_entry": _ToolSpec(
            "gestor.inventory.create_manual_entry", "Registrar uma movimentacao manual de estoque.", "inventory",
            GestorInventoryManualEntryArguments, GestorService._execute_inventory_manual_entry,
            risk_level="medium", mutates_data=True, requires_confirmation=True,
            evidence_required=("item_id", "movement_type", "quantity"), permission="create",
        ),
        "gestor.operations.update_order_status": _ToolSpec(
            "gestor.operations.update_order_status", "Atualizar status de pedido pela maquina de estados.", "pedidos",
            GestorOrderStatusUpdateArguments, GestorService._execute_order_status_update,
            risk_level="high", mutates_data=True, requires_confirmation=True,
            evidence_required=("order_id", "current_status", "new_status"), reauth_required=True, permission="edit",
        ),
        "gestor.crm.create_task": _ToolSpec(
            "gestor.crm.create_task", "Criar tarefa de CRM.", "clientes",
            GestorCRMCreateTaskArguments, GestorService._execute_crm_create_task,
            risk_level="medium", mutates_data=True, requires_confirmation=True, permission="create",
            available=False, unavailable_reason="CRM nao possui service de dominio canonico para criacao de tarefas.",
        ),
        "gestor.inventory.approve_receipt": _ToolSpec(
            "gestor.inventory.approve_receipt", "Aprovar um documento de recebimento de estoque existente.", "inventory",
            GestorInventoryApproveReceiptArguments, GestorService._execute_inventory_approve_receipt,
            risk_level="medium", mutates_data=True, requires_confirmation=True,
        ),
        "gestor.whatsapp.send_message": _ToolSpec(
            "gestor.whatsapp.send_message", "Enfileirar mensagem administrativa pelo WhatsApp oficial Meta.", "whatsapp",
            GestorWhatsAppSendMessageArguments, GestorService._execute_whatsapp_send_message,
            risk_level="medium", mutates_data=True, requires_confirmation=True,
            evidence_required=("to_phone", "message_type", "policy"), reauth_required=True, permission="edit",
        ),
    }


class GestorContactNotFound(DomainError):
    http_status = 404


class GestorOperationNotFound(DomainError):
    http_status = 404


class GestorOperationInvalid(DomainError):
    http_status = 409


class GestorAIUnavailable(DomainError):
    http_status = 503


class GestorWhatsAppNotConfigured(DomainError):
    http_status = 503


class GestorWhatsAppPolicyDenied(DomainError):
    http_status = 409


class GestorMultimodalInvalid(DomainError):
    http_status = 422


class GestorService:
    def __init__(self, db: Session, tenant_id: str, admin_id: str, tenant_context=None):
        if not tenant_id:
            raise DomainError("Contexto de tenant obrigatorio para o Gestor.", code="TenantContextMissing")
        self.db = db
        self.tenant_id = tenant_id
        self.admin_id = admin_id
        self.tenant_context = tenant_context

    @staticmethod
    def _mask_identifier(value: str | None) -> str | None:
        value = (value or "").strip()
        if not value:
            return None
        if len(value) <= 6:
            return "*" * len(value)
        return f"{value[:3]}...{value[-3:]}"

    @staticmethod
    def resolve_gestor_meta_secret(secret_ref: str | None) -> str | None:
        """Resolve only an external secret reference; never read clear DB credentials."""
        ref = (secret_ref or "").strip()
        if not ref.startswith("env:"):
            return None
        env_name = ref[4:].strip()
        if not re.fullmatch(r"GESTOR_META_APP_SECRET_[A-Z0-9_]+", env_name):
            return None
        value = os.getenv(env_name, "").strip()
        return value or None

    @staticmethod
    def resolve_gestor_meta_access_token(secret_ref: str | None) -> str | None:
        """Resolve a bearer token only from the external environment."""
        ref = (secret_ref or "").strip()
        if not ref.startswith("env:"):
            return None
        env_name = ref[4:].strip()
        if not re.fullmatch(r"GESTOR_META_ACCESS_TOKEN_[A-Z0-9_]+", env_name):
            return None
        value = os.getenv(env_name, "").strip()
        return value or None

    def get_whatsapp_channel(self) -> GestorWhatsAppChannel | None:
        return self.db.query(GestorWhatsAppChannel).filter(
            GestorWhatsAppChannel.tenant_id == self.tenant_id,
        ).first()

    def update_whatsapp_channel(self, body: GestorWhatsAppChannelUpdate) -> GestorWhatsAppChannel:
        channel = self.get_whatsapp_channel()
        values = body.model_dump(exclude_unset=True)
        if channel is None:
            required = {"phone_number_id", "business_account_id", "app_secret_ref", "verify_token"}
            missing = sorted(key for key in required if not values.get(key))
            if missing:
                raise GestorWhatsAppNotConfigured(
                    "Canal Meta exige phone_number_id, business_account_id, verify_token e app_secret_ref.",
                    code="GestorWhatsAppConfigurationRequired",
                )
            channel = GestorWhatsAppChannel(
                tenant_id=self.tenant_id,
                enabled=False,
                phone_number_id=str(values.pop("phone_number_id")).strip(),
                business_account_id=str(values.pop("business_account_id")).strip(),
                app_secret_ref=str(values.pop("app_secret_ref")).strip(),
                verify_token_hash=self._hash_token(str(values.pop("verify_token"))),
                status="pending_secret",
            )
            self.db.add(channel)
            for key, value in values.items():
                if key == "verify_token":
                    continue
                if value is not None and key == "integration_connection_id":
                    value = str(value)
                if isinstance(value, str):
                    value = value.strip()
                setattr(channel, key, value)
        else:
            if "verify_token" in values:
                token = str(values.pop("verify_token") or "").strip()
                if not token:
                    raise GestorWhatsAppNotConfigured("verify_token nao pode ser vazio.", code="GestorWhatsAppVerifyTokenRequired")
                channel.verify_token_hash = self._hash_token(token)
            else:
                values.pop("verify_token", None)
            for key, value in values.items():
                if value is not None and key == "integration_connection_id":
                    value = str(value)
                if isinstance(value, str):
                    value = value.strip()
                setattr(channel, key, value)

        if channel.integration_connection_id:
            row = self.db.execute(text(
                "SELECT tenant_id, integration_type FROM integration_connections WHERE id = :id"
            ), {"id": str(channel.integration_connection_id)}).mappings().first()
            if not row or str(row["tenant_id"]) != self.tenant_id or row["integration_type"] != "whatsapp_cloud":
                raise GestorWhatsAppNotConfigured(
                    "integration_connection_id deve apontar para uma conexao WhatsApp Cloud do tenant.",
                    code="GestorWhatsAppIntegrationMismatch",
                )

        secret = self.resolve_gestor_meta_secret(channel.app_secret_ref)
        access_token = self.resolve_gestor_meta_access_token(channel.access_token_ref)
        channel.status = "ready_send" if secret and access_token else ("ready_receive_only" if secret else "pending_secret")
        channel.last_error = None if secret else "Referencia de app_secret sem segredo resolvivel; ativacao bloqueada."
        if values.get("enabled") is True and not secret:
            channel.enabled = False
            self.db.flush()
            raise GestorWhatsAppNotConfigured(
                "Ativacao recusada: configure um secret manager/ref resolvivel para app_secret; nenhum segredo e armazenado pelo Gestor.",
                code="GestorWhatsAppSecretUnavailable",
            )
        if channel.enabled and not secret:
            channel.enabled = False
            self.db.flush()
            raise GestorWhatsAppNotConfigured(
                "Canal nao pode permanecer ativo sem app_secret resolvivel.", code="GestorWhatsAppSecretUnavailable"
            )
        if not channel.enabled:
            channel.status = "disabled" if secret else "pending_secret"
        self.db.flush()
        return channel

    @classmethod
    def _channel_for_phone(cls, db: Session, phone_number_id: str) -> GestorWhatsAppChannel | None:
        return db.query(GestorWhatsAppChannel).filter(
            GestorWhatsAppChannel.phone_number_id == phone_number_id,
            GestorWhatsAppChannel.enabled.is_(True),
        ).first()

    @classmethod
    def verify_gestor_meta_challenge(cls, db: Session, token: str | None) -> str | None:
        if not token:
            return None
        token_hash = cls._hash_token(token)
        rows = db.query(GestorWhatsAppChannel).filter(
            GestorWhatsAppChannel.enabled.is_(True),
            GestorWhatsAppChannel.verify_token_hash == token_hash,
        ).all()
        return "ok" if len(rows) == 1 and cls.resolve_gestor_meta_secret(rows[0].app_secret_ref) else None

    @classmethod
    def _payload_phone_ids(cls, payload: dict[str, Any]) -> set[str]:
        ids: set[str] = set()
        for entry in payload.get("entry") or []:
            for change in (entry or {}).get("changes") or []:
                value = (change or {}).get("value") or {}
                messages = value.get("messages") or []
                if not messages:
                    continue
                phone_id = str((value.get("metadata") or {}).get("phone_number_id") or "").strip()
                if not phone_id:
                    raise GestorWhatsAppNotConfigured("Webhook Meta sem phone_number_id.", code="GestorWhatsAppPhoneIdMissing")
                ids.add(phone_id)
        return ids

    @classmethod
    def receive_gestor_meta_webhook(cls, db: Session, payload: dict[str, Any], raw_body: bytes, signature: str) -> dict[str, Any]:
        phone_ids = cls._payload_phone_ids(payload)
        if not phone_ids:
            raise GestorWhatsAppNotConfigured("Webhook Meta sem mensagem identificavel.", code="GestorWhatsAppMessageMissing")
        channels = [cls._channel_for_phone(db, phone_id) for phone_id in phone_ids]
        if any(channel is None for channel in channels) or len({channel.tenant_id for channel in channels if channel}) != 1:
            raise GestorWhatsAppNotConfigured("phone_number_id nao pertence a um canal Gestor ativo deste tenant.", code="GestorWhatsAppChannelMismatch")
        channel = channels[0]
        secret = cls.resolve_gestor_meta_secret(channel.app_secret_ref)
        if not secret:
            raise GestorWhatsAppNotConfigured("Canal Meta sem app_secret resolvivel.", code="GestorWhatsAppSecretUnavailable")
        if not signature.startswith("sha256="):
            raise GestorWhatsAppNotConfigured("Assinatura Meta invalida.", code="GestorWhatsAppSignatureInvalid")
        expected = "sha256=" + hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected):
            raise GestorWhatsAppNotConfigured("Assinatura Meta invalida.", code="GestorWhatsAppSignatureInvalid")

        received = duplicates = 0
        for entry in payload.get("entry") or []:
            for change in (entry or {}).get("changes") or []:
                value = (change or {}).get("value") or {}
                for message in value.get("messages") or []:
                    provider_id = str((message or {}).get("id") or "").strip()
                    if not provider_id:
                        continue
                    existing = db.query(GestorWhatsAppMessage.id).filter(
                        GestorWhatsAppMessage.tenant_id == channel.tenant_id,
                        GestorWhatsAppMessage.provider_message_id == provider_id,
                    ).first()
                    if existing:
                        duplicates += 1
                        continue
                    message_type = str((message or {}).get("type") or "unknown")[:40]
                    text_body = ((message or {}).get("text") or {}).get("body")
                    db.add(GestorWhatsAppMessage(
                        tenant_id=channel.tenant_id, channel_id=channel.id,
                        provider_message_id=provider_id,
                        from_phone=str((message or {}).get("from") or "")[:32],
                        message_type=message_type, text_body=str(text_body) if text_body is not None else None,
                        payload_json=message, status="RECEIVED",
                    ))
                    received += 1
        db.flush()
        return {"accepted": True, "tenant_id": channel.tenant_id, "channel_id": channel.id, "received": received, "duplicates": duplicates, "status": "RECEIVED"}

    @staticmethod
    def _inbox_metadata(message: GestorWhatsAppMessage) -> dict[str, Any]:
        payload = message.payload_json if isinstance(message.payload_json, dict) else {}
        metadata = payload.get("_gestor_processing")
        return dict(metadata) if isinstance(metadata, dict) else {}

    def _save_inbox_metadata(self, message: GestorWhatsAppMessage, **changes: Any) -> None:
        payload = dict(message.payload_json) if isinstance(message.payload_json, dict) else {}
        metadata = self._inbox_metadata(message)
        metadata.update(changes)
        payload["_gestor_processing"] = metadata
        message.payload_json = payload
        message.updated_at = datetime.now(timezone.utc)

    @staticmethod
    def _inbox_error(kind: str) -> str:
        # Inbox errors are intentionally generic: provider responses and exception
        # text must never become a channel-visible or persisted secret leak.
        return {
            "unauthorized": "Remetente nao autorizado para o Gestor neste tenant.",
            "planner": "Falha no planejamento administrativo do Gestor.",
            "operation": "Falha ao registrar o planejamento administrativo.",
        }.get(kind, "Falha no processamento administrativo do Gestor.")

    def process_gestor_inbox(self, limit: int = 20) -> dict[str, int]:
        """Plan received administrative messages without executing any tool.

        Claiming is an atomic RECEIVED -> PROCESSING update, so repeated worker
        calls cannot create a second operation for the same provider message.
        """
        limit = max(1, min(int(limit), 50))
        counters = {"processed": 0, "planned": 0, "responded": 0, "rejected": 0, "failed": 0, "skipped": 0}
        candidates = self.db.query(GestorWhatsAppMessage.id).filter(
            GestorWhatsAppMessage.tenant_id == self.tenant_id,
            GestorWhatsAppMessage.status == "RECEIVED",
        ).order_by(GestorWhatsAppMessage.created_at.asc()).limit(limit).all()

        for (message_id,) in candidates:
            claimed = self.db.execute(update(GestorWhatsAppMessage).where(
                GestorWhatsAppMessage.id == message_id,
                GestorWhatsAppMessage.tenant_id == self.tenant_id,
                GestorWhatsAppMessage.status == "RECEIVED",
            ).values(status="PROCESSING", updated_at=datetime.now(timezone.utc)))
            if claimed.rowcount != 1:
                counters["skipped"] += 1
                continue
            message = self.db.query(GestorWhatsAppMessage).filter(
                GestorWhatsAppMessage.id == message_id,
                GestorWhatsAppMessage.tenant_id == self.tenant_id,
            ).first()
            if message is None:
                counters["skipped"] += 1
                continue
            counters["processed"] += 1
            try:
                sender_phone = self.normalize_phone(message.from_phone)
            except DomainError:
                sender_phone = ""
            contact = self.db.query(GestorAuthorizedContact).filter(
                GestorAuthorizedContact.tenant_id == self.tenant_id,
                GestorAuthorizedContact.phone_normalized == sender_phone,
                GestorAuthorizedContact.active.is_(True),
            ).first()
            if contact is None:
                message.status = "REJECTED"
                self._save_inbox_metadata(message, error=self._inbox_error("unauthorized"))
                counters["rejected"] += 1
                self.db.flush()
                continue
            try:
                if not (message.text_body or "").strip():
                    raise GestorOperationInvalid("Mensagem sem texto para planejamento administrativo.", code="GestorInboxTextMissing")
                plan = self.plan_ai(GestorAIPlanIn(message=message.text_body, channel="gestor"))
                metadata = {
                    "response_text": plan.response_text,
                    "provider": plan.provider,
                    "model": plan.model,
                    "no_execution": True,
                }
                if not plan.proposed_tools:
                    message.status = "RESPONDED"
                    self._save_inbox_metadata(message, **metadata)
                    counters["responded"] += 1
                    continue
                proposal = plan.proposed_tools[0]
                idempotency_key = "gestor-inbox-" + hashlib.sha256(
                    f"{self.tenant_id}:{message.provider_message_id}".encode("utf-8")
                ).hexdigest()
                operation, _token = self.create_operation(GestorOperationPreviewIn(
                    channel="gestor_whatsapp", phone=message.from_phone,
                    tool_name=proposal.tool_name, risk_level=proposal.risk_level,
                    arguments=proposal.arguments,
                    preview={"summary": proposal.summary, "response_text": plan.response_text,
                             "evidence_required": proposal.evidence_required, "source_message_id": message.id},
                    idempotency_key=idempotency_key,
                ))
                operation.requested_by_admin_id = contact.admin_user_id
                operation.status = "PLANNED"
                metadata.update({"operation_id": operation.id, "tool_name": proposal.tool_name,
                                 "confirmation_required": proposal.requires_confirmation})
                message.status = "PLANNED"
                self._save_inbox_metadata(message, **metadata)
                counters["planned"] += 1
            except Exception:
                message.status = "FAILED"
                self._save_inbox_metadata(message, error=self._inbox_error("planner"))
                counters["failed"] += 1
            self.db.flush()
        return counters

    def list_gestor_inbox(self, status: str | None = None, limit: int = 100) -> list[GestorWhatsAppMessage]:
        query = self.db.query(GestorWhatsAppMessage).filter(
            GestorWhatsAppMessage.tenant_id == self.tenant_id,
        )
        if status:
            query = query.filter(GestorWhatsAppMessage.status == status.strip().upper())
        return query.order_by(GestorWhatsAppMessage.created_at.desc()).limit(max(1, min(int(limit), 500))).all()

    def get_ai_settings(self) -> GestorAISettings:
        item = self.db.query(GestorAISettings).filter(GestorAISettings.tenant_id == self.tenant_id).first()
        if item is None:
            item = GestorAISettings(tenant_id=self.tenant_id)
            self.db.add(item)
            self.db.flush()
        return item

    def update_ai_settings(self, body: GestorAISettingsUpdate) -> GestorAISettings:
        item = self.get_ai_settings()
        for key, value in body.model_dump(exclude_unset=True).items():
            setattr(item, key, value.strip() if isinstance(value, str) else value)
        self.db.flush()
        return item

    @staticmethod
    def _secret_preview(value: str | None) -> str | None:
        value = (value or "").strip()
        if not value:
            return None
        return "configurada" if len(value) <= 10 else f"{value[:3]}...{value[-4:]}"

    def ai_status(self) -> dict[str, Any]:
        from backend.config import get_ai_api_key
        settings = self.get_ai_settings()
        openai_key = get_ai_api_key("OPENAI_API_KEY")
        claude_key = get_ai_api_key("ANTHROPIC_API_KEY")
        configured = settings.provider == "internal" or bool(openai_key if settings.provider == "openai" else claude_key)
        return {
            "provider": settings.provider, "configured": configured,
            "enabled": bool(settings.enabled), "model": settings.model,
            "openai_configured": bool(openai_key), "claude_configured": bool(claude_key),
            "openai_key_preview": self._secret_preview(openai_key),
            "claude_key_preview": self._secret_preview(claude_key),
        }

    @staticmethod
    def _plan_tool(name: str, arguments: dict[str, Any], summary: str) -> GestorAIProposedTool:
        spec = _tool_specs().get(name)
        if spec is None:
            raise GestorOperationInvalid("Ferramenta proposta pela IA nao pertence ao catalogo do Gestor.", code="GestorUnknownTool")
        return GestorAIProposedTool(
            tool_name=name, arguments=arguments, risk_level=spec.risk_level,
            requires_confirmation=spec.requires_confirmation, summary=summary,
            evidence_required=["dados reais do modulo canonico"],
        )

    def _deterministic_plan(self, message: str, settings: GestorAISettings) -> GestorAIPlanOut:
        text = message.lower()
        tools: list[GestorAIProposedTool] = []
        if any(word in text for word in ("aprovar", "aprovação", "recebimento")):
            match = re.search(r"(?:documento|document|id)\s*[:#-]?\s*([a-z0-9][a-z0-9._/-]{1,199})", text, re.I)
            if match:
                tools.append(self._plan_tool("gestor.inventory.approve_receipt", {"document_id": match.group(1)}, "Aprovar o recebimento identificado; a execução exige confirmação explícita."))
        elif any(word in text for word in ("venda", "vendas", "faturamento", "receita")):
            tools.append(self._plan_tool("gestor.bi.dashboard", {"period": "30d"}, "Consultar indicadores reais de vendas no período padrão de 30 dias."))
        elif "estoque" in text or "inventário" in text:
            tools.append(self._plan_tool("gestor.inventory.overview", {}, "Consultar a visão real de estoque e movimentações."))
        elif any(word in text for word in ("financeiro", "finanças", "contas", "despesas")):
            tools.append(self._plan_tool("gestor.finance.overview", {}, "Consultar os indicadores financeiros disponíveis."))
        elif any(word in text for word in ("operação", "operacional", "pedido", "kds", "entrega", "cozinha")):
            tools.append(self._plan_tool("gestor.operations.summary", {}, "Consultar o resumo operacional real."))
        response = "Planejamento concluído sem executar ferramentas."
        if not tools:
            response = "Não reconheci uma intenção administrativa segura. Informe vendas, estoque, financeiro, operações ou um documento explícito para aprovação."
        return GestorAIPlanOut(provider="internal", model=settings.model, response_text=response, proposed_tools=tools, usage=GestorAIUsage())

    @staticmethod
    def _strict_plan_model() -> dict[str, Any]:
        return {
            "type": "object", "additionalProperties": False,
            "required": ["response_text", "proposed_tools"],
            "properties": {
                "response_text": {"type": "string"},
                "proposed_tools": {"type": "array", "items": {
                    "type": "object", "additionalProperties": False,
                    "required": ["tool_name", "arguments", "summary", "evidence_required"],
                    "properties": {"tool_name": {"type": "string"}, "arguments": {"type": "object"},
                                   "summary": {"type": "string"}, "evidence_required": {"type": "array", "items": {"type": "string"}}},
                }},
            },
        }

    def plan_ai(self, body: GestorAIPlanIn) -> GestorAIPlanOut:
        settings = self.get_ai_settings()
        if not settings.enabled:
            raise GestorAIUnavailable("Gestor IA desabilitado para este tenant.", code="GestorAIDisabled")
        if settings.provider == "internal":
            return self._deterministic_plan(body.message, settings)
        from backend.config import get_ai_api_key
        from backend.services.ai.base import AIMessage
        from backend.services.ai.claude_provider import ClaudeProvider
        from backend.services.ai.openai_provider import OpenAIProvider
        key = get_ai_api_key("OPENAI_API_KEY" if settings.provider == "openai" else "ANTHROPIC_API_KEY")
        if not key:
            raise GestorAIUnavailable(f"Provedor {settings.provider} nao configurado no secret manager.", code="GestorAIProviderNotConfigured")
        provider = OpenAIProvider(model=settings.model, api_key=key) if settings.provider == "openai" else ClaudeProvider(model=settings.model, api_key=key)
        catalog = [{"name": item.name, "description": item.description, "risk_level": item.risk_level, "requires_confirmation": item.requires_confirmation, "input_schema": item.input_schema} for item in self.tool_catalog()]
        system = (settings.system_instructions or "") + "\n" + (settings.operational_rules or "")
        system += "\nPlane apenas. Nunca execute ferramentas, invente resultados, use SQL/comandos de sistema ou proponha ferramenta fora deste catalogo. Retorne somente JSON valido conforme este schema: " + json.dumps(self._strict_plan_model(), ensure_ascii=False) + "\nCatalogo: " + json.dumps(catalog, ensure_ascii=False)
        started = time.monotonic()
        result = provider.generate(system, [AIMessage(role="user", content=body.message)], settings.temperature, settings.max_tokens)
        if result.error_reason or not result.content.strip():
            raise GestorAIUnavailable("Nao foi possivel obter um plano do provedor de IA.", code="GestorAIProviderError")
        raw = result.content.strip()
        if raw.startswith("```"):
            raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.I | re.S).strip()
        try:
            parsed = GestorAIProviderPlan.model_validate(json.loads(raw))
            proposed = []
            for item in parsed.proposed_tools:
                proposed.append(self._plan_tool(item.tool_name, item.arguments, item.summary).model_copy(update={"evidence_required": item.evidence_required}))
            return GestorAIPlanOut(provider=settings.provider, model=settings.model, response_text=parsed.response_text, proposed_tools=proposed, usage=GestorAIUsage(input_tokens=result.tokens_input, output_tokens=result.tokens_output, latency_ms=result.latencia_ms or int((time.monotonic() - started) * 1000)))
        except (ValueError, KeyError, TypeError, ValidationError) as exc:
            raise GestorOperationInvalid("Resposta do provedor nao atende ao JSON estrito do Gestor.", code="GestorAIInvalidPlan") from exc

    @classmethod
    def tool_catalog(cls) -> list[GestorToolCatalogItem]:
        return [GestorToolCatalogItem(
            name=spec.name, description=spec.description, module=spec.module,
            risk_level=spec.risk_level, mutates_data=spec.mutates_data,
            requires_confirmation=spec.requires_confirmation,
            input_schema=spec.arguments_model.model_json_schema(),
            evidence_required=list(spec.evidence_required), reauth_required=spec.reauth_required,
            available=spec.available, unavailable_reason=spec.unavailable_reason,
            output_schema=spec.result_model.model_json_schema(),
        ) for spec in _tool_specs().values()]

    def assert_tool_permission(self, tool_name: str) -> None:
        spec = _tool_specs().get(tool_name.strip())
        if spec is None:
            raise GestorOperationInvalid("Ferramenta administrativa desconhecida.", code="GestorUnknownTool")
        # Direct service unit callers do not carry an HTTP actor context. The
        # protected route always supplies the trusted context and therefore
        # performs the full tenant RBAC check below.
        if self.tenant_context is None:
            return
        membership = self.db.query(TenantMembership).filter(
            TenantMembership.tenant_id == self.tenant_id,
            TenantMembership.user_id == self.admin_id,
            TenantMembership.status == "active",
        ).first()
        if membership is not None and membership.role == "owner":
            return
        admin = self.db.query(AdminUser).filter(AdminUser.id == self.admin_id).first()
        role = self.db.query(Role).filter(Role.id == admin.role_id, Role.tenant_id == self.tenant_id).first() if admin and admin.role_id else None
        if role is not None and role.name.lower() == "master":
            return
        module = self.db.query(RbacModule).filter(RbacModule.key == spec.module, RbacModule.is_active.is_(True)).first()
        permission = self.db.query(RbacPermission).filter(RbacPermission.key == spec.permission).first()
        if module is None or permission is None or role is None:
            raise DomainError("Permissao do modulo indisponivel para o Gestor.", code="GestorPermissionDenied")
        override = self.db.query(UserPermission).filter(
            UserPermission.tenant_id == self.tenant_id, UserPermission.user_id == self.admin_id,
            UserPermission.module_id == module.id, UserPermission.permission_id == permission.id,
            UserPermission.overrides_role.is_(True),
        ).first()
        allowed = bool(override.allowed) if override is not None else self.db.query(RolePermission.id).filter(
            RolePermission.tenant_id == self.tenant_id, RolePermission.role_id == role.id,
            RolePermission.module_id == module.id, RolePermission.permission_id == permission.id,
            RolePermission.allowed.is_(True),
        ).first() is not None
        if not allowed:
            raise DomainError("Usuario nao possui permissao para este modulo do Gestor.", code="GestorPermissionDenied")

    @staticmethod
    def _dump(value: Any) -> Any:
        return jsonable_encoder(value)

    @staticmethod
    def _canonical_json(value: Any) -> str:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)

    def _execute_bi_dashboard(self, args: GestorBIDashboardArguments) -> dict[str, Any]:
        from backend.services.business_intelligence_service import BusinessIntelligenceService
        return self._dump(BusinessIntelligenceService(self.db, self.tenant_id).dashboard(period=args.period))

    def _execute_inventory_overview(self, args: GestorInventoryOverviewArguments) -> dict[str, Any]:
        from backend.services.inventory_service import InventoryService
        return self._dump(InventoryService(self.db, self.tenant_id, self.tenant_context, actor_id=self.admin_id).overview())

    def _execute_finance_overview(self, args: GestorFinanceOverviewArguments) -> dict[str, Any]:
        from backend.services.finance_service import FinanceService
        return self._dump(FinanceService(self.db, self.tenant_id, self.tenant_context).overview())

    def _execute_operations_summary(self, args: GestorOperationsSummaryArguments) -> dict[str, Any]:
        from backend.services.kds_service import KdsService
        if self.tenant_context is None:
            raise DomainError("Integracao operacional indisponivel sem contexto confiavel de tenant.", code="GestorIntegrationUnavailable")
        return self._dump(KdsService(self.db, self.tenant_context).overview())

    def _execute_products_catalog(self, args: GestorProductsCatalogArguments) -> dict[str, Any]:
        from backend.models.product import Product
        from backend.services.product_catalog_service import ProductCatalogService
        catalog = ProductCatalogService(self.db, self.tenant_context)
        query = catalog._query(Product)
        if args.active_only:
            query = query.filter(Product.active.is_(True))
        rows = query.order_by(Product.name.asc()).all()
        price_field = "dine_in_price" if args.channel == "dine_in" else "delivery_price"
        return {"channel": args.channel, "products": [
            {"id": row.id, "name": row.name, "category": row.category,
             "product_type": row.product_type, "active": bool(row.active),
             "price": float(getattr(row, price_field) if getattr(row, price_field) is not None else row.price),
             "base_price": float(row.price), "delivery_price": row.delivery_price,
             "dine_in_price": row.dine_in_price}
            for row in rows
        ]}

    def _execute_crm_summary(self, args: GestorCRMSummaryArguments) -> dict[str, Any]:
        from sqlalchemy import func
        from backend.models.customer import Customer
        from backend.routes.crm import CrmCard, CrmTask
        customers = self.db.query(func.count(Customer.id)).filter(Customer.tenant_id == self.tenant_id).scalar() or 0
        pending_tasks = self.db.query(func.count(CrmTask.id)).filter(
            CrmTask.tenant_id == self.tenant_id, CrmTask.status == "pending",
        ).scalar() or 0
        active_cards = self.db.query(func.count(CrmCard.id)).filter(
            CrmCard.tenant_id == self.tenant_id, CrmCard.archived.is_(False),
        ).scalar() or 0
        return {"total_customers": int(customers), "pending_tasks": int(pending_tasks), "active_cards": int(active_cards)}

    def _execute_fiscal_overview(self, args: GestorFiscalOverviewArguments) -> dict[str, Any]:
        from backend.services.fiscal_service import FiscalService
        if self.tenant_context is None:
            raise DomainError("Integracao fiscal indisponivel sem contexto confiavel de tenant.", code="GestorIntegrationUnavailable")
        return self._dump(FiscalService(self.db, self.tenant_id, self.tenant_context).overview())

    def _execute_logistics_summary(self, args: GestorLogisticsSummaryArguments) -> dict[str, Any]:
        from backend.services.kds_service import KdsService
        if self.tenant_context is None:
            raise DomainError("Integracao logistica indisponivel sem contexto confiavel de tenant.", code="GestorIntegrationUnavailable")
        return self._dump(KdsService(self.db, self.tenant_context).overview())

    def _execute_products_update_price(self, args: GestorProductUpdatePriceArguments) -> dict[str, Any]:
        from backend.schemas.product import ProductUpdate
        from backend.services.product_catalog_service import ProductCatalogService
        values = {"price": args.price}
        if args.delivery_price is not None:
            values["delivery_price"] = args.delivery_price
        if args.dine_in_price is not None:
            values["dine_in_price"] = args.dine_in_price
        row = ProductCatalogService(self.db, self.tenant_context).update(args.product_id, ProductUpdate(**values))
        return {"id": row.id, "name": row.name, "price": row.price,
                "delivery_price": row.delivery_price, "dine_in_price": row.dine_in_price}

    def _execute_finance_create_expense(self, args: GestorFinanceCreateExpenseArguments) -> dict[str, Any]:
        from backend.schemas.finance import FinanceTransactionIn
        from backend.services.finance_service import FinanceService
        payload = FinanceTransactionIn(
            account_id=args.account_id, category_id=args.category_id, counterparty_id=args.counterparty_id,
            description=args.description, amount=args.amount, competence_date=date.fromisoformat(args.competence_date),
            due_date=date.fromisoformat(args.due_date) if args.due_date else None, notes=args.notes,
            entry_type="expense", status="pending", origin_type="gestor",
        )
        return self._dump(FinanceService(self.db, self.tenant_id, self.tenant_context).create_transaction(payload, admin_id=self.admin_id))

    def _execute_inventory_manual_entry(self, args: GestorInventoryManualEntryArguments) -> dict[str, Any]:
        from backend.schemas.inventory import InventoryManualEntryIn
        from backend.services.inventory_service import InventoryService
        payload = InventoryManualEntryIn(item_id=args.item_id, location_id=args.location_id,
            movement_type=args.movement_type, quantity=Decimal(str(args.quantity)),
            unit_cost=Decimal(str(args.unit_cost)), reason=args.reason, notes=args.notes)
        return self._dump(InventoryService(self.db, self.tenant_id, self.tenant_context, actor_id=self.admin_id).create_manual_entry(payload))

    def _execute_order_status_update(self, args: GestorOrderStatusUpdateArguments) -> dict[str, Any]:
        from backend.services.order_service import OrderService
        order = OrderService(self.db, self.tenant_context).change_status(args.order_id, args.status, changed_by=args.changed_by)
        return {"id": order.id, "status": getattr(order.status, "value", order.status)}

    def _execute_crm_create_task(self, args: GestorCRMCreateTaskArguments) -> dict[str, Any]:
        raise DomainError("Integracao CRM indisponivel: nao existe service de dominio canonico para criar tarefas.", code="GestorIntegrationUnavailable")

    def _execute_inventory_approve_receipt(self, args: GestorInventoryApproveReceiptArguments) -> dict[str, Any]:
        from backend.services.inventory_receipt_service import InventoryReceiptService
        return self._dump(InventoryReceiptService(self.db, self.tenant_id, self.admin_id).approve(args.document_id))

    def _execute_whatsapp_send_message(self, args: GestorWhatsAppSendMessageArguments) -> dict[str, Any]:
        """Prevent the generic executor from bypassing the durable outbox."""
        raise GestorOperationInvalid(
            "Envio Meta deve passar pelo endpoint de outbox assincrono.",
            code="GestorWhatsAppOutboxRequired",
        )

    def _whatsapp_send_policy(
        self,
        args: GestorWhatsAppSendMessageArguments,
        recipient_phone: str,
    ) -> dict[str, Any]:
        latest = self.db.query(GestorWhatsAppMessage).filter(
            GestorWhatsAppMessage.tenant_id == self.tenant_id,
            GestorWhatsAppMessage.from_phone == recipient_phone,
        ).order_by(GestorWhatsAppMessage.created_at.desc()).first()
        now = datetime.now(timezone.utc)
        latest_at = latest.created_at if latest else None
        if latest_at and latest_at.tzinfo is None:
            latest_at = latest_at.replace(tzinfo=timezone.utc)
        window_open = bool(latest_at and now - latest_at <= timedelta(hours=24))
        if args.message_type == "text" and not window_open:
            raise GestorWhatsAppPolicyDenied(
                "Mensagem livre bloqueada: fora da janela de atendimento de 24 horas da Meta. Use um template aprovado.",
                code="GestorWhatsAppWindowClosed",
            )
        if args.message_type == "text" and not (args.body or "").strip():
            raise GestorWhatsAppPolicyDenied("Mensagem de texto vazia.", code="GestorWhatsAppBodyRequired")
        if args.message_type == "template":
            if not args.template_name or not re.fullmatch(r"[a-z0-9_]+", args.template_name):
                raise GestorWhatsAppPolicyDenied(
                    "Template Meta deve usar o nome aprovado, em minusculas, numeros e underscore.",
                    code="GestorWhatsAppTemplateInvalid",
                )
        return {
            "channel": "meta_cloud_api",
            "window_open": window_open,
            "window_rule": "free_form_allowed_for_24h_after_inbound;_otherwise_approved_template_required",
            "latest_inbound_at": latest_at.isoformat() if latest_at else None,
            "requires_approved_template": not window_open,
            "message_mode": "free_form" if args.message_type == "text" else "template",
        }

    def _channel_for_send(self) -> GestorWhatsAppChannel:
        channel = self.get_whatsapp_channel()
        if channel is None or not channel.enabled:
            raise GestorWhatsAppNotConfigured("Canal Gestor Meta nao esta ativo.", code="GestorWhatsAppChannelDisabled")
        if not self.resolve_gestor_meta_secret(channel.app_secret_ref):
            raise GestorWhatsAppNotConfigured("App secret Meta nao resolvivel no secret manager.", code="GestorWhatsAppSecretUnavailable")
        if not self.resolve_gestor_meta_access_token(channel.access_token_ref):
            raise GestorWhatsAppNotConfigured(
                "Token de acesso Meta nao resolvivel no secret manager.", code="GestorWhatsAppAccessTokenUnavailable"
            )
        return channel

    def enqueue_whatsapp_message(self, operation_id: str) -> tuple[GestorWhatsAppOutbox, bool, dict[str, Any]]:
        operation = self.db.query(GestorOperation).filter(
            GestorOperation.id == str(operation_id), GestorOperation.tenant_id == self.tenant_id,
        ).first()
        if operation is None:
            raise GestorOperationNotFound("Operacao do Gestor nao encontrada.", code="GestorOperationNotFound")
        if operation.requested_by_admin_id and operation.requested_by_admin_id != self.admin_id:
            raise DomainError("Operacao pertence a outro administrador do tenant.", code="GestorOperationActorMismatch")
        self.assert_tool_permission("gestor.whatsapp.send_message")
        if operation.tool_name != "gestor.whatsapp.send_message":
            raise GestorOperationInvalid("Operacao nao e de envio Meta do Gestor.", code="GestorToolMismatch")
        if operation.status not in {"READY_TO_EXECUTE", "QUEUED"}:
            existing = self.db.query(GestorWhatsAppOutbox).filter(
                GestorWhatsAppOutbox.tenant_id == self.tenant_id,
                GestorWhatsAppOutbox.operation_id == operation.id,
            ).first()
            if existing is not None:
                return existing, True, (operation.preview_json or {}).get("policy") or {}
            raise GestorOperationInvalid("Operacao precisa estar confirmada antes do enqueue.", code="GestorOperationNotConfirmed")

        try:
            args = GestorWhatsAppSendMessageArguments.model_validate(operation.arguments_json or {})
        except ValidationError as exc:
            raise GestorOperationInvalid("Argumentos de envio Meta invalidos.", code="GestorWhatsAppArgumentsInvalid") from exc
        recipient_phone = self.normalize_phone(args.to_phone)
        channel = self._channel_for_send()
        policy = self._whatsapp_send_policy(args, recipient_phone)
        existing = self.db.query(GestorWhatsAppOutbox).filter(
            GestorWhatsAppOutbox.tenant_id == self.tenant_id,
            GestorWhatsAppOutbox.operation_id == operation.id,
        ).first()
        if existing is not None:
            return existing, True, policy
        now = datetime.now(timezone.utc)
        item = GestorWhatsAppOutbox(
            tenant_id=self.tenant_id, channel_id=channel.id, operation_id=operation.id,
            recipient_phone=recipient_phone, message_type=args.message_type,
            body=args.body.strip() if args.body else None, template_name=args.template_name,
            template_language=args.template_language, template_variables=list(args.template_variables),
            idempotency_key=f"gestor-meta:{operation.id}", status="pending", attempts=0,
            max_attempts=3, next_attempt_at=now, created_at=now, updated_at=now,
        )
        self.db.add(item)
        operation.status = "QUEUED"
        operation.preview_json = {**(operation.preview_json or {}), "policy": policy, "outbox": "queued"}
        operation.error = None
        self.db.flush()
        return item, False, policy

    @staticmethod
    def _safe_meta_error(response: Any, token: str | None = None) -> str:
        try:
            data = response.json()
        except Exception:
            data = {}
        error = data.get("error") if isinstance(data, dict) else None
        message = error.get("message") if isinstance(error, dict) else None
        value = str(message or getattr(response, "text", "Falha Meta") or "Falha Meta")
        if token:
            value = value.replace(token, "[redacted]")
        return value[:1000]

    def _meta_payload(self, item: GestorWhatsAppOutbox) -> dict[str, Any]:
        payload: dict[str, Any] = {"messaging_product": "whatsapp", "to": item.recipient_phone, "type": item.message_type}
        if item.message_type == "text":
            payload["text"] = {"preview_url": False, "body": item.body or ""}
        else:
            template: dict[str, Any] = {
                "name": item.template_name,
                "language": {"code": item.template_language or "pt_BR"},
            }
            if item.template_variables:
                template["components"] = [{
                    "type": "body",
                    "parameters": [{"type": "text", "text": str(value)} for value in item.template_variables],
                }]
            payload["template"] = template
        return payload

    def _fail_whatsapp_outbox(self, item: GestorWhatsAppOutbox, error: str) -> str:
        now = datetime.now(timezone.utc)
        item.error = error[:1000]
        item.locked_at = None
        item.updated_at = now
        if item.attempts >= item.max_attempts:
            item.status = "dead"
            item.next_attempt_at = None
            result = "dead"
            operation_status = "FAILED"
        else:
            item.status = "failed"
            item.next_attempt_at = now + timedelta(minutes=min(30, 2 ** max(item.attempts - 1, 0)))
            result = "failed"
            operation_status = "QUEUED"
        operation = self.db.query(GestorOperation).filter(
            GestorOperation.id == item.operation_id, GestorOperation.tenant_id == self.tenant_id,
        ).first()
        if operation:
            operation.status = operation_status
            operation.error = item.error
            operation.updated_at = now
        self.db.flush()
        return result

    def _process_whatsapp_item(self, item: GestorWhatsAppOutbox) -> str:
        channel = self.db.query(GestorWhatsAppChannel).filter(
            GestorWhatsAppChannel.id == item.channel_id, GestorWhatsAppChannel.tenant_id == self.tenant_id,
        ).first()
        token = self.resolve_gestor_meta_access_token(channel.access_token_ref if channel else None)
        if channel is None or not channel.enabled or not token:
            return self._fail_whatsapp_outbox(item, "Credencial externa Meta indisponivel para processamento.")
        now = datetime.now(timezone.utc)
        item.status = "processing"
        item.locked_at = now
        item.attempts = (item.attempts or 0) + 1
        item.updated_at = now
        self.db.flush()
        try:
            response = requests.post(
                f"https://graph.facebook.com/v19.0/{channel.phone_number_id}/messages",
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                json=self._meta_payload(item), timeout=15,
            )
            try:
                data = response.json()
            except Exception:
                data = {}
            messages = data.get("messages") if isinstance(data, dict) else None
            provider_id = messages[0].get("id") if isinstance(messages, list) and messages and isinstance(messages[0], dict) else None
            if 200 <= int(getattr(response, "status_code", 0)) < 300 and provider_id:
                now = datetime.now(timezone.utc)
                item.status = "sent"
                item.provider_message_id = str(provider_id)
                item.error = None
                item.locked_at = None
                item.sent_at = now
                item.updated_at = now
                operation = self.db.query(GestorOperation).filter(
                    GestorOperation.id == item.operation_id, GestorOperation.tenant_id == self.tenant_id,
                ).first()
                if operation:
                    operation.status = "EXECUTED"
                    operation.executed_at = now
                    operation.error = None
                self.db.flush()
                return "sent"
            return self._fail_whatsapp_outbox(item, self._safe_meta_error(response, token))
        except Exception:
            return self._fail_whatsapp_outbox(item, "Falha de comunicacao com a API Meta.")

    def process_whatsapp_outbox(self, limit: int = 20) -> dict[str, int]:
        now = datetime.now(timezone.utc)
        rows = self.db.query(GestorWhatsAppOutbox).filter(
            GestorWhatsAppOutbox.tenant_id == self.tenant_id,
            GestorWhatsAppOutbox.status.in_(["pending", "failed"]),
            (GestorWhatsAppOutbox.next_attempt_at.is_(None) | (GestorWhatsAppOutbox.next_attempt_at <= now)),
            or_(
                GestorWhatsAppOutbox.locked_at.is_(None),
                GestorWhatsAppOutbox.locked_at <= now - timedelta(minutes=15),
            ),
        ).order_by(GestorWhatsAppOutbox.created_at.asc()).with_for_update(skip_locked=True).limit(limit).all()
        result = {"processed": 0, "sent": 0, "failed": 0, "deferred": 0, "dead": 0}
        for item in rows:
            outcome = self._process_whatsapp_item(item)
            result["processed"] += 1
            result[outcome] = result.get(outcome, 0) + 1
        return result

    def list_whatsapp_outbox(self, status: str | None = None, limit: int = 100) -> list[GestorWhatsAppOutbox]:
        query = self.db.query(GestorWhatsAppOutbox).filter(GestorWhatsAppOutbox.tenant_id == self.tenant_id)
        if status:
            query = query.filter(GestorWhatsAppOutbox.status == status)
        return query.order_by(GestorWhatsAppOutbox.created_at.desc()).limit(limit).all()

    def retry_whatsapp_outbox(self, outbox_id: str) -> GestorWhatsAppOutbox:
        item = self.db.query(GestorWhatsAppOutbox).filter(
            GestorWhatsAppOutbox.id == outbox_id, GestorWhatsAppOutbox.tenant_id == self.tenant_id,
        ).first()
        if item is None:
            raise GestorOperationNotFound("Item da fila Gestor nao encontrado.", code="GestorWhatsAppOutboxNotFound")
        if item.status == "sent":
            raise GestorOperationInvalid("Mensagem ja enviada pela Meta.", code="GestorWhatsAppOutboxAlreadySent")
        item.status = "pending"
        item.attempts = 0
        item.error = None
        item.locked_at = None
        item.next_attempt_at = datetime.now(timezone.utc)
        operation = self.db.query(GestorOperation).filter(
            GestorOperation.id == item.operation_id, GestorOperation.tenant_id == self.tenant_id,
        ).first()
        if operation and operation.status == "FAILED":
            operation.status = "QUEUED"
            operation.error = None
        self.db.flush()
        return item

    @staticmethod
    def serialize_whatsapp_outbox(item: GestorWhatsAppOutbox) -> dict[str, Any]:
        return {
            "id": item.id, "operation_id": item.operation_id, "recipient_phone": item.recipient_phone,
            "message_type": item.message_type, "body": item.body, "template_name": item.template_name,
            "template_language": item.template_language, "template_variables": item.template_variables or [],
            "idempotency_key": item.idempotency_key, "status": item.status, "attempts": item.attempts,
            "max_attempts": item.max_attempts, "provider_message_id": item.provider_message_id,
            "error": item.error, "next_attempt_at": item.next_attempt_at, "locked_at": item.locked_at,
            "sent_at": item.sent_at, "created_at": item.created_at, "updated_at": item.updated_at,
        }

    def _validate_tool_arguments(self, spec: _ToolSpec, arguments: dict[str, Any]):
        try:
            return spec.arguments_model.model_validate(arguments)
        except ValidationError as exc:
            raise GestorOperationInvalid(
                "Argumentos invalidos para a ferramenta administrativa.", code="GestorToolArgumentsInvalid"
            ) from exc

    def _confirmed_write_operation(self, body: GestorToolExecuteIn, spec: _ToolSpec):
        if not spec.available:
            raise DomainError(spec.unavailable_reason or "Integracao indisponivel.", code="GestorIntegrationUnavailable")
        if spec.reauth_required and not body.reauthenticated:
            raise GestorOperationInvalid("Esta operacao exige reautenticacao explicita.", code="GestorReauthenticationRequired")
        if not body.operation_id:
            raise GestorOperationInvalid(
                "Operacao de escrita exige uma confirmacao previa.", code="GestorConfirmationRequired"
            )
        operation = self.db.query(GestorOperation).filter(
            GestorOperation.id == body.operation_id,
            GestorOperation.tenant_id == self.tenant_id,
        ).first()
        if operation is None:
            raise GestorOperationNotFound("Operacao do Gestor nao encontrada.", code="GestorOperationNotFound")
        if operation.tool_name != spec.name or body.tool_name.strip() != operation.tool_name:
            raise GestorOperationInvalid("Ferramenta divergente da operacao confirmada.", code="GestorToolMismatch")
        args = self._validate_tool_arguments(spec, body.arguments)
        normalized_args = args.model_dump(mode="json")
        if self._canonical_json(operation.arguments_json) != self._canonical_json(normalized_args):
            raise GestorOperationInvalid("Argumentos divergentes da operacao confirmada.", code="GestorArgumentsMismatch")
        if operation.status == "EXECUTED":
            return operation, self._stored_result(operation)
        if operation.status != "READY_TO_EXECUTE":
            raise GestorOperationInvalid(
                "Operacao precisa estar confirmada antes da execucao.", code="GestorOperationNotConfirmed"
            )
        try:
            result = spec.handler(self, args)
            operation.preview_json = {**(operation.preview_json or {}), "_execution_result": result}
            operation.status = "EXECUTED"
            operation.executed_at = datetime.now(timezone.utc)
            operation.error = None
            self.db.flush()
            return operation, result
        except Exception as exc:
            operation.status = "FAILED"
            operation.error = f"{type(exc).__name__}: {exc}"
            operation.executed_at = None
            self.db.flush()
            raise

    def execute_tool(self, body: GestorToolExecuteIn) -> tuple[GestorOperation, dict[str, Any] | None]:
        spec = _tool_specs().get(body.tool_name)
        if spec is None:
            raise GestorOperationInvalid("Ferramenta administrativa desconhecida.", code="GestorUnknownTool")
        self.assert_tool_permission(body.tool_name)
        if spec.mutates_data:
            return self._confirmed_write_operation(body, spec)
        phone = self.normalize_phone(body.phone)
        key = body.idempotency_key or f"gestor-read-{uuid4()}"
        try:
            args = spec.arguments_model.model_validate(body.arguments)
        except ValidationError as exc:
            raise GestorOperationInvalid(
                "Argumentos invalidos para a ferramenta administrativa.", code="GestorToolArgumentsInvalid"
            ) from exc
        normalized_args = args.model_dump(mode="json")
        existing = self.db.query(GestorOperation).filter(
            GestorOperation.tenant_id == self.tenant_id,
            GestorOperation.idempotency_key == key,
        ).first()
        if existing is not None:
            same = (
                existing.tool_name == body.tool_name.strip()
                and existing.channel == body.channel.strip()
                and existing.phone == phone
                and self._canonical_json(existing.arguments_json) == self._canonical_json(normalized_args)
            )
            if not same:
                raise GestorOperationInvalid("Replay divergente para a mesma chave de idempotencia.", code="GestorIdempotencyConflict")
            return existing, self._stored_result(existing)

        operation = GestorOperation(
            tenant_id=self.tenant_id, requested_by_admin_id=self.admin_id,
            channel=body.channel.strip(), phone=phone, tool_name=body.tool_name.strip(),
            risk_level="low", status="EXECUTED", arguments_json=normalized_args,
            preview_json={"read_only": True, "tool": spec.name}, idempotency_key=key,
            executed_at=datetime.now(timezone.utc),
        )
        self.db.add(operation)
        try:
            result = spec.handler(self, args)
            operation.preview_json = {
                "read_only": True, "tool": spec.name, "_execution_result": result,
            }
            operation.status = "EXECUTED"
            operation.executed_at = datetime.now(timezone.utc)
        except Exception as exc:
            operation.status = "FAILED"
            operation.error = f"{type(exc).__name__}: {exc}"
            result = None
        self.db.flush()
        return operation, result

    @staticmethod
    def _stored_result(operation: GestorOperation) -> dict[str, Any] | None:
        value = (operation.preview_json or {}).get("_execution_result")
        return value if isinstance(value, dict) else None

    @staticmethod
    def normalize_phone(phone: str) -> str:
        value = re.sub(r"\D", "", phone or "")
        if not 8 <= len(value) <= 15:
            raise DomainError("Telefone invalido para contato autorizado.", code="InvalidPhone")
        return value

    def _admin_in_tenant(self, admin_user_id: str) -> None:
        exists = self.db.query(TenantMembership.id).filter(
            TenantMembership.tenant_id == self.tenant_id,
            TenantMembership.user_id == admin_user_id,
            TenantMembership.status == "active",
        ).first()
        if exists is None:
            raise DomainError("Administrador nao possui membership ativa neste tenant.", code="AdminTenantMismatch")

    def list_contacts(self) -> list[GestorAuthorizedContact]:
        return self.db.query(GestorAuthorizedContact).filter(
            GestorAuthorizedContact.tenant_id == self.tenant_id,
        ).order_by(GestorAuthorizedContact.created_at.desc()).all()

    def create_contact(self, body: GestorContactCreate) -> GestorAuthorizedContact:
        admin_id = str(body.admin_user_id)
        self._admin_in_tenant(admin_id)
        phone = self.normalize_phone(body.phone)
        if self.db.query(GestorAuthorizedContact.id).filter(
            GestorAuthorizedContact.tenant_id == self.tenant_id,
            GestorAuthorizedContact.phone_normalized == phone,
        ).first():
            raise GestorOperationInvalid("Telefone ja autorizado neste tenant.", code="GestorContactAlreadyExists")
        item = GestorAuthorizedContact(
            tenant_id=self.tenant_id, admin_user_id=admin_id, phone_normalized=phone,
            display_name=body.display_name.strip(), role=body.role.strip(),
            active=body.active, requires_reauth=body.requires_reauth,
        )
        self.db.add(item)
        try:
            self.db.flush()
        except IntegrityError as exc:
            self.db.rollback()
            raise GestorOperationInvalid("Contato autorizado ja existe.", code="GestorContactAlreadyExists") from exc
        return item

    def update_contact(self, contact_id: str, body: GestorContactUpdate) -> GestorAuthorizedContact:
        item = self.db.query(GestorAuthorizedContact).filter(
            GestorAuthorizedContact.id == contact_id,
            GestorAuthorizedContact.tenant_id == self.tenant_id,
        ).first()
        if item is None:
            raise GestorContactNotFound("Contato autorizado nao encontrado.", code="GestorContactNotFound")
        changes = body.model_dump(exclude_unset=True)
        if "phone" in changes:
            changes["phone_normalized"] = self.normalize_phone(changes.pop("phone"))
            duplicate = self.db.query(GestorAuthorizedContact.id).filter(
                GestorAuthorizedContact.tenant_id == self.tenant_id,
                GestorAuthorizedContact.phone_normalized == changes["phone_normalized"],
                GestorAuthorizedContact.id != item.id,
            ).first()
            if duplicate:
                raise GestorOperationInvalid("Telefone ja autorizado neste tenant.", code="GestorContactAlreadyExists")
        for key, value in changes.items():
            if isinstance(value, str):
                value = value.strip()
            setattr(item, key, value)
        self.db.flush()
        return item

    @staticmethod
    def _hash_token(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    def create_operation(self, body: GestorOperationPreviewIn) -> tuple[GestorOperation, str]:
        spec = _tool_specs().get(body.tool_name.strip())
        if spec is not None and not spec.available:
            raise GestorOperationInvalid(
                spec.unavailable_reason or "Integracao indisponivel.", code="GestorIntegrationUnavailable",
            )
        if body.risk_level.strip() in {"medium", "high"}:
            if spec is None or spec.risk_level != body.risk_level.strip() or not spec.requires_confirmation:
                raise GestorOperationInvalid(
                    "Nivel de risco divergente ou ferramenta nao autorizada para preview.", code="GestorToolNotAllowed"
                )
            summary = body.preview.get("summary")
            if not isinstance(summary, str) or not summary.strip():
                raise GestorOperationInvalid(
                    "Preview de escrita exige um resumo da operacao.", code="GestorPreviewSummaryRequired"
                )
            if spec.reauth_required and not body.reauthenticated:
                raise GestorOperationInvalid("Esta operacao exige reautenticacao explicita.", code="GestorReauthenticationRequired")
        if spec is not None:
            try:
                normalized = spec.arguments_model.model_validate(body.arguments).model_dump(mode="json")
            except ValidationError as exc:
                raise GestorOperationInvalid("Argumentos invalidos para a ferramenta administrativa.", code="GestorToolArgumentsInvalid") from exc
        else:
            normalized = body.arguments
        idempotency_key = body.idempotency_key or f"gestor-preview-{uuid4()}"
        existing = self.db.query(GestorOperation).filter(
            GestorOperation.tenant_id == self.tenant_id,
            GestorOperation.idempotency_key == idempotency_key,
        ).first()
        if existing is not None:
            raise GestorOperationInvalid("Idempotency-Key ja utilizado neste tenant.", code="GestorIdempotencyConflict")
        phone = self.normalize_phone(body.phone)
        token = secrets.token_urlsafe(32)
        operation = GestorOperation(
            tenant_id=self.tenant_id, requested_by_admin_id=self.admin_id,
            channel=body.channel.strip(), phone=phone, tool_name=body.tool_name.strip(),
            risk_level=body.risk_level.strip(), status="PENDING_CONFIRMATION",
            arguments_json=normalized, preview_json=body.preview,
            idempotency_key=idempotency_key, confirmation_token_hash=self._hash_token(token),
            confirmation_expires_at=datetime.now(timezone.utc) + timedelta(seconds=body.confirmation_ttl_seconds),
        )
        self.db.add(operation)
        try:
            self.db.flush()
        except IntegrityError as exc:
            self.db.rollback()
            raise GestorOperationInvalid("Idempotency-Key ja utilizado neste tenant.", code="GestorIdempotencyConflict") from exc
        return operation, token

    def confirm_operation(self, operation_id: str, token: str) -> GestorOperation:
        operation = self.db.query(GestorOperation).filter(
            GestorOperation.id == operation_id,
            GestorOperation.tenant_id == self.tenant_id,
        ).first()
        if operation is None:
            raise GestorOperationNotFound("Operacao do Gestor nao encontrada.", code="GestorOperationNotFound")
        now = datetime.now(timezone.utc)
        if operation.status not in {"PENDING_CONFIRMATION", "PLANNED"}:
            raise GestorOperationInvalid("Operacao nao esta aguardando confirmacao.", code="GestorOperationStateInvalid")
        if not operation.confirmation_expires_at or operation.confirmation_expires_at <= now:
            operation.status = "EXPIRED"
            operation.confirmation_token_hash = None
            self.db.flush()
            raise GestorOperationInvalid("Token de confirmacao expirado.", code="GestorConfirmationExpired")
        if not operation.confirmation_token_hash or not hmac.compare_digest(
            operation.confirmation_token_hash, self._hash_token(token)
        ):
            raise GestorOperationInvalid("Token de confirmacao invalido.", code="GestorConfirmationInvalid")
        operation.status = "READY_TO_EXECUTE"
        operation.confirmation_token_hash = None
        operation.updated_at = now
        self.db.flush()
        return operation

    def expire_operations(self) -> int:
        now = datetime.now(timezone.utc)
        count = self.db.query(GestorOperation).filter(
            GestorOperation.tenant_id == self.tenant_id,
            GestorOperation.status == "PENDING_CONFIRMATION",
            GestorOperation.confirmation_expires_at <= now,
        ).update({"status": "EXPIRED", "confirmation_token_hash": None}, synchronize_session=False)
        self.db.flush()
        return count

    def list_operations(self, limit: int = 100) -> list[GestorOperation]:
        self.expire_operations()
        return self.db.query(GestorOperation).filter(
            GestorOperation.tenant_id == self.tenant_id,
        ).order_by(GestorOperation.created_at.desc()).limit(limit).all()

    # ---- Multimodal intake -------------------------------------------------
    _MM_MIME_TYPES = {
        "text": {"text/plain", "text/markdown", "application/json"},
        "image": {"image/jpeg", "image/png", "image/webp", "image/gif"},
        "audio": {"audio/ogg", "audio/opus", "audio/mpeg", "audio/mp3", "audio/mp4", "audio/aac", "audio/webm"},
        "document": {"application/pdf", "application/xml", "text/xml", "image/jpeg", "image/png", "image/webp"},
    }
    _MM_DEFAULT_MIME = {
        "text": "text/plain", "image": "image/jpeg", "audio": "audio/ogg", "document": "application/pdf",
    }
    _MM_EXTENSIONS = {
        "text/plain": "txt", "text/markdown": "md", "application/json": "json",
        "image/jpeg": "jpg", "image/png": "png", "image/webp": "webp", "image/gif": "gif",
        "audio/ogg": "ogg", "audio/opus": "opus", "audio/mpeg": "mp3", "audio/mp3": "mp3",
        "audio/mp4": "m4a", "audio/aac": "aac", "audio/webm": "webm",
        "application/pdf": "pdf", "application/xml": "xml", "text/xml": "xml",
    }
    _MM_MAX_BYTES = {"text": 200_000, "image": 10 * 1024 * 1024, "audio": 20 * 1024 * 1024, "document": 15 * 1024 * 1024}
    _MM_SAFE_METADATA = {"provider", "provider_message_id", "duration_ms", "language", "alt_text", "source", "page_count"}

    @classmethod
    def _sanitize_multimodal_metadata(cls, value: dict[str, Any] | None) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, item in (value or {}).items():
            key = str(key).strip().lower()
            if key not in cls._MM_SAFE_METADATA or any(word in key for word in ("token", "secret", "password", "key")):
                continue
            if isinstance(item, (str, int, float, bool)) or item is None:
                result[key] = str(item)[:500] if isinstance(item, str) else item
        return result

    @staticmethod
    def _safe_multimodal_error(value: Any) -> str:
        return str(value or "Falha no processamento multimodal.").replace("\r", " ").replace("\n", " ")[:500]

    def _multimodal_audit(self, artifact: GestorMultimodalArtifact, event: str, status: str, details: dict[str, Any] | None = None) -> None:
        self.db.add(GestorMultimodalAudit(
            id=str(uuid4()), tenant_id=self.tenant_id, artifact_id=artifact.id,
            actor_admin_id=self.admin_id, event=event, status=status,
            details_json=self._sanitize_multimodal_metadata(details),
        ))

    def _multimodal_storage(self, data: bytes, mime_type: str, filename: str | None) -> tuple[str, str, TenantUploadAsset | None]:
        context = self.tenant_context or trusted_process_context(self.tenant_id, source=TenantSource.JOB)
        extension = self._MM_EXTENSIONS[mime_type]
        supplied = PurePosixPath((filename or "").replace("\\", "/")).name
        stem = re.sub(r"[^A-Za-z0-9._-]", "-", supplied.rsplit(".", 1)[0] if "." in supplied else supplied).strip(".-")[:80]
        storage_name = f"gestor-mm-{uuid4().hex}{('-' + stem) if stem else ''}.{extension}"
        path = tenant_upload_path(PROJECT_ROOT / "uploads", context, storage_name)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        storage_key = TenantUploadService.storage_key(self.tenant_id, storage_name)
        admin = self.db.query(AdminUser).filter(AdminUser.id == self.admin_id).first()
        asset = None
        if admin is not None:
            asset = TenantUploadService(self.db).create_asset(
                context=context, admin=admin, filename=storage_name,
                original_filename=supplied or storage_name, content_type=mime_type,
                byte_size=len(data), visibility="private",
            )
        return storage_key, f"/uploads/{storage_key}", asset

    def _decode_multimodal_input(self, body: GestorMultimodalIn) -> tuple[bytes, str, str | None]:
        media_type = body.media_type
        mime_type = (body.mime_type or self._MM_DEFAULT_MIME[media_type]).split(";", 1)[0].strip().lower()
        if mime_type not in self._MM_MIME_TYPES[media_type]:
            raise GestorMultimodalInvalid("MIME nao permitido para o tipo multimodal informado.", code="GestorMultimodalMimeDenied")
        if media_type == "text":
            if body.text is not None and body.content_base64 is not None:
                raise GestorMultimodalInvalid("Informe texto ou content_base64, nao ambos.", code="GestorMultimodalInputConflict")
            if body.text is not None:
                data = body.text.encode("utf-8")
                text_value = body.text
            elif body.content_base64:
                try:
                    data = base64.b64decode(body.content_base64, validate=True)
                    text_value = data.decode("utf-8")
                except (ValueError, UnicodeDecodeError, binascii.Error) as exc:
                    raise GestorMultimodalInvalid("Conteudo textual base64 invalido.", code="GestorMultimodalContentInvalid") from exc
            else:
                raise GestorMultimodalInvalid("Texto ou content_base64 e obrigatorio.", code="GestorMultimodalContentRequired")
        else:
            if not body.content_base64:
                raise GestorMultimodalInvalid("content_base64 e obrigatorio para midia binaria.", code="GestorMultimodalContentRequired")
            try:
                data = base64.b64decode(body.content_base64, validate=True)
            except (ValueError, binascii.Error) as exc:
                raise GestorMultimodalInvalid("Conteudo base64 invalido.", code="GestorMultimodalContentInvalid") from exc
            text_value = None
        if not data:
            raise GestorMultimodalInvalid("Conteudo multimodal vazio.", code="GestorMultimodalContentEmpty")
        if len(data) > self._MM_MAX_BYTES[media_type]:
            raise GestorMultimodalInvalid("Conteudo multimodal excede o limite permitido.", code="GestorMultimodalSizeExceeded")
        return data, mime_type, text_value

    def _process_multimodal_audio(self, artifact: GestorMultimodalArtifact, media_url: str) -> None:
        # Keep the legacy Agente model graph lazy: Gestor read-only operations
        # must not force unrelated WhatsApp ORM relationships to configure.
        from backend.models.agente_whatsapp import AgenteWhatsAppMessage, AgenteWhatsAppSession
        from backend.services.agente_whatsapp_audio_service import AgenteWhatsAppAudioService

        session_id = f"gestor-mm-{hashlib.sha256(artifact.id.encode()).hexdigest()[:28]}"
        session = self.db.query(AgenteWhatsAppSession).filter(
            AgenteWhatsAppSession.id == session_id, AgenteWhatsAppSession.tenant_id == self.tenant_id,
        ).first()
        if session is None:
            session = AgenteWhatsAppSession(
                id=session_id, tenant_id=self.tenant_id, phone="gestor-multimodal",
                provider="official", origin="gestor", status="open", ai_enabled=False,
            )
            self.db.add(session)
            self.db.flush()
        message = AgenteWhatsAppMessage(
            id=f"gestor-mm-msg-{artifact.id}", tenant_id=self.tenant_id, session_id=session.id,
            provider="official", direction="inbound", sender_type="user", message_type="audio",
            media_url=media_url, media_storage_key=media_url, media_mime_type=artifact.mime_type,
            media_size_bytes=artifact.size_bytes, provider_message_id=artifact.source_message_id or artifact.id,
            processing_status="recorded", idempotency_key=f"gestor-mm-audio:{artifact.id}", raw_payload_json="{}",
        )
        self.db.add(message)
        self.db.flush()
        audio_context = self.tenant_context or trusted_process_context(self.tenant_id, source=TenantSource.JOB)
        result = AgenteWhatsAppAudioService(self.db, audio_context).transcribe_message(message.id)
        quality = result.get("transcription_quality") if isinstance(result, dict) else {}
        quality = quality if isinstance(quality, dict) else {}
        low_confidence = bool(result.get("transcription_status") == "low_confidence" or result.get("low_confidence") or quality.get("low_confidence"))
        text_value = str(result.get("transcription_text") or "").strip()
        if result.get("transcription_status") == "failed" or result.get("transcription_error"):
            artifact.status = "failed"
            artifact.review_required = True
            artifact.review_reason = "Transcricao indisponivel; revisao manual necessaria."
            artifact.error = self._safe_multimodal_error(result.get("transcription_error"))
        else:
            artifact.status = "review_required" if low_confidence else "processed"
            artifact.review_required = low_confidence
            artifact.review_reason = "Baixa confianca na transcricao; confirme ou corrija o texto." if low_confidence else None
            artifact.extracted_text = text_value or None
            artifact.processor = "AgenteWhatsAppAudioService"
            artifact.metadata_json = {**(artifact.metadata_json or {}), "canonical_message_id": message.id, "quality": quality}
            artifact.confidence = 0.2 if low_confidence else 1.0

    def _process_multimodal_document(self, artifact: GestorMultimodalArtifact, path: Path) -> None:
        # XML parsing is pure and canonical; approval, stock and finance writes
        # remain explicit ERP operations and are never triggered here.
        details: dict[str, Any] = {"automatic_mutation": False, "review_required": True}
        if artifact.mime_type in {"application/xml", "text/xml"}:
            try:
                identity = parse_receipt_xml(path.read_bytes())
                details.update({"document_model": identity.document_model, "access_key": identity.access_key, "source_format": artifact.mime_type})
                artifact.processor = "fiscal_receipt_xml"
                artifact.metadata_json = {**(artifact.metadata_json or {}), **details}
            except ReceiptXmlError as exc:
                artifact.error = self._safe_multimodal_error(exc)
                details["parse_error"] = "xml_invalid"
        artifact.status = "review_required"
        artifact.review_required = True
        artifact.review_reason = "Documento recebido; revisao manual obrigatoria antes de qualquer mutacao do ERP."
        artifact.metadata_json = {**(artifact.metadata_json or {}), **details}

    def ingest_multimodal(self, body: GestorMultimodalIn) -> tuple[GestorMultimodalArtifact, bool]:
        existing = self.db.query(GestorMultimodalArtifact).filter(
            GestorMultimodalArtifact.tenant_id == self.tenant_id,
            GestorMultimodalArtifact.idempotency_key == body.idempotency_key,
        ).first()
        if existing is not None:
            return existing, True
        data, mime_type, text_value = self._decode_multimodal_input(body)
        digest = hashlib.sha256(data).hexdigest()
        storage_key, _media_url, asset = self._multimodal_storage(data, mime_type, body.filename)
        artifact = GestorMultimodalArtifact(
            id=str(uuid4()), tenant_id=self.tenant_id, uploaded_by_admin_id=self.admin_id,
            storage_asset_id=asset.id if asset is not None else None,
            media_type=body.media_type, mime_type=mime_type,
            original_filename=PurePosixPath((body.filename or "").replace("\\", "/")).name or None,
            size_bytes=len(data), content_sha256=digest, storage_key=storage_key,
            idempotency_key=body.idempotency_key, status="processing", source_message_id=body.source_message_id,
            metadata_json=self._sanitize_multimodal_metadata(body.metadata),
        )
        self.db.add(artifact)
        self.db.flush()
        self._multimodal_audit(artifact, "ingested", "processing", {"media_type": body.media_type, "mime_type": mime_type, "size_bytes": len(data)})
        try:
            if body.media_type == "text":
                artifact.status = "processed"
                artifact.processor = "inline_text"
                artifact.extracted_text = text_value
                artifact.processed_at = datetime.now(timezone.utc)
            elif body.media_type == "audio":
                self._process_multimodal_audio(artifact, f"/uploads/{storage_key}")
                artifact.processed_at = datetime.now(timezone.utc)
            elif body.media_type == "document":
                self._process_multimodal_document(artifact, PROJECT_ROOT / "uploads" / storage_key)
                artifact.processed_at = datetime.now(timezone.utc)
            else:
                artifact.status = "review_required"
                artifact.review_required = True
                artifact.review_reason = "Imagem armazenada; processador de visao/OCR nao esta habilitado para este tenant."
                artifact.processor = "manual_review"
                artifact.processed_at = datetime.now(timezone.utc)
            self._multimodal_audit(artifact, "processed", artifact.status, {"review_required": artifact.review_required, "processor": artifact.processor})
            self.db.flush()
        except Exception as exc:
            artifact.status = "failed"
            artifact.review_required = True
            artifact.review_reason = "Falha no processamento; revisao manual necessaria."
            artifact.error = self._safe_multimodal_error(exc)
            artifact.processed_at = datetime.now(timezone.utc)
            self._multimodal_audit(artifact, "processing_failed", "failed", {"reason": artifact.error})
            self.db.flush()
        return artifact, False

    def list_multimodal(self, status: str | None = None, limit: int = 100) -> list[GestorMultimodalArtifact]:
        query = self.db.query(GestorMultimodalArtifact).filter(GestorMultimodalArtifact.tenant_id == self.tenant_id)
        if status:
            query = query.filter(GestorMultimodalArtifact.status == status)
        return query.order_by(GestorMultimodalArtifact.created_at.desc()).limit(limit).all()

    def review_multimodal(self, artifact_id: str, body: GestorMultimodalReviewIn) -> GestorMultimodalArtifact:
        artifact = self.db.query(GestorMultimodalArtifact).filter(
            GestorMultimodalArtifact.id == artifact_id, GestorMultimodalArtifact.tenant_id == self.tenant_id,
        ).first()
        if artifact is None:
            raise GestorMultimodalInvalid("Artefato multimodal nao encontrado.", code="GestorMultimodalNotFound")
        if body.extracted_text is not None:
            artifact.extracted_text = body.extracted_text.strip() or None
        artifact.status = "reviewed" if body.approved else "rejected"
        artifact.review_required = False
        artifact.review_reason = body.note.strip() if body.note else (None if body.approved else "Rejeitado na revisao manual.")
        artifact.updated_at = datetime.now(timezone.utc)
        self._multimodal_audit(artifact, "manual_review", artifact.status, {"approved": body.approved, "note": body.note})
        self.db.flush()
        return artifact

    def list_multimodal_audit(self, artifact_id: str, limit: int = 100) -> list[GestorMultimodalAudit]:
        return self.db.query(GestorMultimodalAudit).filter(
            GestorMultimodalAudit.tenant_id == self.tenant_id,
            GestorMultimodalAudit.artifact_id == artifact_id,
        ).order_by(GestorMultimodalAudit.created_at.asc()).limit(limit).all()

    # ---- Proactive automations -------------------------------------------
    @staticmethod
    def _automation_payload(item: GestorAutomation) -> dict[str, Any]:
        return {
            "id": item.id, "name": item.name, "description": item.description,
            "trigger_key": item.trigger_key, "conditions": item.conditions_json or [],
            "actions": item.actions_json or [], "enabled": item.enabled, "dry_run": item.dry_run,
            "max_runs_per_hour": item.max_runs_per_hour,
            "daily_cost_limit": item.daily_cost_limit,
            "daily_quantity_limit": item.daily_quantity_limit,
            "max_actions_per_event": item.max_actions_per_event,
            "service_window_start": item.service_window_start,
            "service_window_end": item.service_window_end,
            "service_weekdays": item.service_weekdays_json or [],
            "opt_out_required": item.opt_out_required,
            "created_at": item.created_at, "updated_at": item.updated_at,
        }

    def _automation_audit(self, automation_id: str, event: str, status: str,
                          details: dict[str, Any], run_id: str | None = None) -> None:
        self.db.add(GestorAutomationAudit(
            tenant_id=self.tenant_id, automation_id=automation_id, run_id=run_id,
            actor_admin_id=self.admin_id, event=event, status=status,
            details_json=details or {},
        ))

    @staticmethod
    def _validate_window_values(start: str, end: str, weekdays: list[int]) -> None:
        if not weekdays or any(day not in range(7) for day in weekdays) or len(set(weekdays)) != len(weekdays):
            raise GestorOperationInvalid("Janela de atendimento possui dias da semana invalidos.", code="GestorAutomationWindowInvalid")

    @staticmethod
    def _validate_gestor_automation(body: GestorAutomationCreate | GestorAutomationUpdate,
                                     current: GestorAutomation | None = None) -> dict[str, Any]:
        values = GestorService._automation_payload(current) if current is not None else {}
        incoming = body.model_dump(exclude_unset=current is not None, mode="json")
        values.update(incoming)
        trigger_key = str(values.get("trigger_key") or "").strip()
        if trigger_key not in TRIGGERS:
            raise GestorOperationInvalid("Gatilho fora da whitelist de eventos existente.", code="GestorAutomationTriggerDenied")
        weekdays = list(values.get("service_weekdays") or [])
        GestorService._validate_window_values(
            str(values.get("service_window_start") or "08:00"),
            str(values.get("service_window_end") or "22:00"), weekdays,
        )
        for action in values.get("actions") or []:
            if action.get("key") != "notification.send_whatsapp":
                raise GestorOperationInvalid(
                    "O Gestor so permite a acao WhatsApp pelo outbox oficial.",
                    code="GestorAutomationActionDenied",
                )
        definition = AutomationDefinitionInput(
            trigger={"key": trigger_key, "config": {}},
            conditions=values.get("conditions") or [], actions=values.get("actions") or [],
        )
        validation = validate_definition(definition)
        if not validation["valid"]:
            raise GestorOperationInvalid(
                "Definicao de automacao invalida: " + "; ".join(error["message"] for error in validation["errors"]),
                code="GestorAutomationDefinitionInvalid",
            )
        for action in values.get("actions") or []:
            config = action.get("config") or {}
            if not str(config.get("message") or "").strip():
                raise GestorOperationInvalid("Acao WhatsApp exige mensagem.", code="GestorAutomationMessageRequired")
        return values

    def list_automations(self, limit: int = 100) -> list[GestorAutomation]:
        return self.db.query(GestorAutomation).filter(
            GestorAutomation.tenant_id == self.tenant_id,
        ).order_by(GestorAutomation.created_at.desc()).limit(limit).all()

    def get_automation(self, automation_id: str) -> GestorAutomation:
        item = self.db.query(GestorAutomation).filter(
            GestorAutomation.id == str(automation_id), GestorAutomation.tenant_id == self.tenant_id,
        ).first()
        if item is None:
            raise GestorOperationNotFound("Automacao do Gestor nao encontrada.", code="GestorAutomationNotFound")
        return item

    def create_automation(self, body: GestorAutomationCreate) -> GestorAutomation:
        values = self._validate_gestor_automation(body)
        if self.db.query(GestorAutomation.id).filter(
            GestorAutomation.tenant_id == self.tenant_id, GestorAutomation.name == body.name.strip(),
        ).first() is not None:
            raise GestorOperationInvalid("Ja existe uma automacao com este nome neste tenant.", code="GestorAutomationAlreadyExists")
        item = GestorAutomation(
            tenant_id=self.tenant_id, created_by_admin_id=self.admin_id, updated_by_admin_id=self.admin_id,
            name=body.name.strip(), description=body.description.strip() if body.description else None,
            trigger_key=values["trigger_key"], conditions_json=values["conditions"], actions_json=values["actions"],
            enabled=body.enabled, dry_run=body.dry_run, max_runs_per_hour=body.max_runs_per_hour,
            daily_cost_limit=body.daily_cost_limit, daily_quantity_limit=body.daily_quantity_limit,
            max_actions_per_event=body.max_actions_per_event, service_window_start=body.service_window_start,
            service_window_end=body.service_window_end, service_weekdays_json=sorted(set(body.service_weekdays)),
            opt_out_required=body.opt_out_required,
        )
        self.db.add(item)
        self.db.flush()
        self._automation_audit(item.id, "created", "created", {"dry_run": item.dry_run, "enabled": item.enabled})
        return item

    def update_automation(self, automation_id: str, body: GestorAutomationUpdate) -> GestorAutomation:
        item = self.get_automation(automation_id)
        values = self._validate_gestor_automation(body, item)
        changes = body.model_dump(exclude_unset=True, mode="json")
        if "name" in changes and self.db.query(GestorAutomation.id).filter(
            GestorAutomation.tenant_id == self.tenant_id, GestorAutomation.name == str(changes["name"]).strip(),
            GestorAutomation.id != item.id,
        ).first() is not None:
            raise GestorOperationInvalid("Ja existe uma automacao com este nome neste tenant.", code="GestorAutomationAlreadyExists")
        mapping = {
            "trigger_key": "trigger_key", "conditions": "conditions_json", "actions": "actions_json",
            "service_weekdays": "service_weekdays_json", "max_runs_per_hour": "max_runs_per_hour",
            "daily_cost_limit": "daily_cost_limit", "daily_quantity_limit": "daily_quantity_limit",
            "max_actions_per_event": "max_actions_per_event", "service_window_start": "service_window_start",
            "service_window_end": "service_window_end", "name": "name", "description": "description",
            "enabled": "enabled", "dry_run": "dry_run", "opt_out_required": "opt_out_required",
        }
        for key, value in changes.items():
            setattr(item, mapping[key], value.strip() if isinstance(value, str) else value)
        if "service_weekdays" in changes:
            item.service_weekdays_json = sorted(set(values["service_weekdays"]))
        item.updated_by_admin_id = self.admin_id
        self._automation_audit(item.id, "updated", "updated", {"fields": sorted(changes)})
        self.db.flush()
        return item

    def delete_automation(self, automation_id: str) -> GestorAutomation:
        """Delete from the active catalog while retaining runs and audit history."""
        item = self.get_automation(automation_id)
        item.enabled = False
        item.updated_by_admin_id = self.admin_id
        self._automation_audit(item.id, "deleted", "disabled", {"reversible": True})
        self.db.flush()
        return item

    @staticmethod
    def _automation_render(template: str, payload: dict[str, Any]) -> str:
        def replace(match: re.Match[str]) -> str:
            value = payload.get(match.group(1))
            return str(value) if value is not None else match.group(0)
        return re.sub(r"\{([a-zA-Z0-9_]+)\}", replace, template).strip()

    @staticmethod
    def _automation_window_open(item: GestorAutomation, now: datetime) -> bool:
        weekdays = set(item.service_weekdays_json or [])
        if now.weekday() not in weekdays:
            return False
        start, end, current = item.service_window_start, item.service_window_end, now.strftime("%H:%M")
        if start == end:
            return True
        return start <= current <= end if start < end else current >= start or current <= end

    def _automation_contact(self, payload: dict[str, Any]) -> dict[str, Any]:
        customer_id = payload.get("customer_id")
        if not customer_id:
            return payload
        try:
            row = self.db.execute(text("""
                SELECT id, name, phone, marketing_whatsapp_consent
                FROM customers WHERE id=:customer_id AND tenant_id=:tenant_id
            """), {"customer_id": str(customer_id), "tenant_id": self.tenant_id}).mappings().first()
        except Exception:
            row = None
        return {**payload, **(dict(row) if row else {})}

    def _automation_limits(self, item: GestorAutomation, now: datetime) -> str | None:
        hourly = self.db.query(GestorAutomationRun).filter(
            GestorAutomationRun.tenant_id == self.tenant_id,
            GestorAutomationRun.automation_id == item.id,
            GestorAutomationRun.created_at >= now - timedelta(hours=1),
            GestorAutomationRun.status.in_(["preview", "awaiting_confirmation", "queued"]),
        ).count()
        if hourly >= item.max_runs_per_hour:
            return "limite de frequencia por hora atingido"
        daily = self.db.query(GestorAutomationRun).filter(
            GestorAutomationRun.tenant_id == self.tenant_id,
            GestorAutomationRun.automation_id == item.id,
            GestorAutomationRun.created_at >= now - timedelta(days=1),
        ).with_entities(GestorAutomationRun.cost_units).all()
        if sum(int(row[0] or 0) for row in daily) >= item.daily_cost_limit:
            return "limite de custo diario atingido"
        if len(daily) >= item.daily_quantity_limit:
            return "limite de quantidade diaria atingido"
        return None

    def _automation_operation(self, item: GestorAutomation, run_id: str, event_id: str,
                              action_index: int, action: dict[str, Any], payload: dict[str, Any]) -> tuple[GestorOperation, str]:
        self.assert_tool_permission("gestor.whatsapp.send_message")
        config = action.get("config") or {}
        target = str(config.get("to_phone") or payload.get("phone") or payload.get("customer_phone") or "").strip()
        if not target:
            raise GestorOperationInvalid("Evento nao possui telefone para a automacao WhatsApp.", code="GestorAutomationPhoneMissing")
        target = self.normalize_phone(target)
        message = self._automation_render(str(config.get("message") or ""), payload)
        if not message:
            raise GestorOperationInvalid("Mensagem proativa vazia.", code="GestorAutomationMessageRequired")
        operation, token = self.create_operation(GestorOperationPreviewIn(
            channel="gestor_automation", phone=target, tool_name="gestor.whatsapp.send_message",
            risk_level="medium", arguments={
                "to_phone": target, "message_type": "text", "body": message,
                "template_name": None, "template_language": "pt_BR", "template_variables": [],
            }, preview={
                "summary": f"Automacao {item.name}: enviar mensagem WhatsApp",
                "automation_id": item.id, "event_id": event_id, "run_id": run_id,
            }, idempotency_key=f"gestor-automation:{item.id}:{event_id}:{action_index}",
            reauthenticated=True,
        ))
        return operation, token

    def simulate_automation(self, automation_id: str, body: GestorAutomationSimulateIn) -> dict[str, Any]:
        item = self.get_automation(automation_id)
        event_key, payload = body.event_key, dict(body.payload)
        if body.event_id:
            row = self.db.execute(text("""
                SELECT event_key, payload_json FROM automation_events
                WHERE id=:event_id AND tenant_id=:tenant_id
            """), {"event_id": body.event_id, "tenant_id": self.tenant_id}).fetchone()
            if not row:
                raise GestorOperationNotFound("Evento de automacao nao encontrado neste tenant.", code="GestorAutomationEventNotFound")
            event_key, payload = row[0], json.loads(row[1] or "{}")
        event_key = event_key or item.trigger_key
        validation = validate_definition(AutomationDefinitionInput(
            trigger={"key": item.trigger_key, "config": {}}, conditions=item.conditions_json or [], actions=item.actions_json or [],
        ))
        matched, steps = conditions_match(AutomationDefinitionInput(
            trigger={"key": item.trigger_key, "config": {}}, conditions=item.conditions_json or [], actions=item.actions_json or [],
        ).conditions, payload)
        trigger_match = event_key == item.trigger_key
        contact = self._automation_contact(payload)
        opt_out = item.opt_out_required and (contact.get("opt_out") is True or contact.get("whatsapp_opt_out") is True or contact.get("marketing_whatsapp_consent") is False)
        blocked = None
        if not validation["valid"]:
            blocked = "definicao invalida"
        elif not trigger_match or not matched:
            blocked = "gatilho ou condicoes nao correspondem"
        elif opt_out:
            blocked = "contato em opt-out ou sem consentimento WhatsApp"
        elif not self._automation_window_open(item, datetime.now(timezone.utc)):
            blocked = "fora da janela de atendimento"
        return {
            "automation_id": item.id, "matched": blocked is None, "would_queue": blocked is None and item.enabled and not item.dry_run,
            "blocked_reason": blocked, "steps": [{"type": "trigger", "key": item.trigger_key, "matched": trigger_match}, *steps],
            "actions": item.actions_json or [], "dry_run": item.dry_run,
        }

    def process_gestor_automation_events(self, limit: int = 25, worker_id: str | None = None) -> dict[str, Any]:
        """Consume due events from the existing automation job stream.

        The transversal worker remains the owner of event publication and its
        lease/retry lifecycle. This consumer only materializes Gestor runs;
        it never executes a commercial action or starts another scheduler.
        """
        from backend.services.automation_event_service import AutomationEventService

        core_result = AutomationEventService(self.db, self.tenant_id).process_pending(
            limit=limit, worker_id=worker_id or f"gestor-automation-{self.admin_id}"
        )
        now = datetime.now(timezone.utc)
        rows = self.db.execute(text("""
            SELECT id, event_key, payload_json, customer_id, aggregate_id
            FROM automation_events
            WHERE tenant_id=:tenant_id AND available_at <= :now
              AND status IN ('pending', 'failed', 'processed')
            ORDER BY available_at, occurred_at LIMIT :limit
        """), {"tenant_id": self.tenant_id, "now": now, "limit": limit}).fetchall()
        result = {"claimed": int(core_result.get("claimed", 0)), "processed": 0, "previews": 0,
                  "awaiting_confirmation": 0, "skipped": 0, "failed": 0, "idempotent_replays": 0,
                  "runs": [], "confirmation_tokens": {}}
        allowed_events = set(TRIGGERS)
        for event_id, event_key, payload_raw, customer_id, aggregate_id in rows:
            if event_key not in allowed_events:
                continue
            payload = json.loads(payload_raw or "{}")
            payload.setdefault("customer_id", customer_id)
            payload.setdefault("aggregate_id", aggregate_id)
            automations = self.db.query(GestorAutomation).filter(
                GestorAutomation.tenant_id == self.tenant_id, GestorAutomation.enabled.is_(True),
                GestorAutomation.trigger_key == event_key,
            ).all()
            for item in automations:
                existing = self.db.query(GestorAutomationRun).filter(
                    GestorAutomationRun.tenant_id == self.tenant_id,
                    GestorAutomationRun.automation_id == item.id,
                    GestorAutomationRun.event_id == str(event_id),
                ).first()
                if existing is not None:
                    result["idempotent_replays"] += 1
                    continue
                simulation = self.simulate_automation(item.id, GestorAutomationSimulateIn(event_key=event_key, payload=payload))
                if simulation["blocked_reason"]:
                    status = "skipped"
                    details = {"reason": simulation["blocked_reason"], "steps": simulation["steps"]}
                    operation_ids: list[str] = []
                    cost_units = 0
                elif (limit_reason := self._automation_limits(item, now)):
                    status = "skipped"
                    details, operation_ids, cost_units = {"reason": limit_reason}, [], 0
                else:
                    actions = (item.actions_json or [])[:item.max_actions_per_event]
                    cost_units = len(actions)
                    operation_ids, tokens, details = [], {}, {"actions": actions, "event_id": str(event_id)}
                    if item.dry_run:
                        status = "preview"
                    else:
                        status = "awaiting_confirmation"
                        try:
                            for index, action in enumerate(actions):
                                operation, token = self._automation_operation(item, str(event_id), str(event_id), index, action, payload)
                                operation_ids.append(operation.id)
                                tokens[operation.id] = token
                            details["operation_ids"] = operation_ids
                            result["confirmation_tokens"].update(tokens)
                        except Exception as exc:
                            status, details, cost_units = "failed", {"reason": str(exc)[:500]}, 0
                    if status == "preview":
                        result["previews"] += 1
                    elif status == "awaiting_confirmation":
                        result["awaiting_confirmation"] += 1
                run = GestorAutomationRun(
                    tenant_id=self.tenant_id, automation_id=item.id, event_id=str(event_id), status=status,
                    action_count=len(operation_ids) if operation_ids else len(item.actions_json or []) if status == "preview" else 0,
                    cost_units=cost_units, operation_ids_json=operation_ids, details_json=details,
                )
                self.db.add(run)
                self.db.flush()
                self._automation_audit(item.id, "event_processed", status, details, run.id)
                result["runs"].append(run)
                result["processed"] += 1
                if status == "skipped":
                    result["skipped"] += 1
                elif status == "failed":
                    result["failed"] += 1
        return result
