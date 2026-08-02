from pathlib import Path


ROOT = Path(__file__).parents[1]


def test_billing_is_locked_idempotent_and_rejects_final_invoice_states():
    service = (ROOT / "backend/services/platform_master_service.py").read_text(encoding="utf-8")
    model = (ROOT / "backend/models/platform_saas.py").read_text(encoding="utf-8")
    migration = (
        ROOT / "backend/migrations/versions/20260815_master_central_core.py"
    ).read_text(encoding="utf-8")

    payment_block = service[service.index("def register_payment("):]
    assert ".with_for_update().first()" in payment_block
    assert '{"paid", "cancelled", "refunded", "courtesy"}' in payment_block
    assert "PaymentReferenceConflict" in payment_block
    assert "payment_idempotent_replayed" in payment_block
    reference_lookup = payment_block.index("if body.reference:")
    final_state_gate = payment_block.index(
        'if invoice.status in {"paid", "cancelled", "refunded", "courtesy"}:'
    )
    assert reference_lookup < final_state_gate
    assert "existing.invoice_id != invoice.id or existing.amount != body.amount" in (
        payment_block[reference_lookup:final_state_gate]
    )
    assert '"idempotent_replay": True' in payment_block[reference_lookup:final_state_gate]
    assert "uq_saas_payments_tenant_reference" in model
    assert "uq_saas_payments_tenant_reference" in migration


def test_user_limit_and_single_owner_are_enforced_in_transaction():
    service = (ROOT / "backend/services/platform_master_service.py").read_text(encoding="utf-8")

    create_block = service[
        service.index("def create_tenant_user("):service.index("def update_tenant_user_role(")
    ]
    assert ".with_for_update().first()" in create_block
    assert "plan.max_users" in create_block
    assert "TenantUserLimitExceeded" in create_block
    assert "role_id=role.id" in create_block

    transfer_block = service[
        service.index("def transfer_ownership("):service.index("def tenant_security(")
    ]
    assert ".with_for_update().all()" in transfer_block
    assert "len(owners) != 1" in transfer_block
    assert 'old_owner.role = "admin"' in transfer_block
    assert 'target.role = "owner"' in transfer_block
    assert "ownership_transferred" in transfer_block


def test_dashboard_alerts_are_a_typed_list_contract():
    service = (ROOT / "backend/services/platform_master_service.py").read_text(encoding="utf-8")
    schema = (ROOT / "backend/schemas/platform_master.py").read_text(encoding="utf-8")

    assert 'result["alerts"] = [' in service
    for key in ("missing_owner", "missing_plan", "missing_domain", "licenses_expiring_7d", "overdue_invoices"):
        assert f'"key": "{key}"' in service
    assert "alerts: list[DashboardAlertOut]" in schema
    assert "created_month: int" in schema
    assert "total_users: int" in schema
    assert "mrr: Decimal" in schema
