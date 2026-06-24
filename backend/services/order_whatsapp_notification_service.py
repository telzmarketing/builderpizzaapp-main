from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.models.admin import AdminUser
from backend.models.order import Order
from backend.models.rbac import Role
from backend.services.whatsapp_gateway_service import WhatsAppGatewayService


SITE_CONFIG_KEY = "order_whatsapp_notifications"
DEFAULT_MESSAGE_TEMPLATE = "Novo pedido recebido\nPedido: #{order_number}\nCliente: {customer_name}"
DEFAULT_SETTINGS = {
    "enabled": False,
    "recipient_admin_ids": [],
    "message_template": DEFAULT_MESSAGE_TEMPLATE,
}


def _digits(value: str | None) -> str:
    return "".join(ch for ch in str(value or "") if ch.isdigit())


class OrderWhatsAppNotificationService:
    """Internal order alert sender.

    It sends directly through WhatsApp Gateway and intentionally does not touch
    Agente WhatsApp sessions, messages or outbox.
    """

    def __init__(self, db: Session):
        self._db = db

    def get_settings(self) -> dict[str, Any]:
        content = self._get_site_content()
        raw = content.get(SITE_CONFIG_KEY)
        if not isinstance(raw, dict):
            raw = {}
        return self._sanitize_settings(raw)

    def update_settings(self, payload: dict[str, Any]) -> dict[str, Any]:
        settings = self._sanitize_settings(payload)
        valid_ids = {item["id"] for item in self.list_recipients() if item["has_phone"]}
        invalid_ids = [rid for rid in settings["recipient_admin_ids"] if rid not in valid_ids]
        if invalid_ids:
            raise ValueError("Selecione apenas usuarios ativos com telefone cadastrado.")

        content = self._get_site_content()
        content[SITE_CONFIG_KEY] = settings
        self._save_site_content(content)
        return settings

    def list_recipients(self) -> list[dict[str, Any]]:
        rows = (
            self._db.query(AdminUser, Role)
            .outerjoin(Role, AdminUser.role_id == Role.id)
            .filter(AdminUser.active == True)  # noqa: E712
            .order_by(AdminUser.name.asc())
            .all()
        )
        result: list[dict[str, Any]] = []
        for user, role in rows:
            role_name = role.name if role else ("Master" if not user.role_id else None)
            phone = (user.phone or "").strip()
            result.append(
                {
                    "id": user.id,
                    "name": user.name,
                    "email": user.email,
                    "phone": phone or None,
                    "role_id": user.role_id,
                    "role_name": role_name,
                    "has_phone": bool(_digits(phone)),
                }
            )
        return result

    def notify_new_order(self, order: Order) -> dict[str, Any]:
        settings = self.get_settings()
        if not settings["enabled"] or not settings["recipient_admin_ids"]:
            return {"enabled": settings["enabled"], "sent": 0, "failed": 0, "results": []}

        recipients = self._selected_recipients(settings["recipient_admin_ids"])
        if not recipients:
            return {"enabled": True, "sent": 0, "failed": 0, "results": []}

        text_body = self._render_message(order, settings["message_template"])
        gateway = WhatsAppGatewayService(self._db)
        results: list[dict[str, Any]] = []

        for recipient in recipients:
            phone = recipient["phone"]
            try:
                result = gateway.send_text_message(phone=phone, text=text_body)
                results.append(
                    {
                        "admin_user_id": recipient["id"],
                        "phone": phone,
                        "ok": bool(result.ok),
                        "status": result.status,
                        "message": result.message,
                        "provider_message_id": result.provider_message_id,
                    }
                )
            except Exception as exc:
                results.append(
                    {
                        "admin_user_id": recipient["id"],
                        "phone": phone,
                        "ok": False,
                        "status": "error",
                        "message": str(exc),
                        "provider_message_id": None,
                    }
                )

        self._db.commit()
        sent = sum(1 for item in results if item["ok"])
        return {"enabled": True, "sent": sent, "failed": len(results) - sent, "results": results}

    def _selected_recipients(self, recipient_admin_ids: list[str]) -> list[dict[str, Any]]:
        selected = set(recipient_admin_ids)
        return [
            item
            for item in self.list_recipients()
            if item["id"] in selected and item["has_phone"] and item["phone"]
        ]

    def _render_message(self, order: Order, template: str) -> str:
        order_number = order.order_code or order.id
        return (
            template.replace("{order_number}", str(order_number))
            .replace("{order_id}", str(order.id))
            .replace("{customer_name}", str(order.delivery_name or "Cliente"))
        ).strip() or DEFAULT_MESSAGE_TEMPLATE

    def _sanitize_settings(self, raw: dict[str, Any]) -> dict[str, Any]:
        ids: list[str] = []
        for value in raw.get("recipient_admin_ids") or []:
            text_value = str(value or "").strip()
            if text_value and text_value not in ids:
                ids.append(text_value)

        template = str(raw.get("message_template") or DEFAULT_MESSAGE_TEMPLATE).strip()
        if not template:
            template = DEFAULT_MESSAGE_TEMPLATE
        if len(template) > 500:
            template = template[:500]

        return {
            "enabled": bool(raw.get("enabled")),
            "recipient_admin_ids": ids,
            "message_template": template,
        }

    def _get_site_content(self) -> dict[str, Any]:
        row = self._db.execute(text("SELECT content FROM site_config WHERE id = 'default'")).fetchone()
        if row and row[0]:
            try:
                data = json.loads(row[0])
                if isinstance(data, dict):
                    return data
            except Exception:
                pass
        return {}

    def _save_site_content(self, content: dict[str, Any]) -> None:
        now = datetime.now(timezone.utc)
        self._db.execute(
            text(
                "INSERT INTO site_config (id, content, updated_at) VALUES ('default', :content, :updated_at) "
                "ON CONFLICT (id) DO UPDATE SET content = EXCLUDED.content, updated_at = EXCLUDED.updated_at"
            ),
            {"content": json.dumps(content, ensure_ascii=False), "updated_at": now},
        )
        self._db.commit()
