from __future__ import annotations

import uuid
import hashlib
from types import SimpleNamespace
from decimal import Decimal
from sqlalchemy.orm import Session, joinedload
from backend.core.exceptions import DomainError
from backend.models.inventory_receipts import InventoryReceiptDocument, InventoryReceiptDocumentLine
from backend.models.finance import FinanceObligation, FinanceObligationInstallment, FinanceTransaction
from backend.services.fiscal_receipt_xml import parse_receipt_xml, ReceiptXmlError
from backend.services.finance_service import FinanceService

class ReceiptDocumentError(DomainError):
    http_status = 422
    def __init__(self, message: str): super().__init__(message, code="ReceiptDocumentError")

class InventoryReceiptService:
    def __init__(self, db: Session, tenant_id: str, admin_id: str | None = None):
        self.db, self.tenant_id, self.admin_id = db, tenant_id, admin_id

    def _out(self, row):
        return {"id": row.id, "tenant_id": row.tenant_id, "purchase_id": row.purchase_id, "supplier_id": row.supplier_id,
                "supplier_name": None, "access_key": row.access_key, "supplier_document": row.issuer_document,
                "document_number": row.number, "series": row.series, "issue_date": row.issued_at, "entry_date": row.received_at,
                "total_products": row.extracted_json.get("total_products") if isinstance(row.extracted_json, dict) else None,
                "total_document": row.extracted_json.get("total_document") if isinstance(row.extracted_json, dict) else None,
                "status": "pending_review" if row.status in {"uploaded", "processing", "review_required"} else ("approved" if row.status == "validated" else row.status),
                "version": 1, "pending_fields": row.validation_errors_json or [], "source_filename": row.source_filename,
                "extraction_method": row.extraction_method or "xml", "extraction_error": row.extraction_error or ((row.validation_errors_json or [None])[0] if row.validation_errors_json else None),
                "financial_status": "linked" if self.db.query(FinanceObligation).filter(FinanceObligation.tenant_id == self.tenant_id, FinanceObligation.receipt_document_id == row.id).first() else "not_requested",
                "financial_transaction_ids": [], "lines": [{"id": l.id, "line_number": l.line_number, "supplier_code": l.supplier_code, "gtin": l.gtin,
                "description": l.description, "commercial_quantity": str(l.quantity), "commercial_unit": l.commercial_unit,
                "taxable_quantity": None, "taxable_unit": None, "unit_price": str(l.unit_price) if l.unit_price is not None else None,
                "total_price": str(l.total_price) if l.total_price is not None else None, "inventory_item_id": l.inventory_item_id,
                "pending_fields": ["inventory_item_id"] if l.association_status == "pending" else [],
                "association_status": "confirmed" if l.association_status == "matched" else ("unmatched" if l.association_status == "ignored" else "pending")} for l in row.lines],
                "created_at": row.created_at, "updated_at": row.updated_at}

    def list(self):
        return [self._out(r) for r in self.db.query(InventoryReceiptDocument).options(joinedload(InventoryReceiptDocument.lines)).filter(InventoryReceiptDocument.tenant_id == self.tenant_id).order_by(InventoryReceiptDocument.created_at.desc()).limit(300)]

    def get(self, document_id):
        row = self.db.query(InventoryReceiptDocument).options(joinedload(InventoryReceiptDocument.lines)).filter(InventoryReceiptDocument.tenant_id == self.tenant_id, InventoryReceiptDocument.id == document_id).first()
        if not row: raise ReceiptDocumentError("Documento de entrada nao encontrado.")
        return self._out(row)

    def upload(self, raw: bytes, idempotency_key: str | None, purchase_id: str | None = None,
               filename: str | None = None, mime_type: str | None = None):
        if not raw or len(raw) > 15 * 1024 * 1024:
            raise ReceiptDocumentError("Arquivo ausente ou acima do limite de 15 MiB.")
        mime = (mime_type or "").split(";", 1)[0].strip().lower()
        name = (filename or "documento").strip()[:255]
        is_xml = mime in {"", "application/xml", "text/xml"} or raw.lstrip().startswith(b"<")
        extraction_method = "xml"
        extraction_error = None
        if is_xml:
            try: identity = parse_receipt_xml(raw)
            except ReceiptXmlError as exc: raise ReceiptDocumentError(str(exc)) from exc
        else:
            if mime not in {"application/pdf", "image/jpeg", "image/png", "image/webp"}:
                raise ReceiptDocumentError("Formato aceito: XML, PDF, JPG, PNG ou WEBP.")
            extraction_method = "manual_review"
            extraction_error = "Documento não estruturado: revisão manual obrigatória antes da aprovação."
            digest = hashlib.sha256(raw).hexdigest()
            identity = SimpleNamespace(
                content_sha256=digest, document_model="NFe", access_key=None,
                series=None, number=None, issuer_document=None, issued_at=None,
                extracted={"source_format": mime, "source_filename": name, "ocr_status": "pending"},
            )
        q = self.db.query(InventoryReceiptDocument).filter(InventoryReceiptDocument.tenant_id == self.tenant_id)
        existing = q.filter((InventoryReceiptDocument.content_sha256 == identity.content_sha256) | (InventoryReceiptDocument.idempotency_key == idempotency_key)).first() if idempotency_key else q.filter(InventoryReceiptDocument.content_sha256 == identity.content_sha256).first()
        if existing: return self._out(existing)
        row = InventoryReceiptDocument(id=f"rec-{uuid.uuid4().hex[:14]}", tenant_id=self.tenant_id, purchase_id=purchase_id, document_model=identity.document_model,
            status="review_required", access_key=identity.access_key, series=identity.series, number=identity.number, issuer_document=identity.issuer_document,
            issued_at=identity.issued_at, content_sha256=identity.content_sha256, idempotency_key=idempotency_key,
            raw_xml=raw.decode("utf-8", errors="replace") if is_xml else None,
            raw_content=None if is_xml else raw, source_filename=name, source_mime_type=mime or "application/xml",
            extraction_method=extraction_method, extraction_error=extraction_error, extracted_json=identity.extracted)
        self.db.add(row); self.db.commit(); self.db.refresh(row); return self._out(row)

    def update(self, document_id, body):
        row = self.db.query(InventoryReceiptDocument).options(joinedload(InventoryReceiptDocument.lines)).filter(InventoryReceiptDocument.tenant_id == self.tenant_id, InventoryReceiptDocument.id == document_id).first()
        if not row: raise ReceiptDocumentError("Documento de entrada nao encontrado.")
        for item in body.get("lines", []):
            line = next((x for x in row.lines if x.id == item.get("id")), None)
            if line and item.get("inventory_item_id") is not None: line.inventory_item_id, line.association_status = item["inventory_item_id"], item.get("association_status", "matched")
        if body.get("purchase_id") is not None: row.purchase_id = body["purchase_id"]
        self.db.commit(); return self._out(row)

    def approve(self, document_id):
        row = self.db.query(InventoryReceiptDocument).filter(InventoryReceiptDocument.tenant_id == self.tenant_id, InventoryReceiptDocument.id == document_id).first()
        if not row: raise ReceiptDocumentError("Documento de entrada nao encontrado.")
        if self.db.query(InventoryReceiptDocumentLine).filter(InventoryReceiptDocumentLine.document_id == row.id, InventoryReceiptDocumentLine.association_status == "pending").first(): raise ReceiptDocumentError("Associe todas as linhas antes da aprovacao.")
        row.status = "validated"; self.db.commit(); return self.get(document_id)

    def reconcile(self, document_id, body, key):
        row = self.db.query(InventoryReceiptDocument).filter(InventoryReceiptDocument.tenant_id == self.tenant_id, InventoryReceiptDocument.id == document_id).first()
        if not row: raise ReceiptDocumentError("Documento de entrada nao encontrado.")
        if row.status != "validated": raise ReceiptDocumentError("O documento precisa ser aprovado antes da obrigacao financeira.")
        installments = body.get("installments") or []
        total = sum((Decimal(str(x["amount"])) for x in installments), Decimal("0"))
        if total <= 0: raise ReceiptDocumentError("Informe parcelas explicitas com valor positivo.")
        existing = self.db.query(FinanceObligation).filter(FinanceObligation.tenant_id == self.tenant_id, FinanceObligation.receipt_document_id == row.id).first()
        if existing: return {"document_id": row.id, "status": "linked", "transaction_ids": [], "obligation_total": str(existing.total_amount), "paid_total": "0"}
        ob = FinanceObligation(id=f"fin-obg-{uuid.uuid4().hex[:12]}", tenant_id=self.tenant_id, receipt_document_id=row.id, idempotency_key=key, total_amount=total, product_amount=total, status="pending", created_by_admin_id=self.admin_id)
        self.db.add(ob); self.db.flush(); txids=[]
        fs = FinanceService(self.db, self.tenant_id)
        for idx, item in enumerate(installments, 1):
            tx = FinanceTransaction(id=f"fin-trx-{uuid.uuid4().hex[:12]}", tenant_id=self.tenant_id, category_id=fs._ensure_category("Compras de estoque", "expense", "inventory_purchases"), counterparty_type="supplier", counterparty_name="Fornecedor", entry_type="expense", status="pending", description=f"Obrigacao NF-e {row.access_key or row.id}", amount=float(item["amount"]), due_date=item.get("due_date"), competence_date=item.get("due_date"), obligation_id=ob.id, origin_type="inventory_receipt_payable", origin_id=row.id, created_by_admin_id=self.admin_id)
            self.db.add(tx); self.db.flush(); txids.append(tx.id); self.db.add(FinanceObligationInstallment(id=f"fin-obg-itm-{uuid.uuid4().hex[:12]}", tenant_id=self.tenant_id, obligation_id=ob.id, finance_transaction_id=tx.id, installment_number=idx, amount=Decimal(str(item["amount"])), due_date=item.get("due_date")))
        self.db.commit(); return {"document_id": row.id, "status": "linked", "transaction_ids": txids, "obligation_total": str(total), "paid_total": "0"}
