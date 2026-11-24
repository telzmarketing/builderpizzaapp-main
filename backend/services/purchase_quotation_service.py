from __future__ import annotations

import uuid
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy.orm import Session, joinedload

from backend.core.exceptions import DomainError
from backend.core.tenant_context import TenantContext
from backend.models.inventory import InventoryItem, InventorySupplier, InventoryUnit
from backend.models.purchase_quotation import PurchaseQuotation, PurchaseQuotationLine, PurchaseQuotationOffer, PurchaseQuotationSupplier
from backend.models.purchase_requisition import PurchaseRequisition
from backend.schemas.purchase_quotation import PurchaseQuotationCreate, PurchaseQuotationOfferCreate, PurchaseQuotationTransitionIn
from backend.services.idempotency_service import IdempotencyService


class PurchaseQuotationNotFound(DomainError):
    http_status = 404
    def __init__(self): super().__init__("Cotacao de compra nao encontrada.", code="PurchaseQuotationNotFound")


class PurchaseQuotationConflict(DomainError):
    http_status = 409


class PurchaseQuotationService:
    def __init__(self, db: Session, actor_id: str, tenant_context: TenantContext):
        self.db, self.actor_id, self.tenant_id = db, actor_id, tenant_context.tenant_id

    def list(self, status: str | None = None):
        query = self.db.query(PurchaseQuotation).options(joinedload(PurchaseQuotation.suppliers).joinedload(PurchaseQuotationSupplier.supplier), joinedload(PurchaseQuotation.lines).joinedload(PurchaseQuotationLine.item), joinedload(PurchaseQuotation.lines).joinedload(PurchaseQuotationLine.unit), joinedload(PurchaseQuotation.offers).joinedload(PurchaseQuotationOffer.supplier)).filter(PurchaseQuotation.tenant_id == self.tenant_id)
        if status: query = query.filter(PurchaseQuotation.status == status)
        return [self._out(row) for row in query.order_by(PurchaseQuotation.created_at.desc()).limit(500).all()]

    def get(self, quotation_id: str):
        row = self._query().filter(PurchaseQuotation.id == quotation_id).first()
        if not row: raise PurchaseQuotationNotFound()
        return self._out(row)

    def create(self, body: PurchaseQuotationCreate, key: str):
        claim = IdempotencyService(self.db, self.tenant_id).claim(key, "purchase_quotation_create", body.model_dump(mode="json"))
        if claim.replay_resource_id: return self.get(claim.replay_resource_id)
        requisition = self.db.query(PurchaseRequisition).options(joinedload(PurchaseRequisition.items)).filter(PurchaseRequisition.tenant_id == self.tenant_id, PurchaseRequisition.id == body.requisition_id).first()
        try:
            if not requisition: raise PurchaseQuotationConflict("Requisicao nao encontrada neste tenant.", code="QuotationRequisitionNotFound")
            if requisition.status not in {"approved", "sourcing"}: raise PurchaseQuotationConflict("A requisicao precisa estar aprovada para iniciar cotacao.", code="QuotationRequisitionNotApproved")
            if self.db.query(PurchaseQuotation).filter(PurchaseQuotation.tenant_id == self.tenant_id, PurchaseQuotation.requisition_id == requisition.id, PurchaseQuotation.status.in_(["draft", "open", "closed"])).first(): raise PurchaseQuotationConflict("Ja existe uma cotacao ativa para esta requisicao.", code="QuotationAlreadyExists")
            suppliers = self.db.query(InventorySupplier).filter(InventorySupplier.tenant_id == self.tenant_id, InventorySupplier.id.in_(set(body.supplier_ids)), InventorySupplier.active.is_(True)).all()
            if len(suppliers) != len(set(body.supplier_ids)): raise PurchaseQuotationConflict("Todos os fornecedores devem ser ativos e pertencer ao tenant.", code="QuotationSupplierInvalid")
            if not requisition.items: raise PurchaseQuotationConflict("A requisicao nao possui itens.", code="QuotationWithoutItems")
            row = PurchaseQuotation(id=f"pquo-{uuid.uuid4().hex[:14]}", tenant_id=self.tenant_id, requisition_id=requisition.id, code=self._next_code(), created_by_admin_id=self.actor_id, response_due=body.response_due, notes=body.notes)
            self.db.add(row); self.db.flush()
            for position, item in enumerate(requisition.items): row.lines.append(PurchaseQuotationLine(id=f"pql-{uuid.uuid4().hex[:14]}", tenant_id=self.tenant_id, item_id=item.item_id, unit_id=item.unit_id, quantity=item.quantity, position=position))
            for supplier in suppliers: row.suppliers.append(PurchaseQuotationSupplier(id=f"pqs-{uuid.uuid4().hex[:14]}", tenant_id=self.tenant_id, supplier_id=supplier.id))
            IdempotencyService(self.db, self.tenant_id).complete(claim.record, row.id, commit=False); self.db.commit(); return self.get(row.id)
        except Exception:
            IdempotencyService(self.db, self.tenant_id).abandon(claim.record); raise

    def add_offer(self, quotation_id: str, body: PurchaseQuotationOfferCreate, key: str):
        claim = IdempotencyService(self.db, self.tenant_id).claim(key, "purchase_quotation_offer", {"quotation_id": quotation_id, **body.model_dump(mode="json")})
        if claim.replay_resource_id: return self.get(quotation_id)
        row = self._locked(quotation_id)
        if row.status != "open": raise PurchaseQuotationConflict("Somente cotacoes abertas recebem propostas.", code="QuotationNotOpen")
        line = next((item for item in row.lines if item.id == body.quotation_line_id), None)
        if not line: raise PurchaseQuotationConflict("Item da cotacao nao encontrado.", code="QuotationLineNotFound")
        supplier_link = next((item for item in row.suppliers if item.supplier_id == body.supplier_id), None)
        if not supplier_link: raise PurchaseQuotationConflict("Fornecedor nao foi convidado para esta cotacao.", code="QuotationSupplierNotInvited")
        offer = next((item for item in row.offers if item.quotation_line_id == line.id and item.supplier_id == body.supplier_id), None)
        values = body.model_dump(exclude={"quotation_line_id", "supplier_id"})
        if offer:
            for key, value in values.items(): setattr(offer, key, value)
        else: row.offers.append(PurchaseQuotationOffer(id=f"pqo-{uuid.uuid4().hex[:14]}", tenant_id=self.tenant_id, quotation_id=row.id, **body.model_dump()))
        supplier_link.status = "responded"; row.version += 1
        IdempotencyService(self.db, self.tenant_id).complete(claim.record, row.id, commit=False); self.db.commit(); return self.get(row.id)

    def transition(self, quotation_id: str, action: str, body: PurchaseQuotationTransitionIn, key: str, supplier_id: str | None = None):
        claim = IdempotencyService(self.db, self.tenant_id).claim(key, "purchase_quotation_transition", {"quotation_id": quotation_id, "action": action, "supplier_id": supplier_id, **body.model_dump(mode="json")})
        if claim.replay_resource_id: return self.get(quotation_id)
        row = self._locked(quotation_id)
        if row.version != body.expected_version: raise PurchaseQuotationConflict("A cotacao foi alterada por outro usuario.", code="QuotationVersionConflict")
        allowed = {"draft": {"open": "open", "cancel": "cancelled"}, "open": {"close": "closed", "cancel": "cancelled"}, "closed": {"award": "awarded"}, "awarded": {}, "cancelled": {}}
        target = allowed.get(row.status, {}).get(action)
        if not target: raise PurchaseQuotationConflict("Transicao de cotacao nao permitida.", code="QuotationInvalidTransition")
        if action == "award":
            if not supplier_id or not any(item.supplier_id == supplier_id for item in row.suppliers): raise PurchaseQuotationConflict("Fornecedor vencedor invalido.", code="QuotationAwardSupplierInvalid")
            if not any(item.supplier_id == supplier_id for item in row.offers): raise PurchaseQuotationConflict("Fornecedor vencedor nao possui proposta.", code="QuotationAwardWithoutOffer")
            row.awarded_supplier_id = supplier_id
        row.status, row.version = target, row.version + 1
        IdempotencyService(self.db, self.tenant_id).complete(claim.record, row.id, commit=False); self.db.commit(); return self.get(row.id)

    def _query(self):
        return self.db.query(PurchaseQuotation).options(joinedload(PurchaseQuotation.suppliers).joinedload(PurchaseQuotationSupplier.supplier), joinedload(PurchaseQuotation.lines).joinedload(PurchaseQuotationLine.item), joinedload(PurchaseQuotation.lines).joinedload(PurchaseQuotationLine.unit), joinedload(PurchaseQuotation.offers).joinedload(PurchaseQuotationOffer.supplier)).filter(PurchaseQuotation.tenant_id == self.tenant_id)

    def _locked(self, quotation_id: str):
        row = self._query().filter(PurchaseQuotation.id == quotation_id).with_for_update().first()
        if not row: raise PurchaseQuotationNotFound()
        return row

    def _next_code(self):
        return f"COT-{self.db.query(PurchaseQuotation).filter(PurchaseQuotation.tenant_id == self.tenant_id).count() + 1:06d}"

    @staticmethod
    def _out(row):
        offers = []
        for offer in row.offers:
            normalized = (Decimal(offer.unit_price) / Decimal(offer.conversion_factor)).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)
            total = (Decimal(offer.unit_price) * Decimal(next(line.quantity for line in row.lines if line.id == offer.quotation_line_id)) / Decimal(offer.conversion_factor) + Decimal(offer.freight) - Decimal(offer.discount)).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)
            offers.append({"id": offer.id, "supplier_id": offer.supplier_id, "supplier_name": offer.supplier.name, "quotation_line_id": offer.quotation_line_id, "unit_price": offer.unit_price, "conversion_factor": offer.conversion_factor, "normalized_unit_price": normalized, "freight": offer.freight, "discount": offer.discount, "total": total, "payment_terms": offer.payment_terms, "delivery_days": offer.delivery_days, "valid_until": offer.valid_until, "notes": offer.notes})
        return {"id": row.id, "tenant_id": row.tenant_id, "requisition_id": row.requisition_id, "code": row.code, "status": row.status, "response_due": row.response_due, "notes": row.notes, "version": row.version, "awarded_supplier_id": row.awarded_supplier_id, "created_by_admin_id": row.created_by_admin_id, "created_at": row.created_at, "updated_at": row.updated_at, "suppliers": [{"supplier_id": s.supplier_id, "supplier_name": s.supplier.name, "status": s.status} for s in row.suppliers], "lines": [{"id": l.id, "item_id": l.item_id, "item_name": l.item.name, "unit_id": l.unit_id, "unit_symbol": l.unit.symbol, "quantity": l.quantity, "position": l.position} for l in row.lines], "offers": offers}
