"""Thin RBAC-gated routes for dispatch label configuration and printing."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.core.exceptions import DomainError
from backend.core.rbac_authorization import AuthorizedTenantActor, require_rbac_permission
from backend.core.response import created, err, ok
from backend.database import get_db
from backend.schemas.label import (
    LabelPrinterIn, LabelPrintIn, LabelReprintIn, LabelSettingsIn,
    LabelTemplateIn, LabelTestIn, LabelVolumeRuleIn,
)
from backend.services.label_service import LabelService


router = APIRouter(prefix="/kds/dispatch", tags=["dispatch-labels"])


def _service(db, actor):
    return LabelService(db, actor.tenant_context)


@router.get("/label-printers")
def list_printers(db: Session = Depends(get_db), actor: AuthorizedTenantActor = Depends(require_rbac_permission("expedicao", "view"))):
    return ok(_service(db, actor).list_printers())


@router.post("/label-printers")
def create_printer(body: LabelPrinterIn, db: Session = Depends(get_db), actor: AuthorizedTenantActor = Depends(require_rbac_permission("expedicao", "edit"))):
    try: return created(_service(db, actor).save_printer(body))
    except DomainError as exc: return err(exc)


@router.put("/label-printers/{printer_id}")
def update_printer(printer_id: str, body: LabelPrinterIn, db: Session = Depends(get_db), actor: AuthorizedTenantActor = Depends(require_rbac_permission("expedicao", "edit"))):
    try: return ok(_service(db, actor).save_printer(body, printer_id))
    except DomainError as exc: return err(exc)


@router.delete("/label-printers/{printer_id}")
def delete_printer(printer_id: str, db: Session = Depends(get_db), actor: AuthorizedTenantActor = Depends(require_rbac_permission("expedicao", "edit"))):
    try: return ok(_service(db, actor).delete_printer(printer_id))
    except DomainError as exc: return err(exc)


@router.get("/label-templates")
def list_templates(db: Session = Depends(get_db), actor: AuthorizedTenantActor = Depends(require_rbac_permission("expedicao", "view"))):
    return ok(_service(db, actor).list_templates())


@router.post("/label-templates")
def create_template(body: LabelTemplateIn, db: Session = Depends(get_db), actor: AuthorizedTenantActor = Depends(require_rbac_permission("expedicao", "edit"))):
    try: return created(_service(db, actor).save_template(body))
    except DomainError as exc: return err(exc)


@router.put("/label-templates/{template_id}")
def update_template(template_id: str, body: LabelTemplateIn, db: Session = Depends(get_db), actor: AuthorizedTenantActor = Depends(require_rbac_permission("expedicao", "edit"))):
    try: return ok(_service(db, actor).save_template(body, template_id))
    except DomainError as exc: return err(exc)


@router.delete("/label-templates/{template_id}")
def delete_template(template_id: str, db: Session = Depends(get_db), actor: AuthorizedTenantActor = Depends(require_rbac_permission("expedicao", "edit"))):
    try: return ok(_service(db, actor).delete_template(template_id))
    except DomainError as exc: return err(exc)


@router.get("/label-settings")
def get_settings(db: Session = Depends(get_db), actor: AuthorizedTenantActor = Depends(require_rbac_permission("expedicao", "view"))):
    return ok(_service(db, actor).get_settings())


@router.put("/label-settings")
def update_settings(body: LabelSettingsIn, db: Session = Depends(get_db), actor: AuthorizedTenantActor = Depends(require_rbac_permission("expedicao", "edit"))):
    try: return ok(_service(db, actor).save_settings(body))
    except DomainError as exc: return err(exc)


@router.get("/label-volume-rules")
def list_rules(db: Session = Depends(get_db), actor: AuthorizedTenantActor = Depends(require_rbac_permission("expedicao", "view"))):
    return ok(_service(db, actor).list_rules())


@router.post("/label-volume-rules")
def create_rule(body: LabelVolumeRuleIn, db: Session = Depends(get_db), actor: AuthorizedTenantActor = Depends(require_rbac_permission("expedicao", "edit"))):
    try: return created(_service(db, actor).save_rule(body))
    except DomainError as exc: return err(exc)


@router.put("/label-volume-rules/{rule_id}")
def update_rule(rule_id: str, body: LabelVolumeRuleIn, db: Session = Depends(get_db), actor: AuthorizedTenantActor = Depends(require_rbac_permission("expedicao", "edit"))):
    try: return ok(_service(db, actor).save_rule(body, rule_id))
    except DomainError as exc: return err(exc)


@router.delete("/label-volume-rules/{rule_id}")
def delete_rule(rule_id: str, db: Session = Depends(get_db), actor: AuthorizedTenantActor = Depends(require_rbac_permission("expedicao", "edit"))):
    try: return ok(_service(db, actor).delete_rule(rule_id))
    except DomainError as exc: return err(exc)


@router.get("/orders/{order_id}/labels/preview")
def preview(order_id: str, printer_id: str | None = Query(default=None), template_id: str | None = Query(default=None), db: Session = Depends(get_db), actor: AuthorizedTenantActor = Depends(require_rbac_permission("expedicao", "view"))):
    try: return ok(_service(db, actor).preview(order_id, printer_id=printer_id, template_id=template_id))
    except DomainError as exc: return err(exc)


@router.post("/orders/{order_id}/labels/print")
def request_print(order_id: str, body: LabelPrintIn, db: Session = Depends(get_db), actor: AuthorizedTenantActor = Depends(require_rbac_permission("expedicao", "edit"))):
    try: return created(_service(db, actor).request_print(order_id, body, actor_id=actor.user_id, reprint=False))
    except DomainError as exc: return err(exc)


@router.post("/orders/{order_id}/labels/reprint")
def request_reprint(order_id: str, body: LabelReprintIn, db: Session = Depends(get_db), actor: AuthorizedTenantActor = Depends(require_rbac_permission("expedicao", "edit"))):
    try: return created(_service(db, actor).request_print(order_id, body, actor_id=actor.user_id, reprint=True))
    except DomainError as exc: return err(exc)


@router.get("/orders/{order_id}/labels/history")
def history(order_id: str, db: Session = Depends(get_db), actor: AuthorizedTenantActor = Depends(require_rbac_permission("expedicao", "view"))):
    try: return ok(_service(db, actor).history(order_id))
    except DomainError as exc: return err(exc)


@router.post("/labels/test")
def test_label(body: LabelTestIn, db: Session = Depends(get_db), actor: AuthorizedTenantActor = Depends(require_rbac_permission("expedicao", "edit"))):
    try: return created(_service(db, actor).request_test(body, actor_id=actor.user_id))
    except DomainError as exc: return err(exc)


@router.post("/label-jobs/{job_id}/dialog-opened")
def dialog_opened(job_id: str, db: Session = Depends(get_db), actor: AuthorizedTenantActor = Depends(require_rbac_permission("expedicao", "edit"))):
    try: return ok(_service(db, actor).mark_dialog_opened(job_id, actor_id=actor.user_id))
    except DomainError as exc: return err(exc)
