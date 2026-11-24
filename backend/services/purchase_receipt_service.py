from __future__ import annotations
import uuid
from decimal import Decimal
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func
from backend.core.exceptions import DomainError
from backend.core.tenant_context import TenantContext
from backend.models.inventory import InventoryPurchase, InventoryPurchaseItem, InventoryStockMovement
from backend.models.inventory_receipts import InventoryReceiptDocument
from backend.models.inventory_foundation import InventoryLot
from backend.schemas.inventory_foundation import OperationIn, MovementLine
from backend.services.inventory_foundation_service import InventoryFoundationService
from backend.models.purchase_receipt import PurchaseReceipt, PurchaseReceiptItem
from backend.schemas.purchase_receipt import PurchaseReceiptCreate, PurchaseReceiptTransition
from backend.services.idempotency_service import IdempotencyService

class PurchaseReceiptConflict(DomainError):
    http_status=409
class PurchaseReceiptNotFound(DomainError):
    http_status=404
    def __init__(self): super().__init__("Recebimento nao encontrado.",code="PurchaseReceiptNotFound")

class PurchaseReceiptService:
    def __init__(self,db:Session,actor_id:str,context:TenantContext): self.db,self.actor_id,self.tenant_id=db,actor_id,context.tenant_id
    def list(self): return [self._out(x) for x in self._query().order_by(PurchaseReceipt.created_at.desc()).limit(300).all()]
    def get(self,id):
        row=self._query().filter(PurchaseReceipt.id==id).first()
        if not row: raise PurchaseReceiptNotFound()
        return self._out(row)
    def create(self,body:PurchaseReceiptCreate,key:str):
        claim=IdempotencyService(self.db,self.tenant_id).claim(key,"purchase_receipt_create",body.model_dump(mode="json"))
        if claim.replay_resource_id:return self.get(claim.replay_resource_id)
        try:
            purchase=self.db.query(InventoryPurchase).filter(InventoryPurchase.tenant_id==self.tenant_id,InventoryPurchase.id==body.purchase_id).first()
            if not purchase or purchase.status != "confirmed": raise PurchaseReceiptConflict("Somente pedidos confirmados podem receber mercadoria.",code="ReceiptPurchaseInvalid")
            if body.document_id:
                document=self.db.query(InventoryReceiptDocument).filter(InventoryReceiptDocument.tenant_id==self.tenant_id,InventoryReceiptDocument.id==body.document_id).first()
                if not document or document.purchase_id != purchase.id or document.status != "validated": raise PurchaseReceiptConflict("O documento fiscal deve estar validado e vinculado ao pedido.",code="ReceiptDocumentInvalid")
            allowed={item.id:(item.item_id,Decimal(str(item.quantity))) for item in purchase.items}; received_ids={item.purchase_item_id for item in body.items}
            if received_ids-allowed.keys(): raise PurchaseReceiptConflict("O recebimento contem linha fora do pedido.",code="ReceiptItemInvalid")
            prior_rows=self.db.query(PurchaseReceiptItem.purchase_item_id,func.coalesce(func.sum(PurchaseReceiptItem.quantity_received),0)).join(PurchaseReceipt,PurchaseReceipt.id==PurchaseReceiptItem.receipt_id).filter(PurchaseReceipt.tenant_id==self.tenant_id,PurchaseReceipt.purchase_id==purchase.id,PurchaseReceipt.status=="posted").group_by(PurchaseReceiptItem.purchase_item_id).all()
            already={item_id:Decimal(str(total)) for item_id,total in prior_rows}
            for item in body.items:
                if item.quantity_rejected>item.quantity_received: raise PurchaseReceiptConflict("Quantidade recusada nao pode exceder quantidade recebida.",code="ReceiptRejectedQuantityInvalid")
                purchase_item_id,ordered_quantity=allowed[item.purchase_item_id]
                if item.item_id != purchase_item_id: raise PurchaseReceiptConflict("O insumo nao corresponde a linha do pedido.",code="ReceiptItemInvalid")
                if already.get(item.purchase_item_id,Decimal("0"))+item.quantity_received>ordered_quantity: raise PurchaseReceiptConflict("Quantidade recebida excede o saldo autorizado do pedido.",code="ReceiptOverage")
                if item.manufactured_on and item.expires_on and item.manufactured_on>item.expires_on: raise PurchaseReceiptConflict("Fabricacao nao pode ser posterior a validade.",code="ReceiptLotDatesInvalid")
            row=PurchaseReceipt(id=f"prc-{uuid.uuid4().hex[:14]}",tenant_id=self.tenant_id,purchase_id=body.purchase_id,document_id=body.document_id,notes=body.notes,received_by_admin_id=self.actor_id)
            self.db.add(row);self.db.flush()
            for pos,item in enumerate(body.items): row.items.append(PurchaseReceiptItem(id=f"prci-{uuid.uuid4().hex[:14]}",tenant_id=self.tenant_id,purchase_item_id=item.purchase_item_id,item_id=item.item_id,location_id=item.location_id,quantity_received=item.quantity_received,quantity_rejected=item.quantity_rejected,unit_cost=item.unit_cost,lot_code=item.lot_code,manufactured_on=item.manufactured_on,expires_on=item.expires_on,temperature_c=item.temperature_c,quality_status=item.quality_status,inspection_notes=item.inspection_notes,position=pos))
            IdempotencyService(self.db,self.tenant_id).complete(claim.record,row.id,commit=False);self.db.commit();return self.get(row.id)
        except Exception: IdempotencyService(self.db,self.tenant_id).abandon(claim.record);raise
    def submit(self,id,body:PurchaseReceiptTransition,key:str): return self._transition(id,"submit",body,key)
    def post(self,id,body:PurchaseReceiptTransition,key:str): return self._transition(id,"post",body,key)
    def _transition(self,id,action,body,key):
        claim=IdempotencyService(self.db,self.tenant_id).claim(key,"purchase_receipt_transition",{"id":id,"action":action,**body.model_dump(mode="json")})
        if claim.replay_resource_id:return self.get(claim.replay_resource_id)
        try:
            row=self._query().filter(PurchaseReceipt.id==id).with_for_update().first()
            if not row:raise PurchaseReceiptNotFound()
            if row.version!=body.expected_version:raise PurchaseReceiptConflict("O recebimento foi alterado por outro usuario.",code="ReceiptVersionConflict")
            target={"submit":{"draft":"submitted"},"post":{"submitted":"posted"}}.get(action,{}).get(row.status)
            if not target:raise PurchaseReceiptConflict("Transicao de recebimento nao permitida.",code="ReceiptInvalidTransition")
            if action=="post":self._post_stock(row)
            row.status=target;row.version+=1
            if body.reason:row.notes=f"{row.notes or ''}\n{body.reason}".strip()
            self.db.commit();IdempotencyService(self.db,self.tenant_id).complete(claim.record,row.id);return self.get(row.id)
        except Exception:IdempotencyService(self.db,self.tenant_id).abandon(claim.record);raise
    def _post_stock(self,row):
        movement_lines=[]
        for line in row.items:
            accepted=Decimal(line.quantity_received)-Decimal(line.quantity_rejected)
            if accepted<=0:continue
            lot_id=None
            if line.lot_code:
                lot=self.db.query(InventoryLot).filter(InventoryLot.tenant_id==self.tenant_id,InventoryLot.item_id==line.item_id,InventoryLot.location_id==line.location_id,InventoryLot.lot_code==line.lot_code,InventoryLot.status.in_(["available","quarantine"])).first()
                if not lot:
                    lot=InventoryLot(id=f"lot-{uuid.uuid4().hex[:14]}",tenant_id=self.tenant_id,item_id=line.item_id,location_id=line.location_id,supplier_id=row.purchase.supplier_id,lot_code=line.lot_code,manufactured_on=line.manufactured_on,expires_on=line.expires_on,status="quarantine" if line.quality_status=="quarantine" else "available",actor_id=self.actor_id);self.db.add(lot);self.db.flush()
                lot_id=lot.id
            movement_lines.append(MovementLine(item_id=line.item_id, quantity=str(accepted), unit_id=line.item.unit_id, location_id=line.location_id, lot_id=lot_id, unit_cost=str(line.unit_cost)))
        if movement_lines:
            body=OperationIn(expected_version=0, kind="receipt", business_key=f"purchase_receipt:{row.id}", reason="purchase_receipt", lines=movement_lines)
            return InventoryFoundationService(self.db,self.tenant_id,self.actor_id).create_operation_in_transaction(body,row.id)
        return None
    def _query(self):return self.db.query(PurchaseReceipt).options(joinedload(PurchaseReceipt.items).joinedload(PurchaseReceiptItem.item)).filter(PurchaseReceipt.tenant_id==self.tenant_id)
    @staticmethod
    def _out(row):return {"id":row.id,"tenant_id":row.tenant_id,"purchase_id":row.purchase_id,"document_id":row.document_id,"status":row.status,"received_at":row.received_at,"notes":row.notes,"version":row.version,"received_by_admin_id":row.received_by_admin_id,"created_at":row.created_at,"updated_at":row.updated_at,"items":[{"id":i.id,"purchase_item_id":i.purchase_item_id,"item_id":i.item_id,"item_name":i.item.name,"location_id":i.location_id,"quantity_received":i.quantity_received,"quantity_rejected":i.quantity_rejected,"unit_cost":i.unit_cost,"lot_code":i.lot_code,"manufactured_on":i.manufactured_on,"expires_on":i.expires_on,"temperature_c":i.temperature_c,"quality_status":i.quality_status,"inspection_notes":i.inspection_notes} for i in row.items]}
