"""Transactional production effects over canonical orders, attempts and stock.

Commands own commit/rollback. They have no HTTP, payment-provider or KDS routing
responsibilities. A reproduction consumes stock when its own attempt starts.
"""
from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy.exc import IntegrityError

from backend.core.exceptions import DomainError, OrderNotFound
from backend.core.tenant_context import TenantContext
from backend.models.cmv import OrderItemCmvSnapshot
from backend.models.finance import FinanceTransaction
from backend.models.inventory import InventoryStockMovement
from backend.models.kds_production import (
    KdsAssignment, ProductionAttempt, ProductionAttemptConsumption,
    ProductionEffect, ProductionUnit,
)
from backend.models.order import Order, OrderItem
from backend.models.payment import Payment
from backend.models.rbac import AdminAuditLog
from backend.models.tenant import Tenant
from backend.schemas.production_effects import (
    OrderBonificationIn, ProductionEffectOut, ProductionLossIn,
    ProductionReproductionIn,
)
from backend.services.kds_production_service import KdsProductionService


class ProductionEffectConflict(DomainError):
    http_status = 409


class ProductionEffectsService:
    def __init__(self, db, context: TenantContext, actor_id: str):
        if not isinstance(context, TenantContext) or not actor_id or not actor_id.strip():
            raise DomainError("Contexto confiavel e ator obrigatorios.", code="ProductionEffectContextRequired")
        if context.actor_id and context.actor_id != actor_id:
            raise DomainError("Ator diverge do contexto confiavel.", code="ProductionEffectActorMismatch")
        self.db, self.context, self.tenant_id, self.actor_id = db, context, context.tenant_id, actor_id
        self.production = KdsProductionService(db, context)

    def _query(self, model):
        return self.db.query(model).filter(model.tenant_id == self.tenant_id)

    def _order(self, order_id):
        order = self._query(Order).filter_by(id=order_id).populate_existing().with_for_update().first()
        if not order or order.archived_at:
            raise OrderNotFound(order_id)
        return order

    def _attempt(self, attempt_id):
        attempt = self.production._unit(attempt_id, True)
        latest = self._query(ProductionAttempt).filter_by(
            production_unit_id=attempt.production_unit_id,
        ).order_by(ProductionAttempt.attempt_number.desc()).first()
        if latest.id != attempt.id:
            raise ProductionEffectConflict("Tentativa ja substituida.", code="SupersededProductionAttempt")
        return attempt

    @staticmethod
    def _result(effect):
        return ProductionEffectOut.model_validate(effect).model_dump(mode="json")

    def _command(self, kind, body, key, business_key, execute):
        if not isinstance(key, str) or not key.strip() or len(key.strip()) > 200:
            raise DomainError("Chave de idempotencia obrigatoria, maximo 200 caracteres.", code="IdempotencyKeyRequired")
        key = key.strip()
        request = body.model_dump(mode="json")
        digest = hashlib.sha256(json.dumps(request, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        try:
            # Same tenant mutex used by KDS commands, before order/attempt/item
            # locks. Unique indexes also protect identities outside this writer.
            if not self.db.query(Tenant).filter_by(id=self.tenant_id).with_for_update().first():
                raise DomainError("Estabelecimento indisponivel.", code="TenantUnavailable")
            prior = self._query(ProductionEffect).filter_by(kind=kind, idempotency_key=key).first()
            if prior:
                if prior.request_hash != digest:
                    raise ProductionEffectConflict("Chave reutilizada com conteudo diferente.", code="IdempotencyConflict")
                result = self._result(prior)
                self.db.commit()
                return result
            if self._query(ProductionEffect).filter_by(kind=kind, business_key=business_key).first():
                raise ProductionEffectConflict("Efeito ja registrado para esta origem.", code="BusinessIdentityConflict")
            effect = ProductionEffect(
                id=str(uuid.uuid4()), tenant_id=self.tenant_id, kind=kind,
                business_key=business_key, idempotency_key=key, request_hash=digest,
                actor_id=self.actor_id, reason=body.reason, cost_total=0,
                discount_amount=0, snapshot_json={},
            )
            execute(effect)
            self.db.add(effect)
            self.db.flush()
            self.db.add(AdminAuditLog(
                id=str(uuid.uuid4()), tenant_id=self.tenant_id, user_id=self.actor_id,
                action=f"production_{kind}", module_key="cozinha",
                entity_type="production_effect", entity_id=effect.id,
                old_value=json.dumps(effect.snapshot_json.get("before", {}), ensure_ascii=True),
                new_value=json.dumps(self._result(effect), ensure_ascii=True),
            ))
            self.db.commit()
            return self._result(effect)
        except IntegrityError as exc:
            self.db.rollback()
            raise ProductionEffectConflict("Conflito de identidade ou referencia concorrente.", code="ProductionEffectIntegrityConflict") from exc
        except Exception:
            self.db.rollback()
            raise

    def record_loss(self, body: ProductionLossIn, key: str):
        def execute(effect):
            attempt = self._attempt(body.attempt_id)
            order = self._order(attempt.unit.order_id)
            if getattr(order.status, "value", order.status) != "preparing" or attempt.unit.dispatch_completed_at:
                raise ProductionEffectConflict("Perda exige pedido em producao e unidade nao expedida.", code="ProductionEffectStateConflict")
            if attempt.version != body.expected_version:
                raise ProductionEffectConflict("Tentativa alterada por outro operador.", code="VersionConflict")
            existing = self._query(ProductionAttemptConsumption).filter_by(attempt_id=attempt.id).first()
            if attempt.state == "cancelled" or not (
                attempt.started_at or existing or attempt.state in {"assembling", "assembled", "baking", "checking", "ready"}
            ):
                raise ProductionEffectConflict("Perda exige evidencia de producao iniciada.", code="ProductionNotStarted")
            before = {"state": attempt.state, "version": attempt.version, "unit_state": attempt.unit.state}
            consumption = self.production.consume_attempt(attempt.id, self.actor_id, require_stock=True)
            attempt.stock_consumption_mode = consumption.get("mode", "attempts")
            lines = self._query(ProductionAttemptConsumption).filter_by(attempt_id=attempt.id).order_by(
                ProductionAttemptConsumption.inventory_item_id,
            ).all()
            if not lines:
                raise ProductionEffectConflict("Perda sem evidencia de consumo.", code="ProductionConsumptionRequired")
            effect.order_id, effect.attempt_id = order.id, attempt.id
            effect.cost_total = sum((line.quantity * line.unit_cost for line in lines), Decimal(0))
            technical = self._query(OrderItemCmvSnapshot).filter_by(order_item_id=attempt.unit.order_item_id).first()
            effect.snapshot_json = {
                "before": before, "order_item_id": attempt.unit.order_item_id,
                "composition": technical.composition_json if technical else None,
                "missing_cost": bool(technical is None or technical.missing_cost),
                "consumption_mode": attempt.stock_consumption_mode,
                "consumptions": [{"id": line.id, "inventory_item_id": line.inventory_item_id,
                    "quantity": str(line.quantity), "unit_cost": str(line.unit_cost),
                    "movement_ids": line.movement_ids, "operation_id": line.operation_id} for line in lines],
                "financial_effect": "non_cash_cost_reclassification",
            }
            attempt.state = attempt.unit.state = "cancelled"
            attempt.version += 1
            attempt.unit.version += 1
            attempt.check_reason = body.reason
            for assignment in self._query(KdsAssignment).filter_by(attempt_id=attempt.id, active=True).all():
                assignment.active, assignment.released_at = False, datetime.now(timezone.utc)
                assignment.reason = body.reason
        return self._command("loss", body, key, body.attempt_id, execute)

    def create_reproduction(self, body: ProductionReproductionIn, key: str):
        def execute(effect):
            loss = self._query(ProductionEffect).filter_by(id=body.loss_id, kind="loss").first()
            if not loss:
                raise DomainError("Perda nao encontrada neste estabelecimento.", code="ProductionLossNotFound")
            order = self._order(loss.order_id)
            if getattr(order.status, "value", order.status) != "preparing":
                raise ProductionEffectConflict("Reposicao exige pedido em producao.", code="ProductionEffectStateConflict")
            previous = self._attempt(loss.attempt_id)
            if previous.state != "cancelled" or previous.unit.dispatch_completed_at:
                raise ProductionEffectConflict("Tentativa original deve estar encerrada por perda.", code="ProductionEffectStateConflict")
            attempt = ProductionAttempt(
                id=str(uuid.uuid4()), tenant_id=self.tenant_id,
                production_unit_id=previous.production_unit_id,
                attempt_number=previous.attempt_number + 1, previous_attempt_id=previous.id,
                state="queued", version=1,
            )
            self.db.add(attempt)
            self.db.flush()
            previous.unit.state = "queued"
            previous.unit.version += 1
            effect.order_id, effect.attempt_id, effect.source_effect_id = order.id, attempt.id, loss.id
            effect.snapshot_json = {
                "previous_attempt_id": previous.id, "production_unit_id": previous.production_unit_id,
                "order_item_id": previous.unit.order_item_id,
                "consumption": "on_attempt_start", "financial_effect": "no_additional_sale",
            }
        return self._command("reproduction", body, key, body.loss_id, execute)

    def bonify_order(self, body: OrderBonificationIn, key: str):
        def execute(effect):
            order = self._order(body.order_id)
            if (getattr(order.status, "value", order.status) != "pending" or order.order_origin != "own"
                    or any((order.preparation_started_at, order.ready_for_pickup_at,
                            order.out_for_delivery_at, order.delivered_at))):
                raise ProductionEffectConflict("Bonificacao exige pedido proprio antes do pagamento.", code="ProductionEffectStateConflict")
            payment = self._query(Payment).filter_by(order_id=order.id).first()
            payment_started = payment is not None and (
                payment.status != "pending" or any(getattr(payment, name) for name in (
                    "transaction_id", "provider_payment_id", "mercado_pago_payment_id", "provider_status",
                    "qr_code", "qr_code_text", "pix_payload", "pix_qr_code", "payment_url", "client_secret",
                    "raw_response", "webhook_data", "paid_at",
                ))
            )
            if payment_started or self._query(FinanceTransaction).filter(
                FinanceTransaction.order_id == order.id, FinanceTransaction.status != "cancelled",
            ).first():
                raise ProductionEffectConflict("Pedido ja possui pagamento ou lancamento financeiro.", code="BonificationPaymentConflict")
            if self._query(InventoryStockMovement).filter(
                InventoryStockMovement.source_id == order.id,
                InventoryStockMovement.source_type.in_(("order_sale", "foundation_order_sale")),
                InventoryStockMovement.quantity_delta < 0,
            ).first():
                raise ProductionEffectConflict("Pedido ja possui consumo de insumos.", code="ProductionAlreadyStarted")
            units = self._query(ProductionUnit).filter_by(order_id=order.id).all()
            if any(unit.state not in {"unassigned", "queued"} for unit in units):
                raise ProductionEffectConflict("Bonificacao deve anteceder a producao.", code="ProductionAlreadyStarted")
            if units:
                unit_ids = [unit.id for unit in units]
                if self._query(ProductionAttempt).filter(
                    ProductionAttempt.production_unit_id.in_(unit_ids),
                    ProductionAttempt.started_at.isnot(None),
                ).first() or self._query(ProductionAttemptConsumption).join(
                    ProductionAttempt, ProductionAttempt.id == ProductionAttemptConsumption.attempt_id,
                ).filter(ProductionAttempt.production_unit_id.in_(unit_ids)).first():
                    raise ProductionEffectConflict("Pedido possui historico de producao.", code="ProductionAlreadyStarted")
            items = self._query(OrderItem).filter_by(order_id=order.id).order_by(OrderItem.position, OrderItem.id).all()
            if not items or order.coupon_id or any(item.is_gift for item in items):
                raise ProductionEffectConflict("Bonificacao exige itens sem outro beneficio aplicado.", code="BonificationCompositionConflict")
            before = {name: getattr(order, name) for name in (
                "subtotal", "discount", "shipping_fee", "delivery_fee_original", "delivery_fee_discount",
                "delivery_fee_final", "total", "manual_discount_type", "manual_discount_value",
            )}
            composition = []
            for item in items:
                # Retain the immutable technical snapshot. Zero sale never means
                # zero ingredients; the canonical attempt writer consumes later.
                snapshot = self._query(OrderItemCmvSnapshot).filter_by(order_item_id=item.id).first()
                if not snapshot or snapshot.missing_recipe or not snapshot.ingredients:
                    raise ProductionEffectConflict("Bonificacao exige composicao tecnica congelada.", code="RecipeSnapshotRequired")
                composition.append({"id": item.id, "product_id": item.product_id, "quantity": item.quantity,
                    "unit_price": item.unit_price, "total_price": item.total_price,
                    "snapshot_id": snapshot.id})
                item.original_price = item.original_price if item.original_price is not None else item.unit_price
                item.standard_unit_price = item.standard_unit_price if item.standard_unit_price is not None else item.unit_price
                item.applied_unit_price = item.unit_price = item.total_price = 0
                item.is_gift, item.gift_reason = True, "staff_meal"
            effect.order_id, effect.discount_amount = order.id, Decimal(str(order.total))
            effect.snapshot_json = {"before": before, "items": composition, "beneficiary": body.beneficiary,
                "consumption": "on_attempt_start", "financial_effect": "sale_waiver_without_cash_settlement"}
            order.subtotal = order.discount = order.shipping_fee = order.total = 0
            order.delivery_fee_original = order.delivery_fee_discount = order.delivery_fee_final = 0
            order.manual_discount_type = order.manual_discount_value = None
        return self._command("bonification", body, key, body.order_id, execute)
