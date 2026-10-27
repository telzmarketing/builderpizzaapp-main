"""Dedicated, permission-gated APIs for the two touch KDS stations."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.core.exceptions import DomainError
from backend.core.rbac_authorization import AuthorizedTenantActor, require_rbac_permission
from backend.core.response import err, ok
from backend.database import get_db
from backend.schemas.kds import DispatchAssignIn, DispatchUnitCompleteIn, DispatchReturnToKitchenIn, KdsOverviewEnvelope, KdsOverviewOut
from backend.services.kds_service import KdsService
from backend.services.kds_production_service import KdsProductionService
from backend.schemas.kds_production import KdsCommandIn, KdsCheckIn, KdsPresenceIn, KdsHeartbeatIn, KdsRedistributionIn


router = APIRouter(prefix="/kds", tags=["kds"])

def production(db, actor):
    return KdsProductionService(db, actor.tenant_context)

@router.get("/kitchen/my-queue")
def kitchen_my_queue(db: Session = Depends(get_db), actor: AuthorizedTenantActor = Depends(require_rbac_permission("cozinha", "view"))):
    service = production(db, actor)
    state = service.db.query(__import__('backend.models.kds_production', fromlist=['KdsOperatorState']).KdsOperatorState).filter_by(tenant_id=actor.tenant_id, user_id=actor.user_id, station_id="cozinha").first()
    tasks = service.queue(actor.user_id)
    presence = {"operator_id": actor.user_id, "operator_name": getattr(actor, "user_name", None) or actor.user_id, "state": state.requested_state if state else "offline", "station_id": "cozinha", "queue_count": len(tasks), "active_task_id": next((x["task_id"] for x in tasks if x["state"] == "assembling"), None), "updated_at": state.updated_at if state else service._now(), "version": state.version if state else 0}
    return ok({"generated_at": service._now(), "presence": presence, "tasks": tasks, "available_operators": []})

@router.get("/kitchen/queue")
def kitchen_queue(db: Session = Depends(get_db), actor: AuthorizedTenantActor = Depends(require_rbac_permission("cozinha", "view"))):
    return ok(production(db, actor).all_queued())

@router.post("/kitchen/orders/{order_id}/initialize")
def kitchen_initialize(order_id: str, db: Session = Depends(get_db), actor: AuthorizedTenantActor = Depends(require_rbac_permission("cozinha", "edit"))):
    try: return ok(production(db, actor).initialize_order(order_id, actor.user_id), status_code=201)
    except DomainError as exc: return err(exc)

@router.post("/kitchen/presence")
def kitchen_presence(body: KdsPresenceIn, db: Session = Depends(get_db), actor: AuthorizedTenantActor = Depends(require_rbac_permission("cozinha", "edit"))):
    try: return ok(production(db, actor).presence(actor.user_id, body))
    except DomainError as exc: return err(exc)

@router.post("/kitchen/heartbeat")
def kitchen_heartbeat(body: KdsHeartbeatIn, db: Session = Depends(get_db), actor: AuthorizedTenantActor = Depends(require_rbac_permission("cozinha", "edit"))):
    try: return ok(production(db, actor).heartbeat(actor.user_id, body))
    except DomainError as exc: return err(exc)

def _production_command(task_id, body, db, actor, command):
    try:
        return ok(production(db, actor).command(task_id, actor.user_id, body, command))
    except DomainError as exc: return err(exc)

@router.post("/kitchen/tasks/{task_id}/start")
def production_start(task_id: str, body: KdsCommandIn, db: Session = Depends(get_db), actor: AuthorizedTenantActor = Depends(require_rbac_permission("cozinha", "edit"))): return _production_command(task_id, body, db, actor, "start")
@router.post("/kitchen/tasks/{task_id}/confirm-stock")
def production_confirm_stock(task_id: str, body: KdsCommandIn, db: Session = Depends(get_db), actor: AuthorizedTenantActor = Depends(require_rbac_permission("cozinha", "edit"))): return _production_command(task_id, body, db, actor, "confirm-stock")
@router.post("/kitchen/tasks/{task_id}/return-to-service")
def production_return_service(task_id: str, body: KdsCommandIn, db: Session = Depends(get_db), actor: AuthorizedTenantActor = Depends(require_rbac_permission("cozinha", "edit"))): return _production_command(task_id, body, db, actor, "return-to-service")
@router.get("/kitchen/stock-alerts")
def production_stock_alerts(db: Session = Depends(get_db), actor: AuthorizedTenantActor = Depends(require_rbac_permission("pedidos", "view"))):
    return ok(production(db, actor).stock_alerts())
@router.post("/kitchen/tasks/{task_id}/finish-assembly")
def production_finish(task_id: str, body: KdsCommandIn, db: Session = Depends(get_db), actor: AuthorizedTenantActor = Depends(require_rbac_permission("cozinha", "edit"))): return _production_command(task_id, body, db, actor, "finish-assembly")
@router.post("/kitchen/tasks/{task_id}/start-oven")
def production_start_oven(task_id: str, body: KdsCommandIn, db: Session = Depends(get_db), actor: AuthorizedTenantActor = Depends(require_rbac_permission("cozinha", "edit"))): return _production_command(task_id, body, db, actor, "start-oven")
@router.post("/kitchen/tasks/{task_id}/complete-oven")
def production_complete_oven(task_id: str, body: KdsCommandIn, db: Session = Depends(get_db), actor: AuthorizedTenantActor = Depends(require_rbac_permission("cozinha", "edit"))): return _production_command(task_id, body, db, actor, "complete-oven")
@router.post("/kitchen/tasks/{task_id}/check")
def production_check(task_id: str, body: KdsCheckIn, db: Session = Depends(get_db), actor: AuthorizedTenantActor = Depends(require_rbac_permission("cozinha", "edit"))): return _production_command(task_id, body, db, actor, "check")
@router.post("/kitchen/tasks/{task_id}/remake")
def production_remake(task_id: str, body: KdsCommandIn, db: Session = Depends(get_db), actor: AuthorizedTenantActor = Depends(require_rbac_permission("cozinha", "edit"))):
    try: return ok(production(db, actor).remake(task_id, actor.user_id, body), status_code=201)
    except DomainError as exc: return err(exc)

@router.post("/management/redistributions")
def production_redistribute(body: KdsRedistributionIn, db: Session = Depends(get_db), actor: AuthorizedTenantActor = Depends(require_rbac_permission("cozinha", "manage"))):
    try: return ok(production(db, actor).redistribute(body, actor.user_id))
    except DomainError as exc: return err(exc)


@router.get("/overview", response_model=KdsOverviewEnvelope)
def overview(
    db: Session = Depends(get_db),
    actor: AuthorizedTenantActor = Depends(require_rbac_permission("pedidos", "view")),
):
    payload = KdsOverviewOut.model_validate(
        KdsService(db, actor.tenant_context).overview()
    )
    return ok(payload)


@router.get("/kitchen/orders")
def kitchen_orders(
    db: Session = Depends(get_db),
    actor: AuthorizedTenantActor = Depends(require_rbac_permission("cozinha", "view")),
):
    return ok(KdsService(db, actor.tenant_context).kitchen_orders())


@router.get("/kitchen/orders/{order_id}/composition")
def kitchen_order_composition(
    order_id: str,
    db: Session = Depends(get_db),
    actor: AuthorizedTenantActor = Depends(require_rbac_permission("cozinha", "view")),
):
    try:
        return ok(KdsService(db, actor.tenant_context).kitchen_order_composition(order_id))
    except DomainError as exc:
        return err(exc)


@router.post("/kitchen/orders/{order_id}/start")
def kitchen_start(
    order_id: str,
    db: Session = Depends(get_db),
    actor: AuthorizedTenantActor = Depends(require_rbac_permission("cozinha", "edit")),
):
    try:
        result = KdsService(db, actor.tenant_context).start_preparation(order_id, actor_id=actor.user_id)
        return ok(result, "Pedido enviado para preparacao.")
    except DomainError as exc:
        return err(exc)


@router.post("/kitchen/orders/{order_id}/ready")
def kitchen_ready(
    order_id: str,
    db: Session = Depends(get_db),
    actor: AuthorizedTenantActor = Depends(require_rbac_permission("cozinha", "edit")),
):
    try:
        result = KdsService(db, actor.tenant_context).mark_ready(order_id, actor_id=actor.user_id)
        return ok(result, "Pedido marcado como pronto.")
    except DomainError as exc:
        return err(exc)


@router.post("/kitchen/orders/{order_id}/pickup-complete")
def kitchen_pickup_complete(
    order_id: str,
    db: Session = Depends(get_db),
    actor: AuthorizedTenantActor = Depends(require_rbac_permission("cozinha", "edit")),
):
    try:
        result = KdsService(db, actor.tenant_context).complete_pickup(order_id, actor_id=actor.user_id)
        return ok(result, "Retirada concluida.")
    except DomainError as exc:
        return err(exc)


@router.get("/dispatch/orders")
def dispatch_orders(
    db: Session = Depends(get_db),
    actor: AuthorizedTenantActor = Depends(require_rbac_permission("expedicao", "view")),
):
    return ok(KdsService(db, actor.tenant_context).dispatch_orders())


@router.get("/dispatch/drivers")
def dispatch_drivers(
    db: Session = Depends(get_db),
    actor: AuthorizedTenantActor = Depends(require_rbac_permission("expedicao", "view")),
):
    return ok(KdsService(db, actor.tenant_context).available_drivers())


@router.post("/dispatch/orders/{order_id}/pickup-complete")
def dispatch_pickup_complete(
    order_id: str,
    db: Session = Depends(get_db),
    actor: AuthorizedTenantActor = Depends(require_rbac_permission("expedicao", "edit")),
):
    try:
        result = KdsService(db, actor.tenant_context).complete_pickup(
            order_id, actor_id=actor.user_id, audit_module="expedicao",
        )
        return ok(result, "Retirada concluida pela expedicao.")
    except DomainError as exc:
        return err(exc)


@router.post("/dispatch/orders/{order_id}/units/{unit_id}/complete")
def dispatch_unit_complete(
    order_id: str,
    unit_id: str,
    body: DispatchUnitCompleteIn,
    db: Session = Depends(get_db),
    actor: AuthorizedTenantActor = Depends(require_rbac_permission("expedicao", "edit")),
):
    try:
        result = KdsService(db, actor.tenant_context).complete_dispatch_unit(
            order_id, unit_id, expected_version=body.expected_version,
            actor_id=actor.user_id,
        )
        return ok(result, "Unidade concluida na expedicao.")
    except DomainError as exc:
        return err(exc)


@router.post("/dispatch/orders/{order_id}/return-to-kitchen")
def dispatch_return_to_kitchen(
    order_id: str,
    body: DispatchReturnToKitchenIn,
    db: Session = Depends(get_db),
    actor: AuthorizedTenantActor = Depends(require_rbac_permission("expedicao", "manage")),
):
    try:
        result = KdsService(db, actor.tenant_context).return_to_kitchen(
            order_id, body.production_unit_ids, reason=body.reason,
            actor_id=actor.user_id,
        )
        return ok(result, "Pedido devolvido para retrabalho na cozinha.")
    except DomainError as exc:
        return err(exc)


@router.post("/dispatch/orders/{order_id}/assign")
def dispatch_assign(
    order_id: str,
    body: DispatchAssignIn,
    db: Session = Depends(get_db),
    actor: AuthorizedTenantActor = Depends(require_rbac_permission("expedicao", "edit")),
):
    try:
        result = KdsService(db, actor.tenant_context).assign_driver(
            order_id, body.delivery_person_id,
            estimated_minutes=body.estimated_minutes, actor_id=actor.user_id,
        )
        return ok(result, "Motoboy atribuido; pedido aguarda inicio da rota.")
    except DomainError as exc:
        return err(exc)


@router.post("/kitchen/orders/{order_id}/serve")
def kitchen_serve(order_id: str, db: Session = Depends(get_db), actor: AuthorizedTenantActor = Depends(require_rbac_permission("cozinha", "edit"))):
    try:
        return ok(KdsService(db, actor.tenant_context).serve_dine_in(order_id, actor_id=actor.user_id), "Pedido servido.")
    except DomainError as exc:
        return err(exc)
