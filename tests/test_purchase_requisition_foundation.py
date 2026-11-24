from datetime import date
from decimal import Decimal

import pytest

from backend.models.purchase_requisition import PurchaseRequisition, PurchaseRequisitionEvent, PurchaseRequisitionItem
from backend.schemas.purchase_requisition import PurchaseRequisitionCreate, PurchaseRequisitionTransitionIn
from backend.services.purchase_requisition_service import PurchaseRequisitionService


def test_requisition_schema_requires_positive_items_and_preserves_decimal():
    body = PurchaseRequisitionCreate(
        priority="urgent",
        needed_by=date(2026, 12, 1),
        items=[{"item_id": "item-a", "unit_id": "unit-kg", "quantity": "2.500000"}],
    )
    assert body.items[0].quantity == Decimal("2.500000")
    with pytest.raises(ValueError):
        PurchaseRequisitionCreate(items=[])
    with pytest.raises(ValueError):
        PurchaseRequisitionCreate(items=[{"item_id": "item-a", "unit_id": "unit-kg", "quantity": "0"}])


def test_transition_contract_contains_no_direct_approval_from_draft():
    assert PurchaseRequisitionService.TRANSITIONS["draft"] == {"submit": "submitted", "cancel": "cancelled"}
    assert PurchaseRequisitionService.TRANSITIONS["submitted"]["approve"] == "approved"
    assert "approve" not in PurchaseRequisitionService.TRANSITIONS["draft"]


def test_transition_payload_requires_optimistic_version():
    assert PurchaseRequisitionTransitionIn(expected_version=1).expected_version == 1
    with pytest.raises(ValueError):
        PurchaseRequisitionTransitionIn(expected_version=0)


def test_models_have_tenant_scoped_identity_and_history_constraints():
    requisition_constraints = {constraint.name for constraint in PurchaseRequisition.__table__.constraints}
    requisition_indexes = {index.name for index in PurchaseRequisition.__table__.indexes}
    item_constraints = {constraint.name for constraint in PurchaseRequisitionItem.__table__.constraints}
    event_constraints = {constraint.name for constraint in PurchaseRequisitionEvent.__table__.constraints}
    assert "uq_purchase_requisitions_tenant_code" in requisition_indexes
    assert "ck_purchase_requisitions_status" in requisition_constraints
    assert "uq_purchase_requisition_items_position" in {index.name for index in PurchaseRequisitionItem.__table__.indexes}
    assert "ck_purchase_requisition_items_quantity" in item_constraints
    assert "ck_purchase_requisition_events_sequence" in event_constraints

    actor_fk = next(
        constraint for constraint in PurchaseRequisitionEvent.__table__.foreign_key_constraints
        if "actor_admin_id" in {column.name for column in constraint.columns}
    )
    assert actor_fk.name == "fk_purchase_requisition_events_actor"
