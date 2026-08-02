"""Transactional application service for the Master Central."""
from __future__ import annotations

import hashlib
import json
import math
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import asc, desc, func, or_
from sqlalchemy.exc import IntegrityError

from backend.core.exceptions import DomainError
from backend.core.security import create_access_token, hash_password
from backend.models.admin import AdminUser
from backend.models.membership import TenantMembership
from backend.models.order import Order
from backend.models.platform_audit import PlatformAuditLog
from backend.models.rbac import RbacModule, RbacPermission, Role, RolePermission
from backend.models.platform_saas import (
    SaaSInvoice,
    SaaSInvoiceItem,
    SaaSModule,
    SaaSPayment,
    SaaSPlan,
    SaaSPlanModule,
    SupportSession,
    TenantInvitation,
    TenantLicense,
    TenantLicenseEvent,
    TenantInternalNote,
    TenantModule,
    TenantProfile,
    TenantSubscription,
    TenantUsageMetric,
)
from backend.models.tenant import Tenant
from backend.models.tenant_domain import TenantDomain
from backend.services.platform_audit_service import PlatformAuditService
from backend.services.tenant_domain_service import TenantDomainService, parse_hostname_set
from backend.services.tenant_service import normalize_tenant_slug


PLATFORM_MODULE_CATALOG = (
    ("dashboard", "Dashboard", "operation", 10),
    ("products", "Produtos", "operation", 20),
    ("categories", "Categorias", "operation", 30),
    ("orders", "Pedidos e cozinha", "operation", 40),
    ("dine_in", "Salao", "operation", 50),
    ("customers", "Clientes", "operation", 60),
    ("coupons", "Cupons", "operation", 70),
    ("loyalty", "Fidelidade", "operation", 80),
    ("store_hours", "Funcionamento", "operation", 90),
    ("appearance", "Aparencia", "operation", 100),
    ("content", "Conteudo", "operation", 110),
    ("shipping", "Frete", "delivery", 10),
    ("delivery_zones", "Zonas de entrega", "delivery", 20),
    ("delivery", "Motoboys", "delivery", 30),
    ("logistics", "Logistica", "delivery", 40),
    ("tracking", "Rastreamento", "delivery", 50),
    ("reviews", "Avaliacao", "delivery", 60),
    ("inventory", "Estoque", "management", 10),
    ("cmv", "CMV", "management", 20),
    ("finance", "Financeiro", "management", 30),
    ("dre", "DRE", "management", 40),
    ("fiscal", "Fiscal", "management", 50),
    ("purchases", "Compras", "management", 60),
    ("suppliers", "Fornecedores", "management", 70),
    ("ingredients", "Insumos", "management", 80),
    ("marketing_dashboard", "Dashboard de marketing", "marketing", 10),
    ("marketing", "Campanhas", "marketing", 20),
    ("visitors", "Visitantes", "marketing", 30),
    ("links", "Links", "marketing", 40),
    ("marketing_integrations", "Integracoes de marketing", "marketing", 50),
    ("whatsapp", "WhatsApp", "marketing", 60),
    ("email", "E-mail", "marketing", 70),
    ("automations", "Automacoes", "marketing", 80),
    ("ads", "Anuncios", "marketing", 90),
    ("workflow", "Workflow", "marketing", 100),
    ("marketing_coupons", "Cupons de marketing", "marketing", 110),
    ("crm", "Dashboard CRM", "crm", 10),
    ("crm_intelligence", "Inteligencia CRM", "crm", 20),
    ("pipeline", "Pipeline", "crm", 30),
    ("groups", "Grupos", "crm", 40),
    ("tags", "Tags", "crm", 50),
    ("segments", "Segmentos", "crm", 60),
    ("tasks", "Tarefas", "crm", 70),
    ("payments", "Pagamentos", "integrations", 10),
    ("mercado_pago", "Mercado Pago", "integrations", 20),
    ("asaas", "Asaas", "integrations", 30),
    ("pix", "PIX", "integrations", 40),
    ("whatsapp_gateway", "WhatsApp Gateway", "integrations", 50),
    ("ai", "Inteligencia artificial", "integrations", 60),
    ("pixels", "Pixels", "integrations", 70),
    ("google", "Google", "integrations", 80),
    ("meta_ads", "Meta Ads", "integrations", 90),
    ("webhooks", "Webhooks", "integrations", 100),
    ("integrations", "API e integracoes externas", "integrations", 110),
)


class PlatformConflict(DomainError):
    http_status = 409


class PlatformNotFound(DomainError):
    http_status = 404


class PlatformValidationError(DomainError):
    http_status = 422


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _id() -> str:
    return str(uuid.uuid4())


def _columns(row) -> dict | None:
    if row is None:
        return None
    return {column.name: getattr(row, column.name) for column in row.__table__.columns}


def _config_configured(value: str | None) -> bool:
    if not value:
        return False
    try:
        return bool(json.loads(value))
    except (TypeError, ValueError):
        # Malformed persisted configuration still represents configured data;
        # never expose it merely because it cannot be parsed.
        return True


def _module_public(row: SaaSModule) -> dict:
    result = _columns(row)
    result["config_configured"] = _config_configured(row.default_config_json)
    if row.module_group == "integrations":
        result["default_config_json"] = None
    return result


def _tenant_module_public(row: TenantModule | None, module_group: str) -> dict | None:
    if row is None:
        return None
    result = _columns(row)
    result["config_configured"] = _config_configured(row.config_json)
    if module_group == "integrations":
        result["config_json"] = None
    return result


def _admin_public(row: AdminUser) -> dict:
    """Explicit allowlist: password_hash and any future secrets never leave services."""
    return {
        "id": row.id,
        "email": row.email,
        "name": row.name,
        "active": bool(row.active),
        "phone": row.phone,
        "job_title": getattr(row, "job_title", None),
        "role_id": row.role_id,
        "last_login_at": row.last_login_at,
        "force_password_change": bool(row.force_password_change),
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }


def _domain_public(row: TenantDomain | None) -> dict | None:
    if row is None:
        return None
    blocked = {"verification_token_hash"}
    return {column.name: getattr(row, column.name) for column in row.__table__.columns if column.name not in blocked}


def _support_public(row: SupportSession) -> dict:
    blocked = {"token_hash"}
    return {column.name: getattr(row, column.name) for column in row.__table__.columns if column.name not in blocked}


def _plan_cycle_price(plan: SaaSPlan, billing_cycle: str | None = None) -> Decimal:
    field_by_cycle = {
        "monthly": "monthly_price",
        "quarterly": "quarterly_price",
        "semiannual": "semiannual_price",
        "annual": "annual_price",
    }
    field = field_by_cycle.get(billing_cycle or plan.billing_cycle)
    specific = getattr(plan, field, None) if field else None
    return Decimal(str(specific if specific is not None else plan.price))


def _effective_contract_price(
    plan: SaaSPlan | None,
    license_row: TenantLicense | None,
) -> Decimal:
    """Resolve the tenant contract first, then the selected cycle on the plan."""
    if license_row is not None and license_row.contract_value is not None:
        return Decimal(str(license_row.contract_value))
    if plan is None:
        return Decimal("0")
    cycle = license_row.billing_cycle if license_row is not None else plan.billing_cycle
    return _plan_cycle_price(plan, cycle)


class PlatformMasterService:
    """TenantSubscription selects commercial terms; TenantLicense alone enforces access."""

    def __init__(self, db):
        self.db = db
        self.audit = PlatformAuditService(db)

    def _tenant(self, tenant_id: str, *, include_archived: bool = False) -> Tenant:
        query = self.db.query(Tenant).filter(Tenant.id == tenant_id)
        if not include_archived:
            query = query.filter(Tenant.deleted_at.is_(None))
        row = query.first()
        if row is None:
            raise PlatformNotFound("Empresa nao encontrada.", code="TenantNotFound")
        return row

    def _domain(self, domain_id: str) -> TenantDomain:
        row = self.db.query(TenantDomain).filter(
            TenantDomain.id == domain_id,
            TenantDomain.status != "removed",
        ).first()
        if row is None:
            raise PlatformNotFound("Dominio nao encontrado.", code="DomainNotFound")
        return row

    def _sync_overdue_invoices(self, *, tenant_id: str | None = None) -> int:
        """Materialize due pending invoices once, with a system audit trail."""
        now = utcnow()
        query = self.db.query(SaaSInvoice).filter(
            SaaSInvoice.status == "pending",
            SaaSInvoice.due_at < now,
        )
        if tenant_id is not None:
            query = query.filter(SaaSInvoice.tenant_id == tenant_id)
        rows = query.with_for_update().all()
        for row in rows:
            before = _columns(row)
            row.status = "overdue"
            row.updated_at = now
            self.audit.record(
                action="invoice_marked_overdue",
                actor=None,
                tenant_id=row.tenant_id,
                resource_type="saas_invoice",
                resource_id=row.id,
                before=before,
                after=row,
                reason="Vencimento automatico da fatura.",
                metadata={"due_at": row.due_at},
            )
        if rows:
            self.db.commit()
        return len(rows)

    def list_tenant_domains(self, tenant_id: str) -> list[dict]:
        self._tenant(tenant_id)
        return [
            _domain_public(row)
            for row in self.db.query(TenantDomain).filter(
                TenantDomain.tenant_id == tenant_id,
                TenantDomain.status != "removed",
            ).order_by(TenantDomain.created_at.desc()).all()
        ]

    def create_domain(
        self,
        tenant_id: str,
        body,
        *,
        actor,
        request=None,
        platform_hostnames: frozenset[str] = frozenset(),
    ) -> dict:
        domain_service = TenantDomainService(self.db)
        domain, token = domain_service.create_pending(
            tenant_id=tenant_id,
            hostname=body.hostname,
            kind=body.kind,
            platform_hostnames=platform_hostnames,
        )
        self.audit.record(
            action="domain_requested",
            actor=actor,
            tenant_id=tenant_id,
            resource_type="tenant_domain",
            resource_id=domain.id,
            after=domain,
            request=request,
        )
        self.db.commit()
        self.db.refresh(domain)
        return {
            "domain": _domain_public(domain),
            "verification": domain_service.verification_challenge(domain, token),
        }

    def domain_page(
        self,
        *,
        page: int,
        page_size: int,
        status: str | None = None,
        q: str | None = None,
    ) -> dict:
        query = self.db.query(TenantDomain).filter(TenantDomain.status != "removed")
        if status:
            query = query.filter(TenantDomain.status == status)
        if q:
            needle = f"%{q.strip()}%"
            query = query.join(Tenant, Tenant.id == TenantDomain.tenant_id).filter(or_(
                TenantDomain.hostname.ilike(needle),
                Tenant.name.ilike(needle),
                Tenant.slug.ilike(needle),
            ))
        total = query.count()
        rows = query.order_by(TenantDomain.created_at.desc()).offset(
            (page - 1) * page_size
        ).limit(page_size).all()
        return {
            "items": [_domain_public(row) for row in rows],
            "total": total,
            "page": page,
            "page_size": page_size,
            "pages": math.ceil(total / page_size) if total else 0,
        }

    def domain_action(
        self,
        domain_id: str,
        action: str,
        *,
        actor,
        request=None,
        reason: str | None = None,
    ) -> dict:
        row = self._domain(domain_id)
        before = _domain_public(row)
        domain_service = TenantDomainService(self.db)
        if action == "verify":
            domain_service.verify_dns(row)
            audit_action = (
                "domain_verified"
                if row.status == "verified"
                else "domain_verification_failed"
            )
        elif action == "activate":
            domain_service.activate(row)
            audit_action = "domain_activated"
        elif action == "primary":
            domain_service.set_primary(row)
            audit_action = "domain_primary_changed"
        elif action == "suspend":
            domain_service.suspend(row, reason)
            audit_action = "domain_suspended"
        elif action == "remove":
            domain_service.remove(row, reason)
            audit_action = "domain_removed"
        else:
            raise PlatformValidationError(
                "Acao de dominio invalida.",
                code="InvalidDomainAction",
            )
        self.audit.record(
            action=audit_action,
            actor=actor,
            tenant_id=row.tenant_id,
            resource_type="tenant_domain",
            resource_id=row.id,
            before=before,
            after=row,
            reason=reason,
            request=request,
        )
        self.db.commit()
        return _domain_public(row)

    def dashboard(self) -> dict:
        self._sync_overdue_invoices()
        now = utcnow()
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        tenant_status = dict(
            self.db.query(Tenant.status, func.count(Tenant.id))
            .filter(Tenant.deleted_at.is_(None))
            .group_by(Tenant.status)
            .all()
        )
        license_status = dict(
            self.db.query(TenantLicense.status, func.count(TenantLicense.id))
            .group_by(TenantLicense.status)
            .all()
        )
        active_subscriptions = self.db.query(
            TenantSubscription, SaaSPlan, TenantLicense
        ).join(
            SaaSPlan, SaaSPlan.id == TenantSubscription.plan_id
        ).outerjoin(
            TenantLicense, TenantLicense.tenant_id == TenantSubscription.tenant_id
        ).filter(
            TenantSubscription.ended_at.is_(None),
            TenantSubscription.status == "active",
            SaaSPlan.status == "active",
        ).all()
        cycle_months = {"monthly": 1, "quarterly": 3, "semiannual": 6, "annual": 12}
        mrr = sum(
            (
                _effective_contract_price(plan, license_row)
                / Decimal(cycle_months.get(
                    license_row.billing_cycle if license_row is not None else plan.billing_cycle,
                    1,
                ))
                for _subscription, plan, license_row in active_subscriptions
            ),
            Decimal("0"),
        ).quantize(Decimal("0.01"))
        missing_owner = [
            row[0] for row in self.db.query(Tenant.id).filter(
                Tenant.deleted_at.is_(None),
                ~Tenant.id.in_(
                    self.db.query(TenantMembership.tenant_id).filter(
                        TenantMembership.role == "owner",
                        TenantMembership.status == "active",
                    )
                ),
            ).all()
        ]
        missing_plan = [
            row[0] for row in self.db.query(Tenant.id).filter(
                Tenant.deleted_at.is_(None),
                ~Tenant.id.in_(
                    self.db.query(TenantSubscription.tenant_id).filter(
                        TenantSubscription.ended_at.is_(None),
                        TenantSubscription.plan_id.isnot(None),
                    )
                ),
            ).all()
        ]
        missing_domain = [
            row[0] for row in self.db.query(Tenant.id).filter(
                Tenant.deleted_at.is_(None),
                ~Tenant.id.in_(
                    self.db.query(TenantDomain.tenant_id).filter(TenantDomain.status == "active")
                ),
            ).all()
        ]
        expiring = [
            row[0] for row in self.db.query(TenantLicense.tenant_id).filter(
                TenantLicense.expires_at >= now,
                TenantLicense.expires_at <= now + timedelta(days=7),
                TenantLicense.status.in_(("trial", "active", "grace_period")),
            ).all()
        ]
        overdue_tenants = [
            row[0] for row in self.db.query(SaaSInvoice.tenant_id).filter(
                SaaSInvoice.status == "overdue"
            ).distinct().all()
        ]
        expired_tenants = [
            row[0] for row in self.db.query(TenantLicense.tenant_id).filter(
                or_(
                    TenantLicense.status == "expired",
                    (
                        TenantLicense.expires_at < now
                    ) & TenantLicense.status.in_(("trial", "active", "grace_period")),
                )
            ).distinct().all()
        ]
        domain_error_tenants = [
            row[0] for row in self.db.query(TenantDomain.tenant_id).filter(
                TenantDomain.status.in_(("dns_error", "ssl_error"))
            ).distinct().all()
        ]
        billing_pending_tenants = [
            row[0] for row in self.db.query(SaaSInvoice.tenant_id).filter(
                SaaSInvoice.status == "pending"
            ).distinct().all()
        ]
        user_limit_tenants = []
        plan_limits = self.db.query(
            TenantSubscription.tenant_id,
            SaaSPlan.max_users,
        ).join(
            SaaSPlan, SaaSPlan.id == TenantSubscription.plan_id
        ).filter(
            TenantSubscription.ended_at.is_(None),
            SaaSPlan.max_users.isnot(None),
        ).all()
        for tenant_id, max_users in plan_limits:
            user_count = self.db.query(TenantMembership).filter(
                TenantMembership.tenant_id == tenant_id,
                TenantMembership.status.in_(("active", "invited")),
            ).count()
            if user_count >= max_users:
                user_limit_tenants.append(tenant_id)
        result = {
            "tenants": {
                "total": sum(tenant_status.values()),
                "active": tenant_status.get("active", 0),
                "suspended": tenant_status.get("suspended", 0),
                "disabled": tenant_status.get("disabled", 0),
            },
            "licenses": {
                "trial": license_status.get("trial", 0),
                "active": license_status.get("active", 0),
                "grace_period": license_status.get("grace_period", 0),
                "expired": license_status.get("expired", 0),
                "suspended": license_status.get("suspended", 0),
                "blocked": license_status.get("blocked", 0),
                "cancelled": license_status.get("cancelled", 0),
                "expiring_7d": len(expiring),
            },
            "billing": {
                "pending_total": str(self.db.query(func.coalesce(func.sum(SaaSInvoice.total_amount), 0)).filter(
                    SaaSInvoice.status.in_(("pending", "overdue"))
                ).scalar()),
                "overdue_count": self.db.query(SaaSInvoice).filter(SaaSInvoice.status == "overdue").count(),
            },
            "domains": {
                "active": self.db.query(TenantDomain).filter(TenantDomain.status == "active").count(),
                "pending": self.db.query(TenantDomain).filter(
                    TenantDomain.status.in_(("pending", "awaiting_dns", "verifying"))
                ).count(),
                "error": self.db.query(TenantDomain).filter(
                    TenantDomain.status.in_(("dns_error", "ssl_error"))
                ).count(),
            },
            "generated_at": now,
        }
        result["metrics"] = {
            "total_tenants": result["tenants"]["total"],
            "active_tenants": result["tenants"]["active"],
            "created_month": self.db.query(Tenant).filter(
                Tenant.created_at >= month_start, Tenant.deleted_at.is_(None)
            ).count(),
            "total_users": self.db.query(TenantMembership).filter(
                TenantMembership.status.in_(("active", "invited"))
            ).count(),
            "trial_licenses": result["licenses"]["trial"],
            "active_licenses": result["licenses"]["active"],
            "mrr": mrr,
            "overdue_invoices": result["billing"]["overdue_count"],
            "active_domains": result["domains"]["active"],
            "expired_licenses": len(expired_tenants),
            "pending_invoices": len(billing_pending_tenants),
            "domain_errors": len(domain_error_tenants),
            "user_limits_reached": len(user_limit_tenants),
        }
        result["alerts"] = [
            {"key": "missing_owner", "severity": "critical", "title": "Empresas sem owner",
             "count": len(missing_owner), "description": "Empresas sem owner ativo.",
             "tenant_ids": missing_owner[:50]},
            {"key": "missing_plan", "severity": "warning", "title": "Empresas sem plano",
             "count": len(missing_plan), "description": "Empresas sem assinatura comercial atual.",
             "tenant_ids": missing_plan[:50]},
            {"key": "missing_domain", "severity": "warning", "title": "Empresas sem dominio ativo",
             "count": len(missing_domain), "description": "Empresas ainda sem hostname publicado.",
             "tenant_ids": missing_domain[:50]},
            {"key": "licenses_expiring_7d", "severity": "warning", "title": "Licencas proximas do vencimento",
             "count": len(expiring), "description": "Licencas que vencem nos proximos sete dias.",
             "tenant_ids": expiring[:50]},
            {"key": "overdue_invoices", "severity": "critical", "title": "Faturas vencidas",
             "count": result["billing"]["overdue_count"], "description": "Faturas SaaS em atraso.",
             "tenant_ids": overdue_tenants[:50]},
            {"key": "expired_licenses", "severity": "critical", "title": "Licencas vencidas",
             "count": len(expired_tenants), "description": "Licencas expiradas ou fora da validade.",
             "tenant_ids": expired_tenants[:50]},
            {"key": "domain_errors", "severity": "critical", "title": "Dominios com erro",
             "count": len(domain_error_tenants), "description": "Dominios com erro de DNS ou SSL.",
             "tenant_ids": domain_error_tenants[:50]},
            {"key": "user_limits_reached", "severity": "warning", "title": "Limite de usuarios atingido",
             "count": len(user_limit_tenants), "description": "Empresas no limite de usuarios do plano.",
             "tenant_ids": user_limit_tenants[:50]},
            {"key": "pending_invoices", "severity": "info", "title": "Cobrancas pendentes",
             "count": len(billing_pending_tenants), "description": "Empresas com cobranca aguardando pagamento.",
             "tenant_ids": billing_pending_tenants[:50]},
        ]
        return result

    def list_tenants(
        self, *, page: int, page_size: int, q: str | None, status: str | None,
        sort_by: str, sort_dir: str, tenant_id: str | None = None,
        email: str | None = None, plan_id: str | None = None,
        domain: str | None = None, billing_status: str | None = None,
        module: str | None = None, expiring_days: int | None = None,
    ) -> dict:
        self._sync_overdue_invoices()
        query = self.db.query(Tenant).filter(Tenant.deleted_at.is_(None))
        if tenant_id:
            query = query.filter(Tenant.id == tenant_id)
        if q:
            needle = f"%{q.strip()}%"
            query = query.outerjoin(TenantProfile, TenantProfile.tenant_id == Tenant.id).filter(or_(
                Tenant.name.ilike(needle), Tenant.slug.ilike(needle),
                Tenant.legal_name.ilike(needle), TenantProfile.tax_id.ilike(needle),
            ))
        if status:
            if status in {"active", "suspended", "disabled"}:
                query = query.filter(Tenant.status == status)
            else:
                query = query.join(TenantLicense, TenantLicense.tenant_id == Tenant.id).filter(
                    TenantLicense.status == status
                )
        if email:
            query = query.filter(Tenant.id.in_(
                self.db.query(TenantMembership.tenant_id).join(
                    AdminUser, AdminUser.id == TenantMembership.user_id
                ).filter(
                    TenantMembership.role == "owner",
                    AdminUser.email.ilike(f"%{email.strip()}%"),
                )
            ))
        if plan_id:
            query = query.filter(Tenant.id.in_(
                self.db.query(TenantSubscription.tenant_id).filter(
                    TenantSubscription.plan_id == plan_id,
                    TenantSubscription.ended_at.is_(None),
                )
            ))
        if domain:
            query = query.filter(Tenant.id.in_(
                self.db.query(TenantDomain.tenant_id).filter(
                    TenantDomain.hostname.ilike(f"%{domain.strip()}%"),
                    TenantDomain.status != "removed",
                )
            ))
        if billing_status:
            if billing_status == "ok":
                query = query.filter(~Tenant.id.in_(
                    self.db.query(SaaSInvoice.tenant_id).filter(
                        SaaSInvoice.status.in_(("pending", "overdue"))
                    )
                ))
            else:
                query = query.filter(Tenant.id.in_(
                    self.db.query(SaaSInvoice.tenant_id).filter(
                        SaaSInvoice.status == billing_status
                    )
                ))
        if module:
            query = query.filter(Tenant.id.in_(
                self.db.query(TenantModule.tenant_id).join(
                    SaaSModule, SaaSModule.id == TenantModule.module_id
                ).filter(
                    or_(SaaSModule.id == module, SaaSModule.key == module),
                    TenantModule.enabled.is_(True),
                )
            ))
        if expiring_days is not None:
            deadline = utcnow() + timedelta(days=expiring_days)
            query = query.filter(Tenant.id.in_(
                self.db.query(TenantLicense.tenant_id).filter(
                    TenantLicense.expires_at >= utcnow(),
                    TenantLicense.expires_at <= deadline,
                )
            ))
        total = query.count()
        license_ends = self.db.query(TenantLicense.expires_at).filter(
            TenantLicense.tenant_id == Tenant.id
        ).correlate(Tenant).scalar_subquery()
        last_access = self.db.query(func.max(AdminUser.last_login_at)).join(
            TenantMembership, TenantMembership.user_id == AdminUser.id
        ).filter(TenantMembership.tenant_id == Tenant.id).correlate(Tenant).scalar_subquery()
        columns = {
            "name": Tenant.name, "slug": Tenant.slug, "status": Tenant.status,
            "created_at": Tenant.created_at, "updated_at": Tenant.updated_at,
            "license_ends_at": license_ends, "last_access": last_access,
        }
        if sort_by not in columns:
            raise PlatformValidationError(
                f"Ordenacao '{sort_by}' nao suportada.",
                code="UnsupportedTenantSort",
            )
        column = columns[sort_by]
        query = query.order_by((desc if sort_dir == "desc" else asc)(column), Tenant.id.asc())
        rows = query.offset((page - 1) * page_size).limit(page_size).all()
        return {
            "items": [self.tenant_summary(row) for row in rows],
            "total": total, "page": page, "page_size": page_size,
            "pages": math.ceil(total / page_size) if total else 0,
        }

    def tenant_summary(self, tenant: Tenant) -> dict:
        subscription = self.db.query(TenantSubscription).filter(
            TenantSubscription.tenant_id == tenant.id, TenantSubscription.ended_at.is_(None)
        ).first()
        plan = self.db.query(SaaSPlan).filter(SaaSPlan.id == subscription.plan_id).first() if subscription and subscription.plan_id else None
        license_row = self.db.query(TenantLicense).filter(TenantLicense.tenant_id == tenant.id).first()
        profile = self.db.query(TenantProfile).filter(
            TenantProfile.tenant_id == tenant.id
        ).first()
        primary_domain = self.db.query(TenantDomain).filter(
            TenantDomain.tenant_id == tenant.id, TenantDomain.is_primary.is_(True),
            TenantDomain.status == "active",
        ).first()
        domain_status_row = primary_domain or self.db.query(TenantDomain).filter(
            TenantDomain.tenant_id == tenant.id,
            TenantDomain.status != "removed",
        ).order_by(
            TenantDomain.is_primary.desc(), TenantDomain.created_at.desc()
        ).first()
        owner = self.db.query(AdminUser).join(
            TenantMembership, TenantMembership.user_id == AdminUser.id
        ).filter(
            TenantMembership.tenant_id == tenant.id,
            TenantMembership.role == "owner",
            TenantMembership.status != "revoked",
        ).order_by(TenantMembership.created_at.asc()).first()
        last_access = self.db.query(func.max(AdminUser.last_login_at)).join(
            TenantMembership, TenantMembership.user_id == AdminUser.id
        ).filter(TenantMembership.tenant_id == tenant.id).scalar()
        license_end = None
        if license_row is not None:
            if license_row.status == "trial":
                license_end = license_row.trial_ends_at
            elif license_row.status == "grace_period":
                license_end = (
                    license_row.grace_period_ends_at or license_row.expires_at
                )
            else:
                license_end = license_row.expires_at
        if license_end is not None and license_end.tzinfo is None:
            license_end = license_end.replace(tzinfo=timezone.utc)
        result = _columns(tenant)
        result.update({
            "plan": _columns(plan), "license": _columns(license_row),
            "primary_domain": _domain_public(primary_domain),
            "trade_name": profile.trade_name if profile else None,
            "document": profile.tax_id if profile else None,
            "responsible": (
                profile.legal_representative_name
                if profile and profile.legal_representative_name
                else (owner.name if owner else None)
            ),
            "last_access": last_access,
            "days_remaining": (
                max(0, (license_end - utcnow()).days)
                if license_end is not None else None
            ),
            "domain_status": domain_status_row.status if domain_status_row else None,
            "user_count": self.db.query(TenantMembership).filter(
                TenantMembership.tenant_id == tenant.id,
                TenantMembership.status.in_(("active", "invited")),
            ).count(),
            "billing_status": None,
        })
        billing_row = self.db.query(SaaSInvoice.status).filter(
            SaaSInvoice.tenant_id == tenant.id,
            SaaSInvoice.status.in_(("overdue", "pending")),
        ).order_by((SaaSInvoice.status == "overdue").desc(), SaaSInvoice.due_at.asc()).first()
        result["billing_status"] = billing_row[0] if billing_row else "ok"
        result["users_count"] = result["user_count"]
        return result

    def detail(self, tenant_id: str) -> dict:
        tenant = self._tenant(tenant_id)
        result = self.tenant_summary(tenant)
        result["profile"] = _columns(self.db.query(TenantProfile).filter(TenantProfile.tenant_id == tenant_id).first())
        result["modules"] = self.list_tenant_modules(tenant_id)
        result["domains"] = [_domain_public(row) for row in self.db.query(TenantDomain).filter(
            TenantDomain.tenant_id == tenant_id, TenantDomain.status != "removed"
        ).order_by(TenantDomain.created_at.desc()).all()]
        return result

    def provision(self, body, *, actor, request=None, platform_hostnames: frozenset[str] = frozenset()) -> dict:
        tenant_in = body.tenant
        slug = normalize_tenant_slug(tenant_in.slug)
        if self.db.query(Tenant.id).filter(Tenant.slug.ilike(slug)).first():
            raise PlatformConflict("Slug de empresa ja cadastrado.", code="TenantSlugConflict")
        email = str(body.owner.email).lower().strip()
        if self.db.query(AdminUser.id).filter(func.lower(AdminUser.email) == email).first():
            raise PlatformConflict("E-mail do owner ja cadastrado.", code="OwnerEmailConflict")
        if body.plan_id and self.db.query(SaaSPlan.id).filter(
            SaaSPlan.id == body.plan_id, SaaSPlan.status == "active"
        ).first() is None:
            raise PlatformNotFound("Plano nao encontrado ou inativo.", code="PlanNotFound")
        modules = []
        if body.module_ids:
            modules = self.db.query(SaaSModule).filter(
                SaaSModule.id.in_(set(body.module_ids)), SaaSModule.active.is_(True)
            ).all()
            if len(modules) != len(set(body.module_ids)):
                raise PlatformNotFound("Um ou mais modulos nao existem.", code="ModuleNotFound")
        now = utcnow()
        tenant = Tenant(
            id=_id(), slug=slug, name=tenant_in.name.strip(),
            legal_name=tenant_in.legal_name.strip() if tenant_in.legal_name else None,
            status=body.initial_status, timezone=tenant_in.timezone,
            locale=tenant_in.locale, is_legacy=False,
        )
        owner_role = Role(
            id=_id(), tenant_id=tenant.id, name=f"Owner {slug}",
            description="Papel empresarial do proprietario; nao concede autoridade de plataforma.",
            is_system=True,
        )
        owner = AdminUser(
            id=_id(), email=email, name=body.owner.name.strip(),
            phone=body.owner.phone, job_title=body.owner.job_title,
            password_hash=hash_password(body.owner.password),
            active=body.owner.status == "active", role_id=owner_role.id,
            created_by=getattr(actor, "id", None),
            force_password_change=body.owner.force_password_change,
        )
        membership = TenantMembership(
            id=_id(), tenant_id=tenant.id, user_id=owner.id, role="owner",
            status=body.owner.status, is_default=body.owner.status == "active",
            invited_by=getattr(actor, "id", None),
            joined_at=now if body.owner.status == "active" else None,
        )
        profile_data = body.profile.model_dump() if body.profile else {}
        profile = TenantProfile(tenant_id=tenant.id, **profile_data)
        subscription = TenantSubscription(
            id=_id(), tenant_id=tenant.id, plan_id=body.plan_id,
            status="trial" if body.trial_days else "active",
            starts_at=body.license_starts_at or now,
            custom_terms_json=json.dumps({
                "contract_value": str(body.contract_value) if body.contract_value is not None else None,
                "first_due_at": body.first_due_at.isoformat() if body.first_due_at else None,
            }),
        )
        license_start = body.license_starts_at or now
        trial_end = (
            license_start + timedelta(days=body.trial_days)
            if body.trial_days else None
        )
        license_end = body.license_expires_at or trial_end
        license_row = TenantLicense(
            id=_id(), tenant_id=tenant.id,
            status="trial" if body.trial_days else "active",
            starts_at=license_start, trial_ends_at=trial_end,
            expires_at=license_end,
            grace_period_ends_at=(
                trial_end + timedelta(days=body.grace_period_days)
                if trial_end and body.grace_period_days else None
            ),
            billing_cycle=body.billing_cycle,
            currency=body.currency.upper(),
            grace_period_days=body.grace_period_days,
            auto_renew=body.auto_renew,
            contract_value=body.contract_value,
            next_due_at=body.first_due_at,
        )
        self.db.add_all([tenant, owner_role, owner])
        self.db.flush()
        for module_id, permission_id in self.db.query(RbacModule.id, RbacPermission.id).filter(
            RbacModule.is_active.is_(True)
        ).all():
            self.db.add(RolePermission(
                id=_id(), tenant_id=tenant.id, role_id=owner_role.id,
                module_id=module_id, permission_id=permission_id, allowed=True,
            ))
        self.db.add_all([membership, profile, subscription, license_row])
        selected_modules = list(modules)
        if body.plan_id:
            plan_module_ids = [
                item[0] for item in self.db.query(SaaSPlanModule.module_id).filter(
                    SaaSPlanModule.plan_id == body.plan_id, SaaSPlanModule.enabled.is_(True)
                ).all()
            ]
            known = {row.id for row in selected_modules}
            selected_modules.extend(self.db.query(SaaSModule).filter(
                SaaSModule.id.in_(plan_module_ids), ~SaaSModule.id.in_(known) if known else True
            ).all())
        for module in selected_modules:
            self.db.add(TenantModule(
                id=_id(), tenant_id=tenant.id, module_id=module.id,
                enabled=True, origin="trial" if body.trial_days else "plan",
            ))
        self.db.add(TenantLicenseEvent(
            id=_id(), tenant_id=tenant.id, license_id=license_row.id,
            actor_user_id=getattr(actor, "id", None), event_type="license_created",
            new_status=license_row.status, metadata_json=json.dumps({"trial_days": body.trial_days}),
        ))
        domain = None
        challenge = None
        if body.domain:
            domain, token = TenantDomainService(self.db).create_pending(
                tenant_id=tenant.id, hostname=body.domain.hostname,
                kind=body.domain.kind, platform_hostnames=platform_hostnames,
            )
            challenge = TenantDomainService.verification_challenge(domain, token)
        self.audit.record(
            action="tenant_created", actor=actor, tenant_id=tenant.id,
            resource_type="tenant", resource_id=tenant.id, after=tenant,
            request=request, metadata={"owner_user_id": owner.id, "plan_id": body.plan_id},
        )
        try:
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return {
            "tenant": self.detail(tenant.id), "owner": _admin_public(owner),
            "license": _columns(license_row), "domain": _domain_public(domain),
            "verification": challenge,
        }

    def create_legacy_compatible(self, body, *, actor, request=None) -> Tenant:
        """Preserve the pre-wizard contract while keeping writes in the service layer."""
        slug = normalize_tenant_slug(body.slug)
        if self.db.query(Tenant.id).filter(Tenant.slug.ilike(slug)).first():
            raise PlatformConflict("Slug de empresa ja cadastrado.", code="TenantSlugConflict")
        tenant = Tenant(id=_id(), slug=slug, name=body.name.strip(),
            legal_name=body.legal_name.strip() if body.legal_name else None,
            status="active", timezone=body.timezone, locale=body.locale, is_legacy=False)
        has_membership = self.db.query(TenantMembership.id).filter(
            TenantMembership.user_id == actor.id, TenantMembership.status == "active"
        ).first() is not None
        self.db.add(tenant)
        self.db.flush()
        self.db.add(TenantMembership(id=_id(), tenant_id=tenant.id, user_id=actor.id,
            role="owner", status="active", is_default=not has_membership,
            invited_by=actor.id, joined_at=utcnow()))
        self.audit.record(action="tenant_created", actor=actor, tenant_id=tenant.id,
            resource_type="tenant", resource_id=tenant.id, after=tenant, request=request,
            metadata={"legacy_compatible_endpoint": True})
        self.db.commit()
        self.db.refresh(tenant)
        return tenant

    def update_tenant(self, tenant_id: str, body, *, actor, request=None) -> dict:
        tenant = self._tenant(tenant_id)
        before = _columns(tenant)
        data = body.model_dump(exclude_unset=True)
        profile_data = data.pop("profile", None)
        for key, value in data.items():
            setattr(tenant, key, value)
        if profile_data is not None:
            profile = self.db.query(TenantProfile).filter(TenantProfile.tenant_id == tenant_id).first()
            if profile is None:
                profile = TenantProfile(tenant_id=tenant_id)
                self.db.add(profile)
            for key, value in profile_data.items():
                setattr(profile, key, value)
        tenant.updated_at = utcnow()
        self.audit.record(action="tenant_updated", actor=actor, tenant_id=tenant_id,
            resource_type="tenant", resource_id=tenant_id, before=before, after=tenant, request=request)
        self.db.commit()
        return self.detail(tenant_id)

    def change_tenant_status(self, tenant_id: str, status: str, *, reason: str, actor, request=None) -> dict:
        tenant = self._tenant(tenant_id)
        if tenant.is_legacy and status in {"disabled", "archived"}:
            raise PlatformConflict("Empresa legada nao pode ser desativada ou arquivada.")
        before = _columns(tenant)
        if status == "archived":
            tenant.status = "disabled"
            tenant.deleted_at = utcnow()
            action = "tenant_archived"
        else:
            tenant.status = status
            action = {"suspended": "tenant_suspended", "active": "tenant_reactivated", "disabled": "tenant_disabled"}.get(status, "tenant_status_changed")
        tenant.updated_at = utcnow()
        self.audit.record(action=action, actor=actor, tenant_id=tenant_id, resource_type="tenant",
            resource_id=tenant_id, before=before, after=tenant, reason=reason, request=request)
        self.db.commit()
        return _columns(tenant)

    def list_users(self, tenant_id: str) -> list[dict]:
        self._tenant(tenant_id)
        rows = self.db.query(TenantMembership, AdminUser).join(
            AdminUser, AdminUser.id == TenantMembership.user_id
        ).filter(TenantMembership.tenant_id == tenant_id).order_by(AdminUser.name).all()
        return [{**_admin_public(user), "membership": _columns(membership)} for membership, user in rows]

    def _safe_member_role(self, tenant: Tenant, role_id: str | None) -> Role:
        if role_id:
            role = self.db.query(Role).filter(
                Role.id == role_id, Role.tenant_id == tenant.id
            ).first()
            reserved_names = {"master", f"owner {tenant.slug}".lower()}
            if role is None or role.name.strip().lower() in reserved_names:
                raise PlatformNotFound("Papel empresarial invalido.", code="TenantRoleNotFound")
            return role
        name = f"Member {tenant.slug}"
        role = self.db.query(Role).filter(Role.tenant_id == tenant.id, Role.name == name).first()
        if role is None:
            role = Role(id=_id(), tenant_id=tenant.id, name=name,
                description="Papel empresarial seguro sem autoridade de plataforma.",
                is_system=True)
            self.db.add(role)
            self.db.flush()
        return role

    def _membership_user(self, tenant_id: str, user_id: str, *, lock: bool = False):
        query = self.db.query(TenantMembership, AdminUser).join(
            AdminUser, AdminUser.id == TenantMembership.user_id
        ).filter(
            TenantMembership.tenant_id == tenant_id,
            TenantMembership.user_id == user_id,
        )
        if lock:
            query = query.with_for_update()
        row = query.first()
        if row is None:
            raise PlatformNotFound("Usuario nao pertence a empresa.", code="TenantUserNotFound")
        return row

    def create_tenant_user(self, tenant_id: str, body, *, actor, request=None) -> dict:
        tenant = self.db.query(Tenant).filter(
            Tenant.id == tenant_id, Tenant.deleted_at.is_(None)
        ).with_for_update().first()
        if tenant is None:
            raise PlatformNotFound("Empresa nao encontrada.", code="TenantNotFound")
        subscription = self.db.query(TenantSubscription).filter(
            TenantSubscription.tenant_id == tenant_id,
            TenantSubscription.ended_at.is_(None),
        ).first()
        plan = self.db.query(SaaSPlan).filter(
            SaaSPlan.id == subscription.plan_id
        ).first() if subscription and subscription.plan_id else None
        current_count = self.db.query(TenantMembership).filter(
            TenantMembership.tenant_id == tenant_id,
            TenantMembership.status.in_(("active", "invited")),
        ).count()
        if plan and plan.max_users is not None and current_count >= plan.max_users:
            raise PlatformConflict(
                f"Limite de {plan.max_users} usuarios do plano atingido.",
                code="TenantUserLimitExceeded",
            )
        email = str(body.email).lower().strip()
        if self.db.query(AdminUser.id).filter(func.lower(AdminUser.email) == email).first():
            raise PlatformConflict("E-mail ja cadastrado.", code="TenantUserEmailConflict")
        role = self._safe_member_role(tenant, body.role_id)
        user = AdminUser(id=_id(), email=email, name=body.name.strip(),
            phone=body.phone, job_title=body.job_title,
            password_hash=hash_password(body.password),
            active=True, role_id=role.id, force_password_change=body.force_password_change,
            created_by=getattr(actor, "id", None))
        membership = TenantMembership(id=_id(), tenant_id=tenant_id, user_id=user.id,
            role=body.membership_role, status="active", is_default=True,
            invited_by=getattr(actor, "id", None), joined_at=utcnow())
        self.db.add_all([user, membership])
        self.audit.record(action="user_created", actor=actor, tenant_id=tenant_id,
            resource_type="admin_user", resource_id=user.id,
            after={"user": _admin_public(user), "membership_role": body.membership_role},
            reason=body.reason, request=request)
        self.db.commit()
        return {**_admin_public(user), "membership": _columns(membership)}

    def _assert_user_capacity(
        self,
        tenant_id: str,
        *,
        include_pending_invitations: bool,
    ) -> None:
        subscription = self.db.query(TenantSubscription).filter(
            TenantSubscription.tenant_id == tenant_id,
            TenantSubscription.ended_at.is_(None),
        ).first()
        plan = self.db.query(SaaSPlan).filter(
            SaaSPlan.id == subscription.plan_id
        ).first() if subscription and subscription.plan_id else None
        if plan is None or plan.max_users is None:
            return
        current_count = self.db.query(TenantMembership).filter(
            TenantMembership.tenant_id == tenant_id,
            TenantMembership.status.in_(("active", "invited")),
        ).count()
        if include_pending_invitations:
            current_count += self.db.query(TenantInvitation).filter(
                TenantInvitation.tenant_id == tenant_id,
                TenantInvitation.status == "pending",
                TenantInvitation.expires_at > utcnow(),
            ).count()
        if current_count >= plan.max_users:
            raise PlatformConflict(
                f"Limite de {plan.max_users} usuarios do plano atingido.",
                code="TenantUserLimitExceeded",
            )

    @staticmethod
    def _invitation_public(row: TenantInvitation) -> dict:
        blocked = {"token_hash"}
        return {
            column.name: getattr(row, column.name)
            for column in row.__table__.columns
            if column.name not in blocked
        }

    def list_invitations(self, tenant_id: str) -> list[dict]:
        self._tenant(tenant_id)
        now = utcnow()
        expired = self.db.query(TenantInvitation).filter(
            TenantInvitation.tenant_id == tenant_id,
            TenantInvitation.status == "pending",
            TenantInvitation.expires_at <= now,
        ).all()
        for row in expired:
            row.status = "expired"
            row.updated_at = now
        if expired:
            self.db.commit()
        return [
            self._invitation_public(row)
            for row in self.db.query(TenantInvitation).filter(
                TenantInvitation.tenant_id == tenant_id
            ).order_by(TenantInvitation.created_at.desc()).all()
        ]

    def invite_tenant_user(self, tenant_id: str, body, *, actor, request=None) -> dict:
        tenant = self.db.query(Tenant).filter(
            Tenant.id == tenant_id,
            Tenant.deleted_at.is_(None),
        ).with_for_update().first()
        if tenant is None:
            raise PlatformNotFound("Empresa nao encontrada.", code="TenantNotFound")
        email = str(body.email).lower().strip()
        existing_user = self.db.query(AdminUser).filter(
            func.lower(AdminUser.email) == email
        ).first()
        if existing_user:
            raise PlatformConflict(
                "E-mail ja pertence a uma identidade existente; vinculacao exige fluxo RBAC dedicado.",
                code="ExistingIdentityInvitationUnsupported",
            )
        expired_pending = self.db.query(TenantInvitation).filter(
            TenantInvitation.tenant_id == tenant_id,
            TenantInvitation.email == email,
            TenantInvitation.status == "pending",
            TenantInvitation.expires_at <= utcnow(),
        ).with_for_update().all()
        for expired in expired_pending:
            expired.status = "expired"
            expired.updated_at = utcnow()
        if expired_pending:
            self.db.flush()
        if self.db.query(TenantInvitation.id).filter(
            TenantInvitation.tenant_id == tenant_id,
            TenantInvitation.email == email,
            TenantInvitation.status == "pending",
            TenantInvitation.expires_at > utcnow(),
        ).first():
            raise PlatformConflict(
                "Ja existe convite pendente para este e-mail.",
                code="TenantInvitationPending",
            )
        self._assert_user_capacity(
            tenant_id,
            include_pending_invitations=True,
        )
        role = self._safe_member_role(tenant, body.role_id)
        raw_token = secrets.token_urlsafe(48)
        now = utcnow()
        row = TenantInvitation(
            id=_id(),
            tenant_id=tenant_id,
            email=email,
            name=body.name.strip(),
            phone=body.phone,
            job_title=body.job_title,
            membership_role=body.membership_role,
            role_id=role.id,
            token_hash=hashlib.sha256(raw_token.encode()).hexdigest(),
            status="pending",
            reason=body.reason,
            invited_by=getattr(actor, "id", None),
            expires_at=now + timedelta(hours=body.expires_in_hours),
            sent_at=now,
        )
        self.db.add(row)
        self.audit.record(
            action="user_invited",
            actor=actor,
            tenant_id=tenant_id,
            resource_type="tenant_invitation",
            resource_id=row.id,
            after=self._invitation_public(row),
            reason=body.reason,
            request=request,
        )
        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise PlatformConflict(
                "Ja existe convite pendente para este e-mail.",
                code="TenantInvitationPending",
            ) from exc
        return {
            "invitation": self._invitation_public(row),
            "invitation_token": raw_token,
        }

    def resend_invitation(
        self,
        tenant_id: str,
        invitation_id: str,
        body,
        *,
        actor,
        request=None,
    ) -> dict:
        self._tenant(tenant_id)
        row = self.db.query(TenantInvitation).filter(
            TenantInvitation.id == invitation_id,
            TenantInvitation.tenant_id == tenant_id,
        ).with_for_update().first()
        if row is None:
            raise PlatformNotFound("Convite nao encontrado.", code="TenantInvitationNotFound")
        if row.status != "pending":
            raise PlatformConflict(
                "Somente convite pendente pode ser reenviado.",
                code="TenantInvitationNotPending",
            )
        raw_token = secrets.token_urlsafe(48)
        now = utcnow()
        row.token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
        row.expires_at = now + timedelta(hours=body.expires_in_hours)
        row.sent_at = now
        row.reason = body.reason
        row.resend_count += 1
        row.updated_at = now
        self.audit.record(
            action="user_invitation_resent",
            actor=actor,
            tenant_id=tenant_id,
            resource_type="tenant_invitation",
            resource_id=row.id,
            after=self._invitation_public(row),
            reason=body.reason,
            request=request,
        )
        self.db.commit()
        return {
            "invitation": self._invitation_public(row),
            "invitation_token": raw_token,
        }

    def accept_invitation(self, body, *, request=None) -> dict:
        token_hash = hashlib.sha256(body.token.encode()).hexdigest()
        row = self.db.query(TenantInvitation).filter(
            TenantInvitation.token_hash == token_hash
        ).with_for_update().first()
        if row is None:
            raise PlatformNotFound(
                "Convite invalido ou ja rotacionado.",
                code="TenantInvitationNotFound",
            )
        now = utcnow()
        if row.status != "pending":
            raise PlatformConflict(
                "Convite nao esta pendente.",
                code="TenantInvitationNotPending",
            )
        if row.expires_at <= now:
            row.status = "expired"
            row.updated_at = now
            self.db.commit()
            raise PlatformConflict("Convite expirado.", code="TenantInvitationExpired")
        tenant = self.db.query(Tenant).filter(
            Tenant.id == row.tenant_id,
            Tenant.deleted_at.is_(None),
        ).with_for_update().first()
        if tenant is None:
            raise PlatformNotFound("Empresa nao encontrada.", code="TenantNotFound")
        user = self.db.query(AdminUser).filter(
            func.lower(AdminUser.email) == row.email
        ).with_for_update().first()
        if user:
            raise PlatformConflict(
                "E-mail ja pertence a uma identidade existente; aceite exige fluxo RBAC dedicado.",
                code="ExistingIdentityInvitationUnsupported",
            )
        self._assert_user_capacity(
            row.tenant_id,
            include_pending_invitations=False,
        )
        role = self.db.query(Role).filter(
            Role.id == row.role_id,
            Role.tenant_id == row.tenant_id,
        ).first()
        reserved_names = {"master", f"owner {tenant.slug}".lower()}
        if role is None or role.name.strip().lower() in reserved_names:
            role = self._safe_member_role(tenant, None)
        if not body.password:
            raise PlatformValidationError(
                "Senha e obrigatoria para novo usuario.",
                code="TenantInvitationPasswordRequired",
            )
        user = AdminUser(
            id=_id(),
            email=row.email,
            name=row.name,
            phone=row.phone,
            job_title=row.job_title,
            password_hash=hash_password(body.password),
            active=True,
            role_id=role.id,
            force_password_change=False,
            created_by=row.invited_by,
        )
        self.db.add(user)
        self.db.flush()
        has_default = self.db.query(TenantMembership.id).filter(
            TenantMembership.user_id == user.id,
            TenantMembership.status == "active",
            TenantMembership.is_default.is_(True),
        ).first() is not None
        membership = TenantMembership(
            id=_id(),
            tenant_id=row.tenant_id,
            user_id=user.id,
            role=row.membership_role,
            status="active",
            is_default=not has_default,
            invited_by=row.invited_by,
            joined_at=now,
        )
        self.db.add(membership)
        row.status = "accepted"
        row.accepted_by = user.id
        row.accepted_at = now
        row.updated_at = now
        self.audit.record(
            action="user_invitation_accepted",
            actor=user,
            tenant_id=row.tenant_id,
            resource_type="tenant_invitation",
            resource_id=row.id,
            after={
                "invitation": self._invitation_public(row),
                "membership_id": membership.id,
            },
            request=request,
        )
        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise PlatformConflict(
                "Convite ja foi aceito ou membership ja existe.",
                code="TenantInvitationAcceptanceConflict",
            ) from exc
        return {
            "user": _admin_public(user),
            "membership": _columns(membership),
            "tenant_id": row.tenant_id,
        }

    def update_tenant_user_role(self, tenant_id: str, user_id: str, body, *, actor, request=None) -> dict:
        tenant = self._tenant(tenant_id)
        membership, user = self._membership_user(tenant_id, user_id, lock=True)
        if membership.role == "owner":
            raise PlatformConflict("Transfira a propriedade antes de alterar o owner.", code="OwnerRoleProtected")
        before = {"role_id": user.role_id, "membership_role": membership.role}
        role = self._safe_member_role(tenant, body.role_id)
        user.role_id = role.id
        membership.role = body.membership_role
        membership.updated_at = utcnow()
        self.audit.record(action="user_role_changed", actor=actor, tenant_id=tenant_id,
            resource_type="admin_user", resource_id=user.id, before=before,
            after={"role_id": user.role_id, "membership_role": membership.role},
            reason=body.reason, request=request)
        self.db.commit()
        return {**_admin_public(user), "membership": _columns(membership)}

    def update_tenant_user_status(self, tenant_id: str, user_id: str, body, *, actor, request=None) -> dict:
        membership, user = self._membership_user(tenant_id, user_id, lock=True)
        if membership.role == "owner" and body.status != "active":
            raise PlatformConflict("Owner ativo nao pode ser bloqueado ou revogado.", code="OwnerStatusProtected")
        before = membership.status
        membership.status = body.status
        membership.updated_at = utcnow()
        self.audit.record(action="user_status_changed", actor=actor, tenant_id=tenant_id,
            resource_type="tenant_membership", resource_id=membership.id,
            before={"status": before}, after={"status": membership.status},
            reason=body.reason, request=request)
        self.db.commit()
        return {**_admin_public(user), "membership": _columns(membership)}

    def reset_tenant_user_password(self, tenant_id: str, user_id: str, body, *, actor, request=None) -> dict:
        membership, user = self._membership_user(tenant_id, user_id, lock=True)
        user.password_hash = hash_password(body.password)
        user.force_password_change = body.force_password_change
        user.auth_version = int(getattr(user, "auth_version", 0) or 0) + 1
        user.updated_by = getattr(actor, "id", None)
        user.updated_at = utcnow()
        self.audit.record(action="user_password_reset", actor=actor, tenant_id=tenant_id,
            resource_type="admin_user", resource_id=user.id,
            after={"force_password_change": user.force_password_change},
            reason=body.reason, request=request)
        self.db.commit()
        return {
            **_admin_public(user),
            "membership": _columns(membership),
            "password_reset": True,
        }

    def revoke_tenant_user_sessions(
        self, tenant_id: str, user_id: str, body, *, actor, request=None,
    ) -> dict:
        membership, user = self._membership_user(tenant_id, user_id, lock=True)
        before_version = int(getattr(user, "auth_version", 0) or 0)
        user.auth_version = before_version + 1
        user.updated_by = getattr(actor, "id", None)
        user.updated_at = utcnow()
        self.audit.record(
            action="user_sessions_revoked", actor=actor, tenant_id=tenant_id,
            resource_type="admin_user", resource_id=user.id,
            before={"auth_version": before_version},
            after={"auth_version": user.auth_version}, reason=body.reason,
            request=request,
        )
        self.db.commit()
        return {**_admin_public(user), "membership": _columns(membership)}

    def transfer_ownership(self, tenant_id: str, body, *, actor, request=None) -> dict:
        tenant = self.db.query(Tenant).filter(
            Tenant.id == tenant_id, Tenant.deleted_at.is_(None)
        ).with_for_update().first()
        if tenant is None:
            raise PlatformNotFound("Empresa nao encontrada.", code="TenantNotFound")
        memberships = self.db.query(TenantMembership).filter(
            TenantMembership.tenant_id == tenant_id
        ).with_for_update().all()
        owners = [row for row in memberships if row.role == "owner" and row.status == "active"]
        if len(owners) != 1:
            raise PlatformConflict("Empresa precisa possuir exatamente um owner ativo.", code="InvalidOwnerState")
        old_owner = owners[0]
        target = next((row for row in memberships if row.user_id == body.new_owner_user_id), None)
        if target is None or target.status != "active":
            raise PlatformNotFound("Novo owner precisa possuir membership ativo.", code="NewOwnerNotEligible")
        if target.user_id == old_owner.user_id:
            raise PlatformConflict("Usuario ja e o owner atual.", code="OwnerUnchanged")
        old_user = self.db.query(AdminUser).filter(AdminUser.id == old_owner.user_id).with_for_update().first()
        new_user = self.db.query(AdminUser).filter(AdminUser.id == target.user_id).with_for_update().first()
        owner_role = self.db.query(Role).filter(
            Role.tenant_id == tenant_id, Role.name == f"Owner {tenant.slug}"
        ).first()
        if owner_role is None:
            raise PlatformConflict("Papel owner da empresa nao esta configurado.", code="OwnerRoleMissing")
        member_role = self._safe_member_role(tenant, None)
        old_owner.role = "admin"
        target.role = "owner"
        old_owner.updated_at = target.updated_at = utcnow()
        old_user.role_id = member_role.id
        new_user.role_id = owner_role.id
        self.audit.record(action="ownership_transferred", actor=actor, tenant_id=tenant_id,
            resource_type="tenant_membership", resource_id=target.id,
            before={"owner_user_id": old_user.id}, after={"owner_user_id": new_user.id},
            reason=body.reason, request=request)
        self.db.commit()
        return {"previous_owner": {**_admin_public(old_user), "membership": _columns(old_owner)},
            "new_owner": {**_admin_public(new_user), "membership": _columns(target)}}

    def tenant_security(self, tenant_id: str) -> dict:
        self._tenant(tenant_id)
        memberships = self.db.query(TenantMembership).filter(
            TenantMembership.tenant_id == tenant_id
        ).all()
        support_rows = self.db.query(SupportSession).filter(
            SupportSession.tenant_id == tenant_id
        ).order_by(SupportSession.created_at.desc()).limit(20).all()
        return {
            "active_users": sum(1 for row in memberships if row.status == "active"),
            "invited_users": sum(1 for row in memberships if row.status == "invited"),
            "blocked_users": sum(1 for row in memberships if row.status in {"suspended", "revoked"}),
            "active_support_sessions": sum(
                1 for row in support_rows if row.status == "active" and row.expires_at >= utcnow()
            ),
            "support_sessions": [_support_public(row) for row in support_rows],
            "session_revocation_available": True,
            "two_factor_available": False,
        }

    def tenant_usage(self, tenant_id: str) -> list[dict]:
        self._tenant(tenant_id)
        return [_columns(row) for row in self.db.query(TenantUsageMetric).filter(
            TenantUsageMetric.tenant_id == tenant_id
        ).order_by(TenantUsageMetric.period_key.desc(), TenantUsageMetric.metric_key).all()]

    def refresh_usage_metrics(self, tenant_id: str) -> list[dict]:
        tenant = self.db.query(Tenant).filter(
            Tenant.id == tenant_id,
            Tenant.deleted_at.is_(None),
        ).with_for_update().first()
        if tenant is None:
            raise PlatformNotFound("Empresa nao encontrada.", code="TenantNotFound")
        now = utcnow()
        period_key = now.strftime("%Y-%m")
        values = {
            "users.current": self.db.query(TenantMembership).filter(
                TenantMembership.tenant_id == tenant_id,
                TenantMembership.status.in_(("active", "invited")),
            ).count(),
            "orders.month": self.db.query(Order).filter(
                Order.tenant_id == tenant_id,
                Order.created_at >= now.replace(
                    day=1, hour=0, minute=0, second=0, microsecond=0
                ),
            ).count(),
        }
        for metric_key, value in values.items():
            row = self.db.query(TenantUsageMetric).filter(
                TenantUsageMetric.tenant_id == tenant_id,
                TenantUsageMetric.metric_key == metric_key,
                TenantUsageMetric.period_key == period_key,
            ).with_for_update().first()
            if row is None:
                row = TenantUsageMetric(
                    id=_id(),
                    tenant_id=tenant_id,
                    metric_key=metric_key,
                    period_key=period_key,
                )
                self.db.add(row)
            row.value = value
            row.updated_at = now
        self.db.commit()
        return self.tenant_usage(tenant_id)

    def notes(self, tenant_id: str) -> list[dict]:
        self._tenant(tenant_id)
        rows = self.db.query(TenantInternalNote, AdminUser).outerjoin(
            AdminUser, AdminUser.id == TenantInternalNote.author_user_id
        ).filter(TenantInternalNote.tenant_id == tenant_id).order_by(
            TenantInternalNote.created_at.desc()
        ).all()
        return [{
            **_columns(note),
            "author": {"id": user.id, "name": user.name, "email": user.email} if user else None,
        } for note, user in rows]

    def add_note(self, tenant_id: str, body, *, actor, request=None) -> dict:
        self._tenant(tenant_id)
        row = TenantInternalNote(id=_id(), tenant_id=tenant_id,
            author_user_id=getattr(actor, "id", None), note=body.note.strip())
        self.db.add(row)
        self.audit.record(action="tenant_note_created", actor=actor, tenant_id=tenant_id,
            resource_type="tenant_internal_note", resource_id=row.id,
            after={"note": row.note}, request=request)
        self.db.commit()
        return {**_columns(row), "author": {
            "id": actor.id, "name": actor.name, "email": actor.email,
        }}

    def list_tenant_modules(self, tenant_id: str) -> list[dict]:
        rows = self.db.query(SaaSModule, TenantModule).outerjoin(
            TenantModule,
            (TenantModule.module_id == SaaSModule.id) & (TenantModule.tenant_id == tenant_id),
        ).order_by(SaaSModule.module_group, SaaSModule.display_order, SaaSModule.name).all()
        return [{
            **_module_public(module),
            "entitlement": _tenant_module_public(link, module.module_group),
        } for module, link in rows]

    def update_modules(self, tenant_id: str, body, *, actor, request=None) -> list[dict]:
        self._tenant(tenant_id)
        for item in body.modules:
            module = self.db.query(SaaSModule).filter(SaaSModule.id == item.module_id).first()
            if module is None:
                raise PlatformNotFound("Modulo nao encontrado.", code="ModuleNotFound")
            row = self.db.query(TenantModule).filter(
                TenantModule.tenant_id == tenant_id, TenantModule.module_id == item.module_id
            ).first()
            before = _columns(row)
            created = row is None
            if created:
                row = TenantModule(id=_id(), tenant_id=tenant_id, module_id=item.module_id)
                self.db.add(row)
            row.enabled = item.enabled
            row.origin = item.origin
            if item.starts_at is not None:
                row.starts_at = item.starts_at
            row.ends_at = item.ends_at
            row.limit_value = item.limit_value
            row.additional_price = item.additional_price
            row.block_reason = item.reason if not item.enabled else None
            if item.config is not None:
                row.config_json = json.dumps(item.config, ensure_ascii=False)
            elif created:
                row.config_json = "{}"
            self.audit.record(action="module_enabled" if item.enabled else "module_disabled",
                actor=actor, tenant_id=tenant_id, resource_type="tenant_module",
                resource_id=row.id, before=before, after=row, reason=body.reason, request=request)
        self.db.commit()
        return self.list_tenant_modules(tenant_id)

    def change_plan(self, tenant_id: str, body, *, actor, request=None) -> dict:
        self._tenant(tenant_id)
        plan = self.db.query(SaaSPlan).filter(
            SaaSPlan.id == body.plan_id, SaaSPlan.status == "active"
        ).first()
        if plan is None:
            raise PlatformNotFound("Plano nao encontrado ou inativo.", code="PlanNotFound")
        now = utcnow()
        current = self.db.query(TenantSubscription).filter(
            TenantSubscription.tenant_id == tenant_id,
            TenantSubscription.ended_at.is_(None),
        ).first()
        before = _columns(current)
        if current:
            current.ended_at = now
            current.status = "cancelled"
        subscription = TenantSubscription(id=_id(), tenant_id=tenant_id,
            plan_id=plan.id, status="active", starts_at=now)
        self.db.add(subscription)
        module_ids = [item[0] for item in self.db.query(SaaSPlanModule.module_id).filter(
            SaaSPlanModule.plan_id == plan.id, SaaSPlanModule.enabled.is_(True)
        ).all()]
        for module_id in module_ids:
            row = self.db.query(TenantModule).filter(
                TenantModule.tenant_id == tenant_id, TenantModule.module_id == module_id
            ).first()
            if row is None:
                self.db.add(TenantModule(id=_id(), tenant_id=tenant_id,
                    module_id=module_id, enabled=True, origin="plan"))
            elif row.origin == "plan":
                row.enabled, row.block_reason = True, None
        # Modules removed from a plan are disabled, never deleted.
        for row in self.db.query(TenantModule).filter(
            TenantModule.tenant_id == tenant_id, TenantModule.origin == "plan",
            ~TenantModule.module_id.in_(module_ids) if module_ids else True,
        ).all():
            row.enabled = False
            row.block_reason = "Modulo removido do plano atual."
        self.audit.record(action="plan_changed", actor=actor, tenant_id=tenant_id,
            resource_type="tenant_subscription", resource_id=subscription.id,
            before=before, after=subscription, reason=body.reason, request=request)
        self.db.commit()
        return self.detail(tenant_id)

    def license(self, tenant_id: str) -> dict:
        row = self.db.query(TenantLicense).filter(TenantLicense.tenant_id == tenant_id).first()
        if row is None:
            raise PlatformNotFound("Licenca nao encontrada.", code="LicenseNotFound")
        now = utcnow()
        result = _columns(row)
        end = row.trial_ends_at if row.status == "trial" else row.expires_at
        result["days_remaining"] = max(0, (end - now).days) if end else None
        result["days_used"] = max(0, (now - row.starts_at).days)
        result["ends_at"] = end
        result["grace_ends_at"] = row.grace_period_ends_at
        return result

    def license_action(self, tenant_id: str, action: str, body, *, actor, request=None) -> dict:
        row = self.db.query(TenantLicense).filter(
            TenantLicense.tenant_id == tenant_id
        ).with_for_update().first()
        if row is None:
            raise PlatformNotFound("Licenca nao encontrada.", code="LicenseNotFound")
        normalized_action = action.strip().lower().replace("-", "_")
        before = _columns(row)
        previous = row.status
        now = utcnow()

        def require_days() -> int:
            if body.days is None:
                raise PlatformValidationError(
                    f"A acao '{normalized_action}' exige quantidade de dias.",
                    code="LicenseActionDaysRequired",
                )
            return body.days

        def clear_restrictions() -> None:
            row.suspended_at = None
            row.suspension_reason = None
            row.blocked_at = None
            row.block_reason = None
            row.cancelled_at = None
            row.cancellation_reason = None

        if normalized_action == "renew":
            days = require_days()
            base = row.expires_at if row.expires_at and row.expires_at > now else now
            row.expires_at = base + timedelta(days=days)
            row.status = "active"
            clear_restrictions()
        elif normalized_action == "extend":
            if row.status not in {"trial", "active", "grace_period"}:
                raise PlatformConflict(
                    f"Licenca em estado '{row.status}' nao pode ser prorrogada.",
                    code="LicenseStateConflict",
                )
            days = require_days()
            if row.status == "trial":
                base = row.trial_ends_at if row.trial_ends_at and row.trial_ends_at > now else now
                row.trial_ends_at = base + timedelta(days=days)
                row.expires_at = row.trial_ends_at
            else:
                base = row.expires_at if row.expires_at and row.expires_at > now else now
                row.expires_at = base + timedelta(days=days)
                if row.status == "grace_period":
                    row.grace_period_ends_at = row.expires_at + timedelta(
                        days=row.grace_period_days
                    )
        elif normalized_action in {"start_trial", "trial"}:
            if row.status not in {"expired", "cancelled"}:
                raise PlatformConflict(
                    "Trial so pode iniciar para licenca expirada ou cancelada.",
                    code="LicenseStateConflict",
                )
            days = require_days()
            row.status = "trial"
            row.starts_at = now
            row.trial_ends_at = now + timedelta(days=days)
            row.expires_at = row.trial_ends_at
            row.grace_period_ends_at = None
            clear_restrictions()
        elif normalized_action in {"convert_trial", "convert"}:
            if row.status != "trial":
                raise PlatformConflict(
                    "Somente trial pode ser convertido em licenca ativa.",
                    code="LicenseStateConflict",
                )
            row.status = "active"
            if body.days is not None:
                base = row.trial_ends_at if row.trial_ends_at and row.trial_ends_at > now else now
                row.expires_at = base + timedelta(days=body.days)
            clear_restrictions()
        elif normalized_action == "courtesy":
            days = require_days()
            base = row.expires_at if row.expires_at and row.expires_at > now else now
            row.expires_at = base + timedelta(days=days)
            row.status = "active"
            clear_restrictions()
        elif normalized_action in {"grace", "grace_period"}:
            if row.status not in {"active", "expired"}:
                raise PlatformConflict(
                    f"Licenca em estado '{row.status}' nao pode entrar em carencia.",
                    code="LicenseStateConflict",
                )
            days = require_days()
            if row.expires_at is None or row.expires_at > now:
                row.expires_at = now
            row.status = "grace_period"
            row.grace_period_ends_at = now + timedelta(days=days)
        elif normalized_action == "expire":
            if row.status in {"expired", "cancelled"}:
                raise PlatformConflict(
                    f"Licenca ja esta em estado final '{row.status}'.",
                    code="LicenseStateConflict",
                )
            row.status = "expired"
            row.expires_at = now
            row.grace_period_ends_at = None
        elif normalized_action == "cancel":
            if row.status == "cancelled":
                raise PlatformConflict(
                    "Licenca ja esta cancelada.",
                    code="LicenseStateConflict",
                )
            row.status = "cancelled"
            row.cancelled_at = now
            row.cancellation_reason = body.reason
        elif normalized_action == "suspend":
            if row.status not in {"trial", "active", "grace_period"}:
                raise PlatformConflict(
                    f"Licenca em estado '{row.status}' nao pode ser suspensa.",
                    code="LicenseStateConflict",
                )
            row.status, row.suspended_at, row.suspension_reason = "suspended", now, body.reason
        elif normalized_action == "block":
            if row.status == "cancelled":
                raise PlatformConflict(
                    "Licenca cancelada nao pode ser bloqueada.",
                    code="LicenseStateConflict",
                )
            row.status, row.blocked_at, row.block_reason = "blocked", now, body.reason
        elif normalized_action == "reactivate":
            if row.status not in {"suspended", "blocked"}:
                raise PlatformConflict(
                    "Somente licenca suspensa ou bloqueada pode ser reativada.",
                    code="LicenseStateConflict",
                )
            if row.expires_at is not None and row.expires_at <= now:
                if body.days is None:
                    raise PlatformValidationError(
                        "Reativacao de licenca vencida exige quantidade de dias.",
                        code="LicenseActionDaysRequired",
                    )
                row.expires_at = now + timedelta(days=body.days)
            row.status = "active"
            clear_restrictions()
        else:
            raise PlatformValidationError(
                "Acao de licenca invalida.",
                code="InvalidLicenseAction",
            )
        row.updated_at = now
        event = TenantLicenseEvent(id=_id(), tenant_id=tenant_id, license_id=row.id,
            actor_user_id=getattr(actor, "id", None), event_type=f"license_{normalized_action}",
            previous_status=previous, new_status=row.status, reason=body.reason,
            metadata_json=json.dumps({"days": body.days}))
        self.db.add(event)
        self.audit.record(action=f"license_{normalized_action}", actor=actor, tenant_id=tenant_id,
            resource_type="tenant_license", resource_id=row.id, before=before, after=row,
            reason=body.reason, request=request)
        self.db.commit()
        return self.license(tenant_id)

    def create_plan(self, body, *, actor, request=None) -> dict:
        if self.db.query(SaaSPlan.id).filter(SaaSPlan.key == body.key).first():
            raise PlatformConflict("Chave de plano ja cadastrada.", code="PlanKeyConflict")
        data = body.model_dump(exclude={"module_ids"})
        row = SaaSPlan(id=_id(), **data)
        self.db.add(row)
        self.db.flush()
        self._replace_plan_modules(row.id, body.module_ids)
        self.audit.record(action="plan_created", actor=actor, resource_type="saas_plan",
            resource_id=row.id, after=row, request=request)
        self.db.commit()
        return self.plan_out(row)

    def _replace_plan_modules(self, plan_id: str, module_ids: list[str]) -> None:
        modules = self.db.query(SaaSModule).filter(SaaSModule.id.in_(set(module_ids))).all() if module_ids else []
        if len(modules) != len(set(module_ids)):
            raise PlatformNotFound("Um ou mais modulos nao existem.", code="ModuleNotFound")
        selected_keys = {module.key for module in modules}
        missing_dependencies: set[str] = set()
        for module in modules:
            try:
                dependencies = json.loads(module.dependencies_json or "[]")
            except (TypeError, ValueError) as exc:
                raise PlatformValidationError(
                    f"Dependencias invalidas no modulo '{module.key}'.",
                    code="ModuleDependencyInvalid",
                ) from exc
            missing_dependencies.update(set(dependencies) - selected_keys)
        if missing_dependencies:
            raise PlatformValidationError(
                "Plano nao inclui dependencias obrigatorias: "
                + ", ".join(sorted(missing_dependencies)),
                code="PlanModuleDependencyMissing",
            )
        self.db.query(SaaSPlanModule).filter(SaaSPlanModule.plan_id == plan_id).delete(synchronize_session=False)
        for module in modules:
            self.db.add(SaaSPlanModule(id=_id(), plan_id=plan_id, module_id=module.id, enabled=True))

    def plan_out(self, row: SaaSPlan) -> dict:
        result = _columns(row)
        result["module_ids"] = [item[0] for item in self.db.query(SaaSPlanModule.module_id).filter(
            SaaSPlanModule.plan_id == row.id, SaaSPlanModule.enabled.is_(True)
        ).all()]
        return result

    def list_plans(self) -> list[dict]:
        return [self.plan_out(row) for row in self.db.query(SaaSPlan).order_by(SaaSPlan.display_order, SaaSPlan.name).all()]

    def update_plan(self, plan_id: str, body, *, actor, request=None) -> dict:
        row = self.db.query(SaaSPlan).filter(SaaSPlan.id == plan_id).first()
        if row is None:
            raise PlatformNotFound("Plano nao encontrado.", code="PlanNotFound")
        before = _columns(row)
        data = body.model_dump(exclude_unset=True)
        module_ids = data.pop("module_ids", None)
        reason = data.pop("reason", None)
        for key, value in data.items():
            setattr(row, key, value)
        if module_ids is not None:
            self._replace_plan_modules(row.id, module_ids)
        if row.status == "archived" and row.archived_at is None:
            row.archived_at = utcnow()
        self.audit.record(action="plan_changed", actor=actor, resource_type="saas_plan",
            resource_id=row.id, before=before, after=row, reason=reason, request=request)
        self.db.commit()
        return self.plan_out(row)

    def create_module(self, body, *, actor, request=None) -> dict:
        if self.db.query(SaaSModule.id).filter(SaaSModule.key == body.key).first():
            raise PlatformConflict("Chave de modulo ja cadastrada.", code="ModuleKeyConflict")
        self._validate_module_dependencies(body.key, body.dependencies)
        data = body.model_dump(exclude={"dependencies", "default_config"})
        row = SaaSModule(id=_id(), **data,
            dependencies_json=json.dumps(body.dependencies, ensure_ascii=False),
            default_config_json=json.dumps(body.default_config, ensure_ascii=False))
        self.db.add(row)
        self.audit.record(action="module_created", actor=actor, resource_type="saas_module",
            resource_id=row.id, after=row, request=request)
        self.db.commit()
        return _module_public(row)

    def _validate_module_dependencies(
        self,
        module_key: str,
        dependencies: list[str],
    ) -> None:
        normalized = list(dict.fromkeys(item.strip() for item in dependencies if item.strip()))
        if module_key in normalized:
            raise PlatformValidationError(
                "Modulo nao pode depender de si mesmo.",
                code="ModuleDependencySelfReference",
            )
        rows = self.db.query(SaaSModule).filter(SaaSModule.active.is_(True)).all()
        by_key = {row.key: row for row in rows}
        missing = sorted(set(normalized) - set(by_key))
        if missing:
            raise PlatformValidationError(
                f"Dependencias invalidas: {', '.join(missing)}.",
                code="ModuleDependencyNotFound",
            )
        graph = {}
        for key, module in by_key.items():
            try:
                graph[key] = list(json.loads(module.dependencies_json or "[]"))
            except (TypeError, ValueError):
                graph[key] = []
        graph[module_key] = normalized
        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(key: str) -> None:
            if key in visiting:
                raise PlatformValidationError(
                    "Dependencias de modulo formam um ciclo.",
                    code="ModuleDependencyCycle",
                )
            if key in visited:
                return
            visiting.add(key)
            for dependency in graph.get(key, []):
                visit(dependency)
            visiting.remove(key)
            visited.add(key)

        for key in graph:
            visit(key)

    def update_module(self, module_id: str, body, *, actor, request=None) -> dict:
        row = self.db.query(SaaSModule).filter(
            SaaSModule.id == module_id
        ).with_for_update().first()
        if row is None:
            raise PlatformNotFound("Modulo nao encontrado.", code="ModuleNotFound")
        before = _columns(row)
        data = body.model_dump(exclude_unset=True)
        reason = data.pop("reason")
        dependencies = data.pop("dependencies", None)
        default_config = data.pop("default_config", None)
        if (
            row.module_group == "integrations"
            and data.get("module_group") not in (None, "integrations")
        ):
            raise PlatformConflict(
                "Modulo de integracao nao pode mudar para grupo publico; "
                "isso poderia expor configuracoes write-only.",
                code="IntegrationModuleGroupLocked",
            )
        if data.get("active") is False and row.active:
            assigned = self.db.query(TenantModule.id).filter(
                TenantModule.module_id == row.id,
                TenantModule.enabled.is_(True),
            ).first() or self.db.query(SaaSPlanModule.id).filter(
                SaaSPlanModule.module_id == row.id,
                SaaSPlanModule.enabled.is_(True),
            ).first()
            dependent = next((
                module for module in self.db.query(SaaSModule).filter(
                    SaaSModule.active.is_(True),
                    SaaSModule.id != row.id,
                ).all()
                if row.key in json.loads(module.dependencies_json or "[]")
            ), None)
            if assigned or dependent:
                raise PlatformConflict(
                    "Modulo atribuido ou exigido por outro modulo nao pode ser desativado.",
                    code="ModuleStillInUse",
                )
        if dependencies is not None:
            self._validate_module_dependencies(row.key, dependencies)
            row.dependencies_json = json.dumps(dependencies, ensure_ascii=False)
        if default_config is not None:
            row.default_config_json = json.dumps(default_config, ensure_ascii=False)
        for key, value in data.items():
            setattr(row, key, value)
        row.updated_at = utcnow()
        self.audit.record(
            action="module_updated" if row.active else "module_archived",
            actor=actor,
            resource_type="saas_module",
            resource_id=row.id,
            before=before,
            after=row,
            reason=reason,
            request=request,
        )
        self.db.commit()
        return _module_public(row)

    def list_modules(self) -> list[dict]:
        return [_module_public(row) for row in self.db.query(SaaSModule).order_by(
            SaaSModule.module_group, SaaSModule.display_order, SaaSModule.name
        ).all()]

    def seed_module_catalog(self, *, actor, request=None) -> dict:
        existing = {
            row[0] for row in self.db.query(SaaSModule.key).filter(
                SaaSModule.key.in_([item[0] for item in PLATFORM_MODULE_CATALOG])
            ).all()
        }
        created_keys = []
        for key, name, group, order in PLATFORM_MODULE_CATALOG:
            if key in existing:
                continue
            row = SaaSModule(
                id=f"catalog_{key}",
                key=key,
                name=name,
                description=f"Modulo base: {name}.",
                module_group=group,
                active=True,
                display_order=order,
                dependencies_json="[]",
                default_config_json="{}",
            )
            self.db.add(row)
            created_keys.append(key)
        self.audit.record(
            action="module_catalog_seeded",
            actor=actor,
            resource_type="saas_module_catalog",
            after={"created_keys": created_keys, "catalog_size": len(PLATFORM_MODULE_CATALOG)},
            request=request,
        )
        try:
            self.db.commit()
        except IntegrityError:
            self.db.rollback()
            # A concurrent seed won. Re-read and report the converged catalog.
            created_keys = []
        return {
            "created_keys": created_keys,
            "catalog_size": len(PLATFORM_MODULE_CATALOG),
            "modules": self.list_modules(),
        }

    def create_invoice(self, tenant_id: str, body, *, actor, request=None) -> dict:
        self._tenant(tenant_id)
        plan = self.db.query(SaaSPlan).filter(SaaSPlan.id == body.plan_id).first() if body.plan_id else None
        if body.plan_id and plan is None:
            raise PlatformNotFound("Plano nao encontrado.", code="PlanNotFound")
        license_row = self.db.query(TenantLicense).filter(
            TenantLicense.tenant_id == tenant_id
        ).first()
        item_total = sum((item.unit_amount * item.quantity for item in body.items), Decimal("0"))
        base = _effective_contract_price(plan, license_row)
        total = base + item_total + body.additions_amount - body.discount_amount
        if total < 0:
            raise DomainError("Desconto nao pode superar o total da fatura.", code="InvalidInvoiceTotal")
        row = SaaSInvoice(id=_id(), tenant_id=tenant_id, plan_id=body.plan_id,
            period_start=body.period_start, period_end=body.period_end, due_at=body.due_at,
            base_amount=base, additions_amount=body.additions_amount + item_total,
            discount_amount=body.discount_amount, total_amount=total,
            status=body.status, notes=body.notes)
        self.db.add(row)
        for item in body.items:
            self.db.add(SaaSInvoiceItem(id=_id(), invoice_id=row.id, description=item.description,
                quantity=item.quantity, unit_amount=item.unit_amount,
                total_amount=item.unit_amount * item.quantity))
        self.audit.record(action="invoice_created", actor=actor, tenant_id=tenant_id,
            resource_type="saas_invoice", resource_id=row.id, after=row, request=request)
        self.db.commit()
        return _columns(row)

    def list_invoices(self, tenant_id: str) -> list[dict]:
        self._tenant(tenant_id)
        self._sync_overdue_invoices(tenant_id=tenant_id)
        return [_columns(row) for row in self.db.query(SaaSInvoice).filter(
            SaaSInvoice.tenant_id == tenant_id
        ).order_by(SaaSInvoice.due_at.desc()).all()]

    def register_payment(self, invoice_id: str, body, *, actor, request=None) -> dict:
        invoice = self.db.query(SaaSInvoice).filter(
            SaaSInvoice.id == invoice_id
        ).with_for_update().first()
        if invoice is None:
            raise PlatformNotFound("Fatura nao encontrada.", code="InvoiceNotFound")
        invoice_tenant_id = invoice.tenant_id
        if body.reference:
            existing = self.db.query(SaaSPayment).filter(
                SaaSPayment.tenant_id == invoice_tenant_id,
                SaaSPayment.reference == body.reference,
            ).first()
            if existing:
                if existing.invoice_id != invoice.id or existing.amount != body.amount:
                    raise PlatformConflict(
                        "Referencia de pagamento ja utilizada com outro payload.",
                        code="PaymentReferenceConflict",
                    )
                self.audit.record(action="payment_idempotent_replayed", actor=actor,
                    tenant_id=invoice_tenant_id, resource_type="saas_payment",
                    resource_id=existing.id, request=request,
                    metadata={"reference": body.reference})
                self.db.commit()
                return {"payment": _columns(existing), "invoice": _columns(invoice),
                    "idempotent_replay": True}
        if invoice.status in {"paid", "cancelled", "refunded", "courtesy"}:
            raise PlatformConflict(
                f"Fatura em estado final '{invoice.status}' nao aceita pagamento.",
                code="InvoiceFinalState",
            )
        paid_total = self.db.query(func.coalesce(func.sum(SaaSPayment.amount), 0)).filter(
            SaaSPayment.invoice_id == invoice.id,
            SaaSPayment.status.in_(("registered", "confirmed")),
        ).scalar()
        if Decimal(str(paid_total)) + body.amount > invoice.total_amount:
            raise DomainError("Pagamento supera o saldo da fatura.", code="PaymentExceedsInvoice")
        row = SaaSPayment(id=_id(), tenant_id=invoice_tenant_id, invoice_id=invoice.id,
            amount=body.amount, payment_method=body.payment_method, status="confirmed",
            paid_at=body.paid_at, reference=body.reference, notes=body.notes,
            registered_by=getattr(actor, "id", None))
        self.db.add(row)
        if Decimal(str(paid_total)) + body.amount == invoice.total_amount:
            invoice.status, invoice.paid_at, invoice.payment_method = "paid", body.paid_at, body.payment_method
        self.audit.record(action="payment_registered", actor=actor, tenant_id=invoice_tenant_id,
            resource_type="saas_payment", resource_id=row.id, after=row, request=request)
        try:
            self.db.commit()
        except IntegrityError:
            self.db.rollback()
            if not body.reference:
                raise
            existing = self.db.query(SaaSPayment).filter(
                SaaSPayment.tenant_id == invoice_tenant_id,
                SaaSPayment.reference == body.reference,
            ).first()
            if existing is None or existing.invoice_id != invoice_id or existing.amount != body.amount:
                raise PlatformConflict(
                    "Referencia de pagamento ja utilizada com outro payload.",
                    code="PaymentReferenceConflict",
                )
            self.audit.record(action="payment_idempotent_replayed", actor=actor,
                tenant_id=existing.tenant_id, resource_type="saas_payment",
                resource_id=existing.id, request=request,
                metadata={"reference": body.reference, "after_unique_race": True})
            self.db.commit()
            refreshed_invoice = self.db.query(SaaSInvoice).filter(
                SaaSInvoice.id == invoice_id
            ).first()
            return {"payment": _columns(existing), "invoice": _columns(refreshed_invoice),
                "idempotent_replay": True}
        return {"payment": _columns(row), "invoice": _columns(invoice)}

    def _locked_mutable_invoice(
        self,
        invoice_id: str,
        *,
        allowed_statuses: set[str],
        action: str,
    ) -> SaaSInvoice:
        row = self.db.query(SaaSInvoice).filter(
            SaaSInvoice.id == invoice_id
        ).with_for_update().first()
        if row is None:
            raise PlatformNotFound("Fatura nao encontrada.", code="InvoiceNotFound")
        if row.status not in allowed_statuses:
            raise PlatformConflict(
                f"Fatura em estado '{row.status}' nao permite {action}.",
                code="InvoiceStateConflict",
            )
        return row

    def discount_invoice(self, invoice_id: str, body, *, actor, request=None) -> dict:
        row = self._locked_mutable_invoice(
            invoice_id,
            allowed_statuses={"draft", "pending", "overdue", "negotiated"},
            action="desconto",
        )
        before = _columns(row)
        gross = Decimal(str(row.base_amount)) + Decimal(str(row.additions_amount))
        if body.amount > gross:
            raise PlatformValidationError(
                "Desconto nao pode superar o valor bruto da fatura.",
                code="InvoiceDiscountExceedsGross",
            )
        paid_total = Decimal(str(
            self.db.query(func.coalesce(func.sum(SaaSPayment.amount), 0)).filter(
                SaaSPayment.invoice_id == row.id,
                SaaSPayment.status.in_(("registered", "confirmed")),
            ).scalar()
        ))
        if paid_total > gross - body.amount:
            raise PlatformConflict(
                "Desconto deixaria o total abaixo do valor ja pago.",
                code="InvoiceDiscountBelowPaidAmount",
            )
        if gross - body.amount == 0 and paid_total == 0:
            raise PlatformValidationError(
                "Use a acao de cortesia para zerar uma fatura sem pagamento.",
                code="InvoiceDiscountRequiresCourtesy",
            )
        row.discount_amount = body.amount
        row.total_amount = gross - body.amount
        if paid_total == row.total_amount and paid_total > 0:
            latest_payment = self.db.query(SaaSPayment).filter(
                SaaSPayment.invoice_id == row.id,
                SaaSPayment.status.in_(("registered", "confirmed")),
            ).order_by(SaaSPayment.paid_at.desc()).first()
            row.status = "paid"
            row.paid_at = latest_payment.paid_at if latest_payment else utcnow()
            row.payment_method = latest_payment.payment_method if latest_payment else row.payment_method
        row.updated_at = utcnow()
        self.audit.record(
            action="invoice_discounted",
            actor=actor,
            tenant_id=row.tenant_id,
            resource_type="saas_invoice",
            resource_id=row.id,
            before=before,
            after=row,
            reason=body.reason,
            request=request,
        )
        self.db.commit()
        return _columns(row)

    def courtesy_invoice(self, invoice_id: str, body, *, actor, request=None) -> dict:
        row = self._locked_mutable_invoice(
            invoice_id,
            allowed_statuses={"draft", "pending", "overdue", "negotiated"},
            action="cortesia",
        )
        before = _columns(row)
        if self.db.query(SaaSPayment.id).filter(
            SaaSPayment.invoice_id == row.id,
            SaaSPayment.status.in_(("registered", "confirmed")),
        ).first():
            raise PlatformConflict(
                "Fatura com pagamento registrado nao pode receber cortesia.",
                code="InvoiceCourtesyHasPayments",
            )
        gross = Decimal(str(row.base_amount)) + Decimal(str(row.additions_amount))
        row.discount_amount = gross
        row.total_amount = Decimal("0")
        row.status = "courtesy"
        row.updated_at = utcnow()
        self.audit.record(
            action="invoice_courtesy_granted",
            actor=actor,
            tenant_id=row.tenant_id,
            resource_type="saas_invoice",
            resource_id=row.id,
            before=before,
            after=row,
            reason=body.reason,
            request=request,
        )
        self.db.commit()
        return _columns(row)

    def extend_invoice_due_date(self, invoice_id: str, body, *, actor, request=None) -> dict:
        row = self._locked_mutable_invoice(
            invoice_id,
            allowed_statuses={"draft", "pending", "overdue", "negotiated"},
            action="prorrogacao",
        )
        if body.due_at <= row.due_at:
            raise PlatformValidationError(
                "Nova data precisa ser posterior ao vencimento atual.",
                code="InvoiceDueDateNotExtended",
            )
        before = _columns(row)
        row.due_at = body.due_at
        if row.status == "overdue":
            row.status = "pending"
        row.updated_at = utcnow()
        self.audit.record(
            action="invoice_due_date_extended",
            actor=actor,
            tenant_id=row.tenant_id,
            resource_type="saas_invoice",
            resource_id=row.id,
            before=before,
            after=row,
            reason=body.reason,
            request=request,
        )
        self.db.commit()
        return _columns(row)

    def cancel_invoice(self, invoice_id: str, body, *, actor, request=None) -> dict:
        row = self._locked_mutable_invoice(
            invoice_id,
            allowed_statuses={"draft", "pending", "overdue", "negotiated"},
            action="cancelamento",
        )
        confirmed_payments = self.db.query(SaaSPayment.id).filter(
            SaaSPayment.invoice_id == row.id,
            SaaSPayment.status.in_(("registered", "confirmed")),
        ).first()
        if confirmed_payments:
            raise PlatformConflict(
                "Fatura com pagamento registrado nao pode ser cancelada.",
                code="InvoiceHasPayments",
            )
        before = _columns(row)
        row.status = "cancelled"
        row.updated_at = utcnow()
        self.audit.record(
            action="invoice_cancelled",
            actor=actor,
            tenant_id=row.tenant_id,
            resource_type="saas_invoice",
            resource_id=row.id,
            before=before,
            after=row,
            reason=body.reason,
            request=request,
        )
        self.db.commit()
        return _columns(row)

    def invoice_history(self, invoice_id: str) -> list[dict]:
        row = self.db.query(SaaSInvoice).filter(SaaSInvoice.id == invoice_id).first()
        if row is None:
            raise PlatformNotFound("Fatura nao encontrada.", code="InvoiceNotFound")
        payment_ids = [
            item[0] for item in self.db.query(SaaSPayment.id).filter(
                SaaSPayment.invoice_id == invoice_id
            ).all()
        ]
        resource_ids = [invoice_id, *payment_ids]
        return [
            _columns(event)
            for event in self.db.query(PlatformAuditLog).filter(
                PlatformAuditLog.tenant_id == row.tenant_id,
                PlatformAuditLog.resource_id.in_(resource_ids),
            ).order_by(PlatformAuditLog.created_at.desc()).all()
        ]

    def start_support(self, body, *, actor, request=None) -> dict:
        self._tenant(body.tenant_id)
        if body.target_user_id:
            membership = self.db.query(TenantMembership).filter(
                TenantMembership.tenant_id == body.tenant_id,
                TenantMembership.user_id == body.target_user_id,
                TenantMembership.status == "active",
            ).first()
            if membership is None:
                raise PlatformNotFound("Usuario alvo nao pertence ao tenant.", code="TargetMembershipNotFound")
        raw_token = secrets.token_urlsafe(32)
        row = SupportSession(id=_id(), tenant_id=body.tenant_id,
            actor_user_id=actor.id, target_user_id=body.target_user_id,
            reason=body.reason, status="active", token_hash=hashlib.sha256(raw_token.encode()).hexdigest(),
            starts_at=utcnow(), expires_at=utcnow() + timedelta(minutes=body.duration_minutes),
            ip_address=request.client.host if request is not None and request.client else None,
            user_agent=request.headers.get("user-agent") if request is not None else None)
        self.db.add(row)
        self.audit.record(action="support_session_started", actor=actor, tenant_id=body.tenant_id,
            resource_type="support_session", resource_id=row.id, after=row,
            reason=body.reason, request=request)
        self.db.commit()
        return {"session": _support_public(row), "support_token": raw_token}

    def exchange_support_token(self, body, *, request=None) -> dict:
        token_hash = hashlib.sha256(body.support_token.encode()).hexdigest()
        row = self.db.query(SupportSession).filter(
            SupportSession.token_hash == token_hash
        ).with_for_update().first()
        if row is None:
            raise PlatformNotFound(
                "Token de suporte invalido.",
                code="SupportTokenNotFound",
            )
        now = utcnow()
        if row.status != "active":
            raise PlatformConflict(
                "Sessao de suporte nao esta ativa.",
                code="SupportSessionNotActive",
            )
        if row.expires_at <= now:
            row.status = "expired"
            row.ended_at = now
            self.db.commit()
            raise PlatformConflict(
                "Sessao de suporte expirada.",
                code="SupportSessionExpired",
            )
        if row.exchanged_at is not None:
            raise PlatformConflict(
                "Token de suporte ja foi consumido.",
                code="SupportTokenAlreadyExchanged",
            )
        actor = self.db.query(AdminUser).filter(
            AdminUser.id == row.actor_user_id,
            AdminUser.active.is_(True),
        ).first()
        if actor is None:
            raise PlatformConflict(
                "Autor da sessao de suporte esta inativo.",
                code="SupportSessionActorInactive",
            )
        row.exchanged_at = now
        row.last_seen_at = now
        access_token = create_access_token(
            subject=actor.id,
            extra={
                "email": actor.email,
                "name": actor.name,
                "role_id": actor.role_id,
                "auth_version": int(getattr(actor, "auth_version", 0) or 0),
                "token_kind": "support",
                "support_session_id": row.id,
                "tenant_id": row.tenant_id,
                "support": True,
            },
            expires_at=row.expires_at,
        )
        self.audit.record(
            action="support_session_consumed",
            actor=actor,
            tenant_id=row.tenant_id,
            resource_type="support_session",
            resource_id=row.id,
            after=_support_public(row),
            request=request,
        )
        self.db.commit()
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "expires_at": row.expires_at,
            "tenant_id": row.tenant_id,
            "support_session_id": row.id,
        }

    def end_support(self, session_id: str, *, actor, request=None) -> dict:
        row = self.db.query(SupportSession).filter(
            SupportSession.id == session_id
        ).with_for_update().first()
        if row is None:
            raise PlatformNotFound("Sessao de suporte nao encontrada.", code="SupportSessionNotFound")
        if row.actor_user_id != actor.id:
            raise DomainError("Somente o autor pode encerrar esta sessao.", code="SupportSessionActorMismatch")
        if row.status in {"ended", "revoked", "expired"}:
            return _support_public(row)
        row.status, row.ended_at = "ended", utcnow()
        self.audit.record(action="support_session_ended", actor=actor, tenant_id=row.tenant_id,
            resource_type="support_session", resource_id=row.id, after=row, request=request)
        self.db.commit()
        return _support_public(row)

    def audit_page(self, *, page: int, page_size: int, tenant_id: str | None, action: str | None) -> dict:
        query = self.db.query(PlatformAuditLog)
        if tenant_id:
            query = query.filter(PlatformAuditLog.tenant_id == tenant_id)
        if action:
            query = query.filter(PlatformAuditLog.action == action)
        total = query.count()
        rows = query.order_by(PlatformAuditLog.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
        return {"items": [_columns(row) for row in rows], "total": total, "page": page,
            "page_size": page_size, "pages": math.ceil(total / page_size) if total else 0}
