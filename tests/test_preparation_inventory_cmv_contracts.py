"""Focused contract tests for preparation, inventory and CMV boundaries.

These tests deliberately inspect only the existing contracts.  They do not
create a database, mutate production code, or touch the finance test files.
"""

from pathlib import Path

from backend.models.inventory_foundation import InventoryOperation
from backend.models.preparation import PreparationExecution, PreparationOrder
from backend.services.preparation_service import PreparationService


ROOT = Path(__file__).resolve().parents[1]
PREPARATION_SERVICE = ROOT / "backend/services/preparation_service.py"
PREPARATION_ROUTES = ROOT / "backend/routes/preparation.py"


def test_preparation_records_are_tenant_scoped_and_idempotent():
    for model in (PreparationOrder, PreparationExecution):
        assert model.__table__.c.tenant_id.nullable is False

    execution_indexes = {
        index.name: tuple(column.name for column in index.columns)
        for index in PreparationExecution.__table__.indexes
    }
    assert execution_indexes["uq_preparation_executions_tenant_order_key"] == (
        "tenant_id",
        "order_id",
        "idempotency_key",
    )

    operation_indexes = {
        index.name: tuple(column.name for column in index.columns)
        for index in InventoryOperation.__table__.indexes
    }
    assert operation_indexes["uq_inventory_operation_request"] == (
        "tenant_id",
        "idempotency_scope",
        "idempotency_key",
    )


def test_preparation_service_scopes_order_queries_to_the_active_tenant():
    source = PREPARATION_SERVICE.read_text(encoding="utf-8")
    assert "def _q(self, model): return self.db.query(model).filter(model.tenant_id == self.tenant_id)" in source
    assert "q=self._q(PreparationOrder).filter(PreparationOrder.id==oid)" in source
    assert 'raise PreparationNotFound("Ordem nao encontrada neste tenant.")' in source


def test_preparation_status_contract_has_guarded_transitions_and_version_checks():
    source = PREPARATION_SERVICE.read_text(encoding="utf-8")
    assert '"approve": {"draft":"approved"}' in source
    assert '"cancel":{"draft":"cancelled"' in source
    assert "if b.expected_version != o.version: raise PreparationConflict" in source
    assert any(
        "status IN ('draft','approved','scheduled','waiting','in_progress','paused','partially_completed','blocked','completed','cancelled')"
        in str(constraint.sqltext)
        for constraint in PreparationOrder.__table__.constraints
        if hasattr(constraint, "sqltext")
    )


def test_preparation_order_query_contract_exposes_list_and_recipe_lookup():
    source = PREPARATION_ROUTES.read_text(encoding="utf-8")
    assert '@router.get("/orders")' in source
    assert '@router.get("/orders/{order_id}/recipe")' in source
