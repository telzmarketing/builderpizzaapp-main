from datetime import date, datetime
from decimal import Decimal
from pydantic import BaseModel, Field, model_validator
class PurchaseReceiptItemCreate(BaseModel):
    purchase_item_id:str; item_id:str; location_id:str; quantity_received:Decimal=Field(gt=0); quantity_rejected:Decimal=Field(default=Decimal("0"),ge=0); unit_cost:Decimal=Field(default=Decimal("0"),ge=0); lot_code:str|None=None; manufactured_on:date|None=None; expires_on:date|None=None; temperature_c:Decimal|None=None; quality_status:str="accepted"; inspection_notes:str|None=None
    @model_validator(mode="after")
    def validate_receipt_line(self):
        if self.quantity_rejected > self.quantity_received:
            raise ValueError("quantity_rejected cannot exceed quantity_received")
        if self.manufactured_on and self.expires_on and self.manufactured_on > self.expires_on:
            raise ValueError("manufactured_on cannot be after expires_on")
        if self.quality_status not in {"accepted", "quarantine", "rejected"}:
            raise ValueError("invalid quality_status")
        return self
class PurchaseReceiptCreate(BaseModel):
    purchase_id:str; document_id:str|None=None; notes:str|None=None; items:list[PurchaseReceiptItemCreate]=Field(min_length=1)
class PurchaseReceiptTransition(BaseModel): expected_version:int=Field(gt=0); reason:str|None=None
class PurchaseReceiptItemOut(BaseModel): id:str;purchase_item_id:str;item_id:str;item_name:str;location_id:str;quantity_received:Decimal;quantity_rejected:Decimal;unit_cost:Decimal;lot_code:str|None;manufactured_on:date|None;expires_on:date|None;temperature_c:Decimal|None;quality_status:str;inspection_notes:str|None
class PurchaseReceiptOut(BaseModel): id:str;tenant_id:str;purchase_id:str;document_id:str|None;status:str;received_at:datetime;notes:str|None;version:int;received_by_admin_id:str;created_at:datetime;updated_at:datetime;items:list[PurchaseReceiptItemOut]
