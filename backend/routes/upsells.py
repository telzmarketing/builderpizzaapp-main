from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.core.response import ok, created
from backend.database import get_db
from backend.routes.admin_auth import get_current_admin
from backend.core.tenant_context import TenantContext
from backend.core.tenant_route_context import operation_tenant_id, panel_operation_context, public_operation_context
from backend.schemas.upsell import (
    UpsellEligibleIn,
    UpsellEventIn,
    UpsellIn,
    UpsellMetricsSummary,
    UpsellOut,
)
from backend.services.upsell_engine import UpsellEngine

router = APIRouter(prefix="/upsells", tags=["upsells"])


def _engine(db: Session, tenant_id: str | None = None) -> UpsellEngine:
    return UpsellEngine(db, tenant_id)


# ── Public endpoints ──────────────────────────────────────────────────────────

@router.post("/eligible", response_model=list[UpsellOut])
def get_eligible(body: UpsellEligibleIn, db: Session = Depends(get_db), context: TenantContext | None = Depends(public_operation_context)):
    """Engine: retorna upsells elegíveis para o carrinho informado."""
    return _engine(db, operation_tenant_id(context)).get_eligible(body.cart_items, body.cart_total)


@router.post("/events")
def log_event(body: UpsellEventIn, db: Session = Depends(get_db), context: TenantContext | None = Depends(public_operation_context)):
    """Registra evento de upsell (viewed / accepted / rejected)."""
    _engine(db, operation_tenant_id(context)).log_event(body)
    return ok({"recorded": True})


# ── Admin endpoints ───────────────────────────────────────────────────────────

@router.get("", response_model=list[UpsellOut])
def list_upsells(db: Session = Depends(get_db), _=Depends(get_current_admin), context: TenantContext | None = Depends(panel_operation_context)):
    return _engine(db, operation_tenant_id(context)).list_upsells()


@router.post("", response_model=UpsellOut, status_code=201)
def create_upsell(body: UpsellIn, db: Session = Depends(get_db), _=Depends(get_current_admin), context: TenantContext | None = Depends(panel_operation_context)):
    try:
        return _engine(db, operation_tenant_id(context)).create_upsell(body)
    except UpsellEngine.ValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/metrics", response_model=UpsellMetricsSummary)
def metrics(db: Session = Depends(get_db), _=Depends(get_current_admin), context: TenantContext | None = Depends(panel_operation_context)):
    return _engine(db, operation_tenant_id(context)).metrics_summary()


@router.get("/{upsell_id}", response_model=UpsellOut)
def get_upsell(upsell_id: str, db: Session = Depends(get_db), _=Depends(get_current_admin), context: TenantContext | None = Depends(panel_operation_context)):
    result = _engine(db, operation_tenant_id(context)).get_upsell(upsell_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Upsell nao encontrado.")
    return result


@router.put("/{upsell_id}", response_model=UpsellOut)
def update_upsell(upsell_id: str, body: UpsellIn, db: Session = Depends(get_db), _=Depends(get_current_admin), context: TenantContext | None = Depends(panel_operation_context)):
    result = _engine(db, operation_tenant_id(context)).update_upsell(upsell_id, body)
    if result is None:
        raise HTTPException(status_code=404, detail="Upsell nao encontrado.")
    return result


@router.patch("/{upsell_id}/toggle", response_model=UpsellOut)
def toggle_upsell(upsell_id: str, db: Session = Depends(get_db), _=Depends(get_current_admin), context: TenantContext | None = Depends(panel_operation_context)):
    result = _engine(db, operation_tenant_id(context)).toggle_upsell(upsell_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Upsell nao encontrado.")
    return result


@router.delete("/{upsell_id}")
def delete_upsell(upsell_id: str, db: Session = Depends(get_db), _=Depends(get_current_admin), context: TenantContext | None = Depends(panel_operation_context)):
    deleted = _engine(db, operation_tenant_id(context)).delete_upsell(upsell_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Upsell nao encontrado.")
    return ok({"deleted": True})


@router.post("/reorder")
def reorder(body: list[str], db: Session = Depends(get_db), _=Depends(get_current_admin), context: TenantContext | None = Depends(panel_operation_context)):
    """Recebe lista ordenada de IDs e atualiza prioridades."""
    _engine(db, operation_tenant_id(context)).reorder(body)
    return ok({"reordered": True})
