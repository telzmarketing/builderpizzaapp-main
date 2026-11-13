from __future__ import annotations

import uuid
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy.orm import Session

from backend.core.exceptions import DomainError
from backend.models.marketplace_settlement import MarketplaceSettlement
from backend.models.order import Order, OrderStatus
from backend.schemas.marketplace_settlement import MarketplaceSettlementIn


MONEY = Decimal("0.01")
APP_ORIGINS = {"partner_99", "ifood", "keeta"}


def money(value: Decimal | int | float | str | None) -> Decimal:
    return Decimal(str(value or 0)).quantize(MONEY, rounding=ROUND_HALF_UP)


class MarketplaceSettlementService:
    def __init__(self, db: Session, tenant_id: str):
        self.db = db
        self.tenant_id = tenant_id

    def create(self, order_id: str, payload: MarketplaceSettlementIn, idempotency_key: str, admin_id: str | None = None) -> MarketplaceSettlement:
        key = idempotency_key.strip()
        if not key:
            raise DomainError("Idempotency-Key e obrigatoria.", code="MarketplaceSettlementIdempotencyRequired")
        existing = self.db.query(MarketplaceSettlement).filter_by(tenant_id=self.tenant_id, idempotency_key=key).first()
        if existing:
            return existing
        order = self.db.query(Order).filter(Order.tenant_id == self.tenant_id, Order.id == order_id).first()
        if order is None:
            raise DomainError("Pedido nao encontrado.", code="OrderNotFound")
        origin = order.order_origin.value if hasattr(order.order_origin, "value") else order.order_origin
        if order.status != OrderStatus.delivered or origin not in APP_ORIGINS:
            raise DomainError("A conciliacao so pode ser criada para pedido de aplicativo entregue.", code="MarketplaceSettlementOrderNotEligible")
        if self.db.query(MarketplaceSettlement).filter_by(tenant_id=self.tenant_id, provider=payload.provider, order_id=order.id).first():
            raise DomainError("Este pedido ja possui conciliacao para o provedor.", code="MarketplaceSettlementAlreadyExists")
        expected = money(payload.expected_net_amount)
        received = money(payload.received_net_amount)
        status = payload.status
        variance = money(received - expected)
        if status == "received" and received == 0:
            raise DomainError("Recebimento precisa ter valor positivo.", code="MarketplaceSettlementInvalidReceivedAmount")
        row = MarketplaceSettlement(
            id=str(uuid.uuid4()), tenant_id=self.tenant_id, order_id=order.id, provider=payload.provider,
            status=status, gross_amount=money(payload.gross_amount), store_discount_amount=money(payload.store_discount_amount),
            marketplace_discount_amount=money(payload.marketplace_discount_amount), delivery_fee=money(payload.delivery_fee),
            service_fee=money(payload.service_fee), commission_amount=money(payload.commission_amount), tax_amount=money(payload.tax_amount),
            expected_net_amount=expected, received_net_amount=received, variance_amount=variance,
            external_settlement_reference=payload.external_settlement_reference, expected_settlement_at=payload.expected_settlement_at,
            settled_at=payload.settled_at, idempotency_key=key, notes=payload.notes, created_by_admin_id=admin_id,
        )
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def list(self, *, order_id: str | None = None, provider: str | None = None, status: str | None = None) -> list[MarketplaceSettlement]:
        query = self.db.query(MarketplaceSettlement).filter(MarketplaceSettlement.tenant_id == self.tenant_id)
        if order_id:
            query = query.filter(MarketplaceSettlement.order_id == order_id)
        if provider:
            query = query.filter(MarketplaceSettlement.provider == provider)
        if status:
            query = query.filter(MarketplaceSettlement.status == status)
        return query.order_by(MarketplaceSettlement.created_at.desc()).all()
