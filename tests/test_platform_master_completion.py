from __future__ import annotations

import ast
import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

# Register every class referenced by Order relationships before any mapped
# instance is created in this combined test process.
from backend.models import (  # noqa: F401
    coupon,
    customer,
    delivery,
    loyalty,
    payment,
    product,
    product_promotion,
    salao,
)
from backend.core.tenant_auth import get_current_tenant_context
from backend.core.tenant_context import TenantSource
from backend import database
from backend.models.platform_audit import PlatformAuditLog
from backend.models.platform_saas import (
    SaaSInvoice,
    SaaSModule,
    SupportSession,
    TenantInvitation,
    TenantModule,
)
from backend.models.rbac import AdminAuditLog, Role, RolePermission, UserPermission
from backend.routes import admin_auth
from backend.routes.admin_auth import ChangePasswordIn, _authenticated_admin, _support_path_allowed
from backend.schemas.admin import AdminLoginIn
from backend.schemas.platform_master import (
    PlanUpdateIn,
    ModuleIn,
    TenantInvitationCreateIn,
    TenantInvitationResendIn,
    TenantModulesUpdateIn,
    TenantSummaryOut,
)
from backend.schemas.tenant_domain import TenantDomainVerificationChallenge
from backend.services.platform_master_service import (
    PlatformConflict,
    PlatformMasterService,
    PlatformNotFound,
    _effective_contract_price,
)
from backend.services.tenant_domain_service import TenantDomainService


ROOT = Path(__file__).parents[1]


class FakeQuery:
    def __init__(self, row=None):
        self.row = row

    def filter(self, *_args, **_kwargs):
        return self

    def join(self, *_args, **_kwargs):
        return self

    def outerjoin(self, *_args, **_kwargs):
        return self

    def with_for_update(self, *_args, **_kwargs):
        return self

    def order_by(self, *_args, **_kwargs):
        return self

    def first(self):
        return self.row

    def all(self):
        return self.row if isinstance(self.row, list) else []


class QueueDB:
    def __init__(self, *rows):
        self.rows = list(rows)
        self.commits = 0
        self.added = []

    def query(self, *_args, **_kwargs):
        assert self.rows, "unexpected query"
        return FakeQuery(self.rows.pop(0))

    def add(self, row):
        self.added.append(row)

    def flush(self):
        return None

    def commit(self):
        self.commits += 1

    def rollback(self):
        return None


def _admin(*, force_password_change=False, auth_version=0):
    return SimpleNamespace(
        id="admin-1",
        email="admin@example.com",
        name="Admin",
        role_id="role-1",
        active=True,
        force_password_change=force_password_change,
        auth_version=auth_version,
        password_hash="hash",
    )


def test_support_scope_is_explicit_and_denies_master_rbac_and_secrets(monkeypatch):
    for path in (
        "/api/admin/auth/me",
        "/api/gestao/finance/transactions",
        "/api/store-operation/status",
    ):
        assert _support_path_allowed(path)

    for path in (
        "/api/orders",
        "/api/payments/1",
        "/api/products",
        "/api/delivery",
        "/api/gestao",
        "/api/gestao/fiscal/documents",
        "/api/inventory/items",
        "/api/salao/tables",
        "/api/admin/platform/dashboard",
        "/api/admin/auth/me/permissions",
        "/api/admin/users",
        "/api/rbac/roles",
        "/api/whatsapp-gateway/instances/1/qrcode",
    ):
        assert not _support_path_allowed(path)

    monkeypatch.setattr(
        admin_auth,
        "decode_access_token",
        lambda _token: {
            "sub": "admin-1",
            "token_kind": "support",
            "tenant_id": "tenant-a",
            "support_session_id": "support-1",
            "auth_version": 0,
        },
    )
    with pytest.raises(HTTPException) as exc:
        _authenticated_admin(
            authorization="Bearer support",
            db=QueueDB(_admin()),
            request_path="/api/admin/auth/me/permissions",
        )
    assert exc.value.status_code == 403
    assert exc.value.detail["code"] == "SupportTokenScopeDenied"


def test_support_context_ignores_global_flag_but_rejects_x_tenant_mismatch(monkeypatch):
    from backend.core import tenant_auth

    now = datetime.now(timezone.utc)
    session = SimpleNamespace(
        id="support-1",
        tenant_id="tenant-a",
        actor_user_id="admin-1",
        status="active",
        expires_at=now + timedelta(minutes=10),
    )
    monkeypatch.setattr(
        tenant_auth,
        "decode_access_token",
        lambda _token: {
            "sub": "admin-1",
            "token_kind": "support",
            "tenant_id": "tenant-a",
            "support_session_id": "support-1",
        },
    )
    monkeypatch.setattr(
        tenant_auth,
        "get_settings",
        lambda: SimpleNamespace(MULTI_TENANT_AUTH_ENABLED=False),
    )
    context = get_current_tenant_context(
        authorization="Bearer support",
        requested_tenant_id="tenant-a",
        admin=_admin(),
        db=QueueDB(session),
    )
    assert context.tenant_id == "tenant-a"
    assert context.source is TenantSource.SUPPORT

    with pytest.raises(HTTPException) as exc:
        get_current_tenant_context(
            authorization="Bearer support",
            requested_tenant_id="tenant-b",
            admin=_admin(),
            db=QueueDB(),
        )
    assert exc.value.status_code == 403


def test_force_password_and_auth_version_fail_closed(monkeypatch):
    payload = {"sub": "admin-1", "auth_version": 0}
    monkeypatch.setattr(admin_auth, "decode_access_token", lambda _token: payload)

    with pytest.raises(HTTPException) as exc:
        _authenticated_admin(
            authorization="Bearer regular",
            db=QueueDB(_admin(force_password_change=True)),
            request_path="/api/orders",
        )
    assert exc.value.status_code == 403
    assert exc.value.detail["code"] == "PasswordChangeRequired"

    allowed = _authenticated_admin(
        authorization="Bearer regular",
        db=QueueDB(_admin(force_password_change=True)),
        allow_forced_password_change=True,
        request_path="/api/admin/auth/me",
    )
    assert allowed.id == "admin-1"

    # Tokens without the new claim remain valid only while no explicit
    # revocation has incremented the persisted version.
    payload.clear()
    payload["sub"] = "admin-1"
    assert _authenticated_admin(
        authorization="Bearer old",
        db=QueueDB(_admin(auth_version=0)),
        request_path="/api/orders",
    ).id == "admin-1"
    with pytest.raises(HTTPException) as exc:
        _authenticated_admin(
            authorization="Bearer revoked-old",
            db=QueueDB(_admin(auth_version=1)),
            request_path="/api/orders",
        )
    assert exc.value.status_code == 401

    payload["auth_version"] = "not-an-integer"
    with pytest.raises(HTTPException) as exc:
        _authenticated_admin(
            authorization="Bearer malformed",
            db=QueueDB(_admin()),
            request_path="/api/orders",
        )
    assert exc.value.status_code == 401


def test_bcrypt_byte_limit_is_enforced_for_login_and_password_change():
    oversized_unicode = "é" * 40  # 40 chars, 80 UTF-8 bytes.
    with pytest.raises(ValidationError):
        AdminLoginIn(email="admin@example.com", password=oversized_unicode)
    with pytest.raises(ValidationError):
        ChangePasswordIn(current_password="old", new_password=oversized_unicode)
    with pytest.raises(ValidationError):
        ChangePasswordIn(current_password=oversized_unicode, new_password="new-password")


def test_password_change_rejects_reusing_current_password(monkeypatch):
    monkeypatch.setattr(admin_auth, "verify_password", lambda *_args: True)
    response = admin_auth.change_password(
        ChangePasswordIn(current_password="same-password", new_password="same-password"),
        _admin(),
        QueueDB(),
    )
    assert response.status_code == 400
    assert b"PasswordReuseDenied" in response.body


def test_legacy_startup_create_all_excludes_master_central_tables(monkeypatch):
    captured = {}

    def capture_create_all(*, bind, tables):
        captured["bind"] = bind
        captured["tables"] = {table.name for table in tables}

    monkeypatch.setattr(database.Base.metadata, "create_all", capture_create_all)
    database.create_all_tables()

    assert captured["bind"] is database.engine
    assert "products" in captured["tables"]
    assert database.MASTER_CENTRAL_MIGRATION_TABLES.isdisjoint(captured["tables"])
    assert database.MASTER_CENTRAL_MIGRATION_TABLES <= set(database.Base.metadata.tables)


class _OverdueQuery:
    def __init__(self, row):
        self.row = row

    def filter(self, *_args):
        return self

    def with_for_update(self):
        return self

    def all(self):
        return [self.row] if self.row.status == "pending" else []


class _OverdueDb:
    def __init__(self, row):
        self.row = row
        self.added = []
        self.commits = 0

    def query(self, model):
        assert model is SaaSInvoice
        return _OverdueQuery(self.row)

    def add(self, row):
        self.added.append(row)

    def commit(self):
        self.commits += 1


def test_pending_past_due_invoice_transitions_once_with_system_audit():
    invoice = SaaSInvoice(
        id="invoice-overdue",
        tenant_id="tenant-a",
        period_start=datetime.now(timezone.utc) - timedelta(days=40),
        period_end=datetime.now(timezone.utc) - timedelta(days=10),
        due_at=datetime.now(timezone.utc) - timedelta(days=1),
        status="pending",
        base_amount=Decimal("100"),
        additions_amount=Decimal("0"),
        discount_amount=Decimal("0"),
        total_amount=Decimal("100"),
    )
    db = _OverdueDb(invoice)
    service = PlatformMasterService(db)

    assert service._sync_overdue_invoices() == 1
    assert service._sync_overdue_invoices() == 0
    assert invoice.status == "overdue"
    assert db.commits == 1
    audits = [item for item in db.added if isinstance(item, PlatformAuditLog)]
    assert len(audits) == 1
    assert audits[0].action == "invoice_marked_overdue"
    assert audits[0].actor_type == "system"


def test_plan_status_change_requires_audit_reason():
    assert PlanUpdateIn(name="Plano atualizado").reason is None
    with pytest.raises(ValidationError):
        PlanUpdateIn(status="archived")
    assert PlanUpdateIn(status="archived", reason="Encerramento comercial").status == "archived"


def test_tenant_summary_contract_and_service_expose_required_real_fields():
    required = {
        "trade_name", "document", "responsible", "last_access",
        "days_remaining", "domain_status",
    }
    assert required <= set(TenantSummaryOut.model_fields)
    service = (ROOT / "backend/services/platform_master_service.py").read_text(encoding="utf-8")
    summary = service[service.index("def tenant_summary("):service.index("def detail(")]
    for expression in (
        "profile.tax_id",
        "profile.legal_representative_name",
        "func.max(AdminUser.last_login_at)",
        '"days_remaining"',
        '"domain_status"',
    ):
        assert expression in summary


def test_domain_listing_searches_tenant_and_domain_and_routes_stay_thin():
    service = (ROOT / "backend/services/platform_master_service.py").read_text(encoding="utf-8")
    page = service[service.index("def domain_page("):service.index("def domain_action(")]
    assert "join(Tenant, Tenant.id == TenantDomain.tenant_id)" in page
    assert "TenantDomain.hostname.ilike(needle)" in page
    assert "Tenant.name.ilike(needle)" in page
    assert "Tenant.slug.ilike(needle)" in page

    routes = (ROOT / "backend/routes/platform_tenants.py").read_text(encoding="utf-8")
    actions = routes[routes.index("def verify_domain("):routes.index("def list_plans(")]
    assert "PlatformMasterService(db).domain_action(" in actions
    assert "db.commit()" not in actions
    assert "PlatformAuditService" not in actions
    assert "def remove_domain(domain_id: str, body: ReasonIn" in actions


def test_invitation_rejects_existing_identity_cross_tenant_and_expiry():
    service = PlatformMasterService(QueueDB(
        SimpleNamespace(id="tenant-a", slug="a"),
        SimpleNamespace(id="existing-user"),
    ))
    body = TenantInvitationCreateIn(
        email="existing@example.com",
        name="Existing User",
        reason="Acesso operacional",
    )
    with pytest.raises(PlatformConflict) as exc:
        service.invite_tenant_user("tenant-a", body, actor=_admin())
    assert exc.value.code == "ExistingIdentityInvitationUnsupported"

    cross_db = QueueDB(SimpleNamespace(id="tenant-a"), None)
    cross_service = PlatformMasterService(cross_db)
    with pytest.raises(PlatformNotFound) as exc:
        cross_service.resend_invitation(
            "tenant-a",
            "invite-from-tenant-b",
            TenantInvitationResendIn(reason="Reenvio controlado"),
            actor=_admin(),
        )
    assert exc.value.code == "TenantInvitationNotFound"

    expired = TenantInvitation(
        id="invite-1",
        tenant_id="tenant-a",
        email="new@example.com",
        name="New User",
        membership_role="viewer",
        token_hash="hash",
        status="pending",
        reason="Acesso",
        expires_at=datetime.now(timezone.utc) - timedelta(minutes=1),
        sent_at=datetime.now(timezone.utc) - timedelta(hours=1),
        resend_count=0,
    )
    expired_db = QueueDB(expired)
    expired_service = PlatformMasterService(expired_db)
    with pytest.raises(PlatformConflict) as exc:
        expired_service.accept_invitation(
            SimpleNamespace(token="x" * 32, password="temporary-password")
        )
    assert exc.value.code == "TenantInvitationExpired"
    assert expired.status == "expired"
    assert expired_db.commits == 1


def test_support_token_is_one_time_and_expired_token_is_closed(monkeypatch):
    now = datetime.now(timezone.utc)
    session = SupportSession(
        id="support-1",
        tenant_id="tenant-a",
        actor_user_id="admin-1",
        reason="Diagnostico",
        status="active",
        token_hash="ignored-by-fake-db",
        starts_at=now,
        expires_at=now + timedelta(minutes=15),
    )
    db = QueueDB(session, _admin(), session)
    service = PlatformMasterService(db)
    service.audit = SimpleNamespace(record=lambda **_kwargs: None)
    monkeypatch.setattr(
        "backend.services.platform_master_service.create_access_token",
        lambda *args, **kwargs: "scoped-jwt",
    )
    result = service.exchange_support_token(SimpleNamespace(support_token="x" * 32))
    assert result["access_token"] == "scoped-jwt"
    assert session.exchanged_at is not None
    with pytest.raises(PlatformConflict) as exc:
        service.exchange_support_token(SimpleNamespace(support_token="x" * 32))
    assert exc.value.code == "SupportTokenAlreadyExchanged"

    expired = SupportSession(
        id="support-expired",
        tenant_id="tenant-a",
        actor_user_id="admin-1",
        reason="Diagnostico",
        status="active",
        token_hash="expired",
        starts_at=now - timedelta(hours=1),
        expires_at=now - timedelta(seconds=1),
    )
    expired_db = QueueDB(expired)
    expired_service = PlatformMasterService(expired_db)
    with pytest.raises(PlatformConflict) as exc:
        expired_service.exchange_support_token(SimpleNamespace(support_token="y" * 32))
    assert exc.value.code == "SupportSessionExpired"
    assert expired.status == "expired"


def test_billing_paid_zero_and_effective_cycle_contracts():
    paid = SaaSInvoice(id="invoice-paid", tenant_id="tenant-a", status="paid")
    service = PlatformMasterService(QueueDB(paid))
    with pytest.raises(PlatformConflict) as exc:
        service._locked_mutable_invoice(
            paid.id,
            allowed_statuses={"draft", "pending", "overdue", "negotiated"},
            action="cortesia",
        )
    assert exc.value.code == "InvoiceStateConflict"

    invoice = SaaSInvoice(
        id="invoice-1",
        tenant_id="tenant-a",
        status="pending",
        base_amount=Decimal("100.00"),
        additions_amount=Decimal("20.00"),
        discount_amount=Decimal("0"),
        total_amount=Decimal("120.00"),
        period_start=datetime.now(timezone.utc),
        period_end=datetime.now(timezone.utc) + timedelta(days=30),
        due_at=datetime.now(timezone.utc) + timedelta(days=5),
    )
    zero_db = QueueDB(None)
    zero_service = PlatformMasterService(zero_db)
    zero_service.audit = SimpleNamespace(record=lambda **_kwargs: None)
    zero_service._locked_mutable_invoice = lambda *_args, **_kwargs: invoice
    result = zero_service.courtesy_invoice(
        invoice.id,
        SimpleNamespace(reason="Cortesia comercial"),
        actor=_admin(),
    )
    assert result["status"] == "courtesy"
    assert result["total_amount"] == Decimal("0")

    plan = SimpleNamespace(
        billing_cycle="monthly",
        price=Decimal("99"),
        monthly_price=Decimal("100"),
        quarterly_price=Decimal("270"),
        semiannual_price=Decimal("510"),
        annual_price=Decimal("900"),
    )
    assert _effective_contract_price(
        plan, SimpleNamespace(contract_value=None, billing_cycle="quarterly")
    ) == Decimal("270")
    assert _effective_contract_price(
        plan, SimpleNamespace(contract_value=None, billing_cycle="annual")
    ) == Decimal("900")
    assert _effective_contract_price(
        plan, SimpleNamespace(contract_value=Decimal("777"), billing_cycle="custom")
    ) == Decimal("777")


def test_domain_challenge_matches_the_declared_response_contract():
    domain = SimpleNamespace(
        hostname="store.example.com",
        expected_txt_record="_telz-verification.store.example.com",
    )
    challenge = TenantDomainService.verification_challenge(domain, "proof")
    parsed = TenantDomainVerificationChallenge.model_validate(challenge)
    assert parsed.hostname == domain.hostname


def test_platform_operations_is_the_single_static_head_and_master_downgrade_is_symmetric():
    versions = ROOT / "backend/migrations/versions"
    revisions: dict[str, tuple[str, ...]] = {}
    for path in versions.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        values = {}
        for node in tree.body:
            if isinstance(node, ast.Assign) and len(node.targets) == 1:
                target = node.targets[0]
                if isinstance(target, ast.Name) and target.id in {"revision", "down_revision"}:
                    values[target.id] = ast.literal_eval(node.value)
            elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                if node.target.id in {"revision", "down_revision"} and node.value is not None:
                    values[node.target.id] = ast.literal_eval(node.value)
        revision = values.get("revision")
        if not revision:
            continue
        down = values.get("down_revision")
        parents = tuple(down) if isinstance(down, (tuple, list)) else ((down,) if down else ())
        assert revision not in revisions
        revisions[revision] = parents

    missing = {
        parent
        for parents in revisions.values()
        for parent in parents
        if parent not in revisions
    }
    heads = set(revisions) - {parent for parents in revisions.values() for parent in parents}
    assert missing == set()
    assert heads == {"20260818_platform_operations"}

    bridge = (versions / "20260814_merge_all_heads.py").read_text(encoding="utf-8")
    assert 'down_revision = "20260813_automation_event_core"' in bridge
    assert "five historical heads" not in bridge

    migration = (versions / "20260816_master_completion.py").read_text(encoding="utf-8")
    assert 'down_revision = "20260815_master_central_core"' in migration
    assert 'op.drop_table("tenant_invitations")' in migration
    assert 'op.drop_column("admin_users", "auth_version")' in migration
    assert 'op.drop_column("admin_users", "job_title")' in migration
    assert "WHERE id = 'seed_' || plan_id || '_' || module_id" in migration
    assert "WHERE module_id IN ({catalog_ids})" not in migration
    assert "DROP CONSTRAINT IF EXISTS roles_name_key" in migration
    assert '"uq_roles_legacy_name"' not in migration
    assert "Cannot restore roles_name_key" in migration

    wave0 = (versions / "20260817_platform_wave0_foundation.py").read_text(encoding="utf-8")
    assert 'down_revision = "20260816_master_completion"' in wave0
    operations = (versions / "20260818_platform_operations.py").read_text(encoding="utf-8")
    assert 'down_revision = "20260817_platform_wave0"' in operations

    role_model = (ROOT / "backend/models/rbac.py").read_text(encoding="utf-8")
    role_block = role_model[role_model.index("class Role("):role_model.index("class RbacModule(")]
    assert 'UniqueConstraint("tenant_id", "name", name="uq_roles_tenant_name")' in role_block
    assert "uq_roles_legacy_name" not in role_block
    assert "name        = Column(String(100), nullable=False)" in role_block
    assert "name        = Column(String(100), unique=True" not in role_block

    for model in (Role, RolePermission, UserPermission, AdminAuditLog):
        assert model.__table__.c.tenant_id.nullable is False


def test_master_central_migrations_match_model_indexes_symmetrically():
    versions = ROOT / "backend/migrations/versions"
    sources = [
        (versions / "20260815_master_central_core.py").read_text(encoding="utf-8"),
        (versions / "20260816_master_completion.py").read_text(encoding="utf-8"),
        (versions / "20260818_platform_operations.py").read_text(encoding="utf-8"),
    ]
    upgrades = "\n".join(source.split("def downgrade()", 1)[0] for source in sources)
    downgrades = "\n".join(source.split("def downgrade()", 1)[1] for source in sources)
    for table_name in database.MASTER_CENTRAL_MIGRATION_TABLES:
        for index in database.Base.metadata.tables[table_name].indexes:
            needle = f'"{index.name}"'
            assert needle in upgrades, f"missing upgrade index {index.name}"
            assert needle in downgrades, f"missing downgrade index {index.name}"

    core = sources[0]
    assert 'sa.UniqueConstraint("key", name="uq_saas_plans_key")' in core
    assert 'sa.UniqueConstraint("key", name="uq_saas_modules_key")' in core
    for legacy_name in (
        "ix_saas_modules_group",
        "ix_saas_plan_modules_plan",
        "ix_saas_invoice_items_invoice",
    ):
        assert f'"{legacy_name}"' not in core


def test_integration_module_config_is_write_only_and_omitted_update_preserves_it():
    now = datetime.now(timezone.utc)
    module = SaaSModule(
        id="module-integration",
        key="provider",
        name="Provider",
        module_group="integrations",
        active=True,
        display_order=1,
        dependencies_json="[]",
        default_config_json='{"client_secret":"catalog-secret"}',
        created_at=now,
        updated_at=now,
    )
    link = TenantModule(
        id="tenant-module",
        tenant_id="tenant-a",
        module_id=module.id,
        enabled=True,
        origin="addon",
        starts_at=now,
        additional_price=Decimal("10"),
        config_json='{"client_secret":"tenant-secret"}',
        created_at=now,
        updated_at=now,
    )
    db = QueueDB(
        SimpleNamespace(id="tenant-a"),
        module,
        link,
        [(module, link)],
    )
    body = TenantModulesUpdateIn.model_validate({
        "modules": [{
            "module_id": module.id,
            "enabled": False,
            "origin": "courtesy",
            "reason": "Pausa operacional",
        }],
        "reason": "Ajuste administrativo",
    })
    result = PlatformMasterService(db).update_modules(
        "tenant-a",
        body,
        actor=SimpleNamespace(
            id="platform-user",
            name="Platform",
            email="platform@example.com",
            role_id="platform-admin",
        ),
    )

    assert link.config_json == '{"client_secret":"tenant-secret"}'
    assert result[0]["default_config_json"] is None
    assert result[0]["config_configured"] is True
    assert result[0]["entitlement"]["config_json"] is None
    assert result[0]["entitlement"]["config_configured"] is True
    audit = next(item for item in db.added if isinstance(item, PlatformAuditLog))
    assert "tenant-secret" not in (audit.after_data or "")
    assert json.loads(audit.after_data)["config_json"] == "[REDACTED]"


def test_tenant_module_explicit_empty_config_still_clears_it():
    item = TenantModulesUpdateIn.model_validate({
        "modules": [{"module_id": "module", "config": {}}],
        "reason": "Limpeza solicitada",
    }).modules[0]
    omitted = TenantModulesUpdateIn.model_validate({
        "modules": [{"module_id": "module"}],
        "reason": "Preservacao solicitada",
    }).modules[0]
    assert item.config == {}
    assert omitted.config is None


def test_module_default_config_rejects_nested_credentials():
    with pytest.raises(ValidationError, match="credenciais ou segredos"):
        ModuleIn.model_validate({
            "key": "provider",
            "name": "Provider",
            "module_group": "integrations",
            "default_config": {"oauth": [{"client_secret": "must-not-persist"}]},
        })


def test_alembic_env_imports_every_model_module_for_complete_metadata():
    models_dir = ROOT / "backend/models"
    expected = {path.stem for path in models_dir.glob("*.py") if path.stem != "__init__"}
    tree = ast.parse((ROOT / "backend/migrations/env.py").read_text(encoding="utf-8"))
    imported = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module == "backend.models"
        for alias in node.names
    }
    assert expected <= imported
