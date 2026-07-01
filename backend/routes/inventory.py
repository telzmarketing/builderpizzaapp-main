from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.core.exceptions import DomainError
from backend.core.response import err, no_content
from backend.database import get_db
from backend.models.admin import AdminUser
from backend.routes.admin_auth import get_current_admin
from backend.schemas.inventory import (
    InventoryCategoryIn,
    InventoryCategoryOut,
    InventoryItemIn,
    InventoryItemOut,
    InventoryLocationIn,
    InventoryLocationOut,
    InventoryManualEntryIn,
    InventoryManualEntryOut,
    InventoryOverviewOut,
    InventoryPurchaseIn,
    InventoryPurchaseOut,
    InventoryRecipeVersionIn,
    InventoryRecipeVersionOut,
    InventoryStockBalanceOut,
    InventoryStockMovementOut,
    InventorySupplierIn,
    InventorySupplierOut,
    InventoryUnitIn,
    InventoryUnitOut,
)
from backend.services.inventory_service import InventoryService

router = APIRouter(prefix="/gestao/inventory", tags=["gestao-inventory"])


def service(db: Session) -> InventoryService:
    return InventoryService(db)


@router.get("/overview", response_model=InventoryOverviewOut)
def overview(db: Session = Depends(get_db), _admin: AdminUser = Depends(get_current_admin)):
    return service(db).overview()


@router.get("/units", response_model=list[InventoryUnitOut])
def list_units(db: Session = Depends(get_db), _admin: AdminUser = Depends(get_current_admin)):
    return service(db).list_units()


@router.post("/units", response_model=InventoryUnitOut, status_code=201)
def create_unit(body: InventoryUnitIn, db: Session = Depends(get_db), _admin: AdminUser = Depends(get_current_admin)):
    return service(db).create_unit(body)


@router.put("/units/{item_id}", response_model=InventoryUnitOut)
def update_unit(item_id: str, body: InventoryUnitIn, db: Session = Depends(get_db), _admin: AdminUser = Depends(get_current_admin)):
    try:
        return service(db).update_unit(item_id, body)
    except DomainError as exc:
        return err(exc)


@router.delete("/units/{item_id}", status_code=204)
def delete_unit(item_id: str, db: Session = Depends(get_db), _admin: AdminUser = Depends(get_current_admin)):
    try:
        service(db).delete_unit(item_id)
        return no_content()
    except DomainError as exc:
        return err(exc)


@router.get("/categories", response_model=list[InventoryCategoryOut])
def list_categories(db: Session = Depends(get_db), _admin: AdminUser = Depends(get_current_admin)):
    return service(db).list_categories()


@router.post("/categories", response_model=InventoryCategoryOut, status_code=201)
def create_category(body: InventoryCategoryIn, db: Session = Depends(get_db), _admin: AdminUser = Depends(get_current_admin)):
    return service(db).create_category(body)


@router.put("/categories/{item_id}", response_model=InventoryCategoryOut)
def update_category(item_id: str, body: InventoryCategoryIn, db: Session = Depends(get_db), _admin: AdminUser = Depends(get_current_admin)):
    try:
        return service(db).update_category(item_id, body)
    except DomainError as exc:
        return err(exc)


@router.delete("/categories/{item_id}", status_code=204)
def delete_category(item_id: str, db: Session = Depends(get_db), _admin: AdminUser = Depends(get_current_admin)):
    try:
        service(db).delete_category(item_id)
        return no_content()
    except DomainError as exc:
        return err(exc)


@router.get("/locations", response_model=list[InventoryLocationOut])
def list_locations(db: Session = Depends(get_db), _admin: AdminUser = Depends(get_current_admin)):
    return service(db).list_locations()


@router.post("/locations", response_model=InventoryLocationOut, status_code=201)
def create_location(body: InventoryLocationIn, db: Session = Depends(get_db), _admin: AdminUser = Depends(get_current_admin)):
    return service(db).create_location(body)


@router.put("/locations/{item_id}", response_model=InventoryLocationOut)
def update_location(item_id: str, body: InventoryLocationIn, db: Session = Depends(get_db), _admin: AdminUser = Depends(get_current_admin)):
    try:
        return service(db).update_location(item_id, body)
    except DomainError as exc:
        return err(exc)


@router.delete("/locations/{item_id}", status_code=204)
def delete_location(item_id: str, db: Session = Depends(get_db), _admin: AdminUser = Depends(get_current_admin)):
    try:
        service(db).delete_location(item_id)
        return no_content()
    except DomainError as exc:
        return err(exc)


@router.get("/suppliers", response_model=list[InventorySupplierOut])
def list_suppliers(db: Session = Depends(get_db), _admin: AdminUser = Depends(get_current_admin)):
    return service(db).list_suppliers()


@router.post("/suppliers", response_model=InventorySupplierOut, status_code=201)
def create_supplier(body: InventorySupplierIn, db: Session = Depends(get_db), _admin: AdminUser = Depends(get_current_admin)):
    return service(db).create_supplier(body)


@router.put("/suppliers/{item_id}", response_model=InventorySupplierOut)
def update_supplier(item_id: str, body: InventorySupplierIn, db: Session = Depends(get_db), _admin: AdminUser = Depends(get_current_admin)):
    try:
        return service(db).update_supplier(item_id, body)
    except DomainError as exc:
        return err(exc)


@router.delete("/suppliers/{item_id}", status_code=204)
def delete_supplier(item_id: str, db: Session = Depends(get_db), _admin: AdminUser = Depends(get_current_admin)):
    try:
        service(db).delete_supplier(item_id)
        return no_content()
    except DomainError as exc:
        return err(exc)


@router.get("/items", response_model=list[InventoryItemOut])
def list_items(db: Session = Depends(get_db), _admin: AdminUser = Depends(get_current_admin)):
    return service(db).list_items()


@router.post("/items", response_model=InventoryItemOut, status_code=201)
def create_item(body: InventoryItemIn, db: Session = Depends(get_db), _admin: AdminUser = Depends(get_current_admin)):
    try:
        return service(db).create_item(body)
    except DomainError as exc:
        return err(exc)


@router.put("/items/{item_id}", response_model=InventoryItemOut)
def update_item(item_id: str, body: InventoryItemIn, db: Session = Depends(get_db), _admin: AdminUser = Depends(get_current_admin)):
    try:
        return service(db).update_item(item_id, body)
    except DomainError as exc:
        return err(exc)


@router.delete("/items/{item_id}", status_code=204)
def delete_item(item_id: str, db: Session = Depends(get_db), _admin: AdminUser = Depends(get_current_admin)):
    try:
        service(db).delete_item(item_id)
        return no_content()
    except DomainError as exc:
        return err(exc)


@router.get("/purchases", response_model=list[InventoryPurchaseOut])
def list_purchases(db: Session = Depends(get_db), _admin: AdminUser = Depends(get_current_admin)):
    return service(db).list_purchases()


@router.post("/purchases", response_model=InventoryPurchaseOut, status_code=201)
def create_purchase(body: InventoryPurchaseIn, db: Session = Depends(get_db), _admin: AdminUser = Depends(get_current_admin)):
    try:
        return service(db).create_purchase(body)
    except DomainError as exc:
        return err(exc)


@router.put("/purchases/{purchase_id}", response_model=InventoryPurchaseOut)
def update_purchase(purchase_id: str, body: InventoryPurchaseIn, db: Session = Depends(get_db), _admin: AdminUser = Depends(get_current_admin)):
    try:
        return service(db).update_purchase(purchase_id, body)
    except DomainError as exc:
        return err(exc)


@router.delete("/purchases/{purchase_id}", status_code=204)
def delete_purchase(purchase_id: str, db: Session = Depends(get_db), _admin: AdminUser = Depends(get_current_admin)):
    try:
        service(db).delete_purchase(purchase_id)
        return no_content()
    except DomainError as exc:
        return err(exc)


@router.get("/manual-entries", response_model=list[InventoryManualEntryOut])
def list_manual_entries(db: Session = Depends(get_db), _admin: AdminUser = Depends(get_current_admin)):
    return service(db).list_manual_entries()


@router.post("/manual-entries", response_model=InventoryManualEntryOut, status_code=201)
def create_manual_entry(body: InventoryManualEntryIn, db: Session = Depends(get_db), _admin: AdminUser = Depends(get_current_admin)):
    try:
        return service(db).create_manual_entry(body)
    except DomainError as exc:
        return err(exc)


@router.delete("/manual-entries/{entry_id}", status_code=204)
def delete_manual_entry(entry_id: str, db: Session = Depends(get_db), _admin: AdminUser = Depends(get_current_admin)):
    try:
        service(db).delete_manual_entry(entry_id)
        return no_content()
    except DomainError as exc:
        return err(exc)


@router.get("/movements", response_model=list[InventoryStockMovementOut])
def list_movements(db: Session = Depends(get_db), _admin: AdminUser = Depends(get_current_admin)):
    return service(db).list_movements()


@router.get("/balances", response_model=list[InventoryStockBalanceOut])
def list_balances(db: Session = Depends(get_db), _admin: AdminUser = Depends(get_current_admin)):
    return service(db).list_balances()


@router.get("/products/{product_id}/recipes", response_model=list[InventoryRecipeVersionOut])
def list_product_recipes(product_id: str, db: Session = Depends(get_db), _admin: AdminUser = Depends(get_current_admin)):
    try:
        return service(db).list_product_recipes(product_id)
    except DomainError as exc:
        return err(exc)


@router.post("/products/{product_id}/recipes", response_model=InventoryRecipeVersionOut, status_code=201)
def create_product_recipe(product_id: str, body: InventoryRecipeVersionIn, db: Session = Depends(get_db), _admin: AdminUser = Depends(get_current_admin)):
    try:
        return service(db).create_product_recipe(product_id, body)
    except DomainError as exc:
        return err(exc)


@router.put("/products/{product_id}/recipes/{recipe_id}", response_model=InventoryRecipeVersionOut)
def update_product_recipe(product_id: str, recipe_id: str, body: InventoryRecipeVersionIn, db: Session = Depends(get_db), _admin: AdminUser = Depends(get_current_admin)):
    try:
        return service(db).update_product_recipe(product_id, recipe_id, body)
    except DomainError as exc:
        return err(exc)


@router.delete("/products/{product_id}/recipes/{recipe_id}", status_code=204)
def delete_product_recipe(product_id: str, recipe_id: str, db: Session = Depends(get_db), _admin: AdminUser = Depends(get_current_admin)):
    try:
        service(db).delete_product_recipe(product_id, recipe_id)
        return no_content()
    except DomainError as exc:
        return err(exc)
