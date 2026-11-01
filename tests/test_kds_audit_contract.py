from pathlib import Path


ROOT = Path(__file__).parents[1]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_kds_audit_persistence_is_tenant_scoped_and_reuses_existing_assets():
    model = read("backend/models/kds_audit.py")
    migration = read("backend/migrations/versions/20261101_kds_delivery_audit.py")
    assert "class DeliveryAudit" in model
    assert "class DeliveryAuditItemConfirmation" in model
    assert "class DeliveryAuditVolume" in model
    assert "class DeliveryAuditEvidence" in model
    assert 'ForeignKey("tenant_upload_assets.id"' in model
    assert 'UniqueConstraint("tenant_id", "order_id"' in model
    assert "20261101_kds_delivery_audit" in migration
    assert "20261101_silent_label_print_queue" in migration
    assert "kds_auditoria" in migration


def test_kds_audit_service_enforces_lock_and_handoff_contract():
    service = read("backend/services/kds_audit_service.py")
    assert "OrderStatus.ready_for_pickup" in service
    assert "DeliveryStatus.pending_assignment, DeliveryStatus.assigned" in service
    assert ".with_for_update()" in service
    assert "DeliveryStatus.picked_up" in service
    assert "OrderStatus.on_the_way" in service
    assert "WhatsApp" not in service


def test_kds_audit_routes_are_rbac_gated_and_registered():
    routes = read("backend/routes/kds_audit.py")
    main = read("backend/main.py")
    assert 'require_rbac_permission("kds_auditoria", "view")' in routes
    assert 'require_rbac_permission("kds_auditoria", "edit")' in routes
    assert 'from backend.routes import kds_audit as kds_audit_routes' in main
    assert 'app.include_router(kds_audit_routes.router, prefix="/api")' in main


def test_kds_audit_uses_only_existing_upload_reference_input():
    schema = read("backend/schemas/kds_audit.py")
    service = read("backend/services/kds_audit_service.py")
    assert "asset_id" in schema
    assert "TenantUploadAsset" in service
    assert "TenantUploadAsset.tenant_id == self.tenant_id" in service
