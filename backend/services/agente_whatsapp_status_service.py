from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from backend.core.events import (
    DeliveryAssigned,
    DeliveryCompleted,
    OrderCancelled,
    OrderCreated,
    OrderStatusChanged,
    PaymentConfirmed,
    PaymentFailed,
)
from backend.models.agente_whatsapp import AgenteWhatsAppEvent, AgenteWhatsAppMessage
from backend.models.order import Order
from backend.services.agente_whatsapp_service import AgenteWhatsAppService
from backend.services.customer_identity_service import normalize_phone


def _json_dump(value: dict[str, Any] | None) -> str:
    return json.dumps(value or {}, ensure_ascii=False, default=str)


class AgenteWhatsAppStatusService:
    """Creates WhatsApp status notifications from ERP domain events.

    Phase 6 queues outbound/system messages in the AGENTE WHATSAPP history.
    Phase 8 outbox workers can pick up these queued messages and send them via
    the configured WhatsApp provider.
    """

    STATUS_LABELS = {
        "order_created": "Pedido recebido",
        "payment_approved": "Pagamento aprovado",
        "payment_failed": "Pagamento nao aprovado",
        "order_preparing": "Pedido em preparo",
        "order_ready": "Pedido pronto",
        "order_out_delivery": "Saiu para entrega",
        "order_delivered": "Pedido entregue",
        "order_cancelled": "Pedido cancelado",
    }

    ORDER_STATUS_MAP = {
        "pago": "payment_approved",
        "paid": "payment_approved",
        "preparing": "order_preparing",
        "ready_for_pickup": "order_ready",
        "on_the_way": "order_out_delivery",
        "delivered": "order_delivered",
        "cancelled": "order_cancelled",
    }

    def __init__(self, db: Session):
        self._db = db

    def handle_order_created(self, event: OrderCreated) -> dict[str, Any]:
        return self.queue_order_status(event.order_id, "order_created", {"event": event.name})

    def handle_payment_confirmed(self, event: PaymentConfirmed) -> dict[str, Any]:
        return self.queue_order_status(
            event.order_id,
            "payment_approved",
            {
                "event": event.name,
                "payment_id": event.payment_id,
                "amount": event.amount,
                "gateway": event.gateway,
                "transaction_id": event.transaction_id,
            },
        )

    def handle_payment_failed(self, event: PaymentFailed) -> dict[str, Any]:
        return self.queue_order_status(
            event.order_id,
            "payment_failed",
            {"event": event.name, "payment_id": event.payment_id, "reason": event.reason},
        )

    def handle_order_status_changed(self, event: OrderStatusChanged) -> dict[str, Any] | None:
        notification_type = self.ORDER_STATUS_MAP.get(event.to_status)
        if not notification_type:
            return None
        return self.queue_order_status(
            event.order_id,
            notification_type,
            {
                "event": event.name,
                "from_status": event.from_status,
                "to_status": event.to_status,
                "changed_by": event.changed_by,
            },
        )

    def handle_order_cancelled(self, event: OrderCancelled) -> dict[str, Any]:
        return self.queue_order_status(
            event.order_id,
            "order_cancelled",
            {"event": event.name, "reason": event.reason, "refund_required": event.refund_required},
        )

    def handle_delivery_assigned(self, event: DeliveryAssigned) -> dict[str, Any]:
        return self.queue_order_status(
            event.order_id,
            "order_out_delivery",
            {
                "event": event.name,
                "delivery_id": event.delivery_id,
                "delivery_person_id": event.delivery_person_id,
                "delivery_person_name": event.delivery_person_name,
                "estimated_minutes": event.estimated_minutes,
            },
        )

    def handle_delivery_completed(self, event: DeliveryCompleted) -> dict[str, Any]:
        return self.queue_order_status(
            event.order_id,
            "order_delivered",
            {
                "event": event.name,
                "delivery_id": event.delivery_id,
                "delivery_person_id": event.delivery_person_id,
                "duration_minutes": event.duration_minutes,
            },
        )

    def queue_order_status(
        self,
        order_id: str,
        notification_type: str,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        order = self._db.query(Order).filter(Order.id == order_id).first()
        if not order:
            return {"queued": False, "reason": "order_not_found", "order_id": order_id}

        phone = normalize_phone(order.delivery_phone or (order.customer.phone if order.customer else None))
        if not phone:
            return {"queued": False, "reason": "order_without_phone", "order_id": order_id}

        event_type = f"agente_whatsapp_status_{notification_type}"
        if self._already_queued(order.id, event_type):
            return {"queued": False, "reason": "already_queued", "order_id": order.id, "event_type": event_type}

        session, _created = AgenteWhatsAppService(self._db).get_or_create_session(
            phone=phone,
            customer_id=order.customer_id,
            provider="official",
            origin="order_status",
            ai_enabled=False,
            metadata={"source": "order_status", "order_id": order.id},
        )

        message = AgenteWhatsAppMessage(
            id=str(uuid.uuid4()),
            session_id=session.id,
            customer_id=session.customer_id or order.customer_id,
            direction="outbound",
            sender_type="system",
            message_type="status",
            body=self._message_for_order(order, notification_type, payload or {}),
            provider_status="queued",
            raw_payload_json=_json_dump(
                {
                    "notification_type": notification_type,
                    "order_id": order.id,
                    "payload": payload or {},
                }
            ),
            created_at=datetime.now(timezone.utc),
        )
        self._db.add(message)
        self._db.flush()

        self._db.add(
            AgenteWhatsAppEvent(
                id=str(uuid.uuid4()),
                session_id=session.id,
                customer_id=session.customer_id or order.customer_id,
                order_id=order.id,
                event_type=event_type,
                source="order_status",
                payload_json=_json_dump(
                    {
                        "message_id": message.id,
                        "notification_type": notification_type,
                        "label": self.STATUS_LABELS.get(notification_type, notification_type),
                        "phone": phone,
                        "queued_only": True,
                        "payload": payload or {},
                    }
                ),
            )
        )
        self._db.flush()
        return {
            "queued": True,
            "order_id": order.id,
            "session_id": session.id,
            "message_id": message.id,
            "notification_type": notification_type,
        }

    def _already_queued(self, order_id: str, event_type: str) -> bool:
        return (
            self._db.query(AgenteWhatsAppEvent.id)
            .filter(
                AgenteWhatsAppEvent.order_id == order_id,
                AgenteWhatsAppEvent.event_type == event_type,
                AgenteWhatsAppEvent.source == "order_status",
            )
            .first()
            is not None
        )

    def _message_for_order(self, order: Order, notification_type: str, payload: dict[str, Any]) -> str:
        name = (order.delivery_name or (order.customer.name if order.customer else "") or "Cliente").strip()
        code = order.order_code or order.id
        total = f"R$ {float(order.total or 0):.2f}".replace(".", ",")

        if notification_type == "order_created":
            return f"{name}, recebemos seu pedido #{code}. Total: {total}."
        if notification_type == "payment_approved":
            return f"{name}, o pagamento do pedido #{code} foi aprovado. Seu pedido seguira para preparo."
        if notification_type == "payment_failed":
            return f"{name}, o pagamento do pedido #{code} nao foi aprovado. Voce pode tentar novamente."
        if notification_type == "order_preparing":
            return f"{name}, seu pedido #{code} esta em preparo."
        if notification_type == "order_ready":
            return f"{name}, seu pedido #{code} esta pronto."
        if notification_type == "order_out_delivery":
            driver = payload.get("delivery_person_name")
            if driver:
                return f"{name}, seu pedido #{code} saiu para entrega com {driver}."
            return f"{name}, seu pedido #{code} saiu para entrega."
        if notification_type == "order_delivered":
            return f"{name}, seu pedido #{code} foi entregue. Obrigado pela preferencia!"
        if notification_type == "order_cancelled":
            return f"{name}, seu pedido #{code} foi cancelado."
        return f"{name}, atualizacao do pedido #{code}: {self.STATUS_LABELS.get(notification_type, notification_type)}."
