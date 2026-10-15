import importlib.util
import ipaddress
from datetime import timedelta
import contextlib
from io import StringIO
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from backend.database import Base
from backend.models.admin import AdminUser
from backend.models.platform_audit import PlatformAuditLog
from backend.models.platform_operations import PlatformWorkerHeartbeat
from backend.models.tenant import Tenant
from backend.models.tenant_domain import TenantDomain
from backend.models.tenant_domain_ssl import TenantDomainCertificateJob as Job
from backend.schemas.tenant_domain_ssl import CertificateRequestIn, CertificateSummaryOut
from backend.services import tenant_domain_ssl_service as ssl_service
from backend.services.tenant_domain_service import TenantDomainService

ROOT = Path(__file__).parents[1]


@pytest.fixture
def scenario(monkeypatch):
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine, tables=[Tenant.__table__, TenantDomain.__table__,
        AdminUser.__table__, Job.__table__, PlatformWorkerHeartbeat.__table__, PlatformAuditLog.__table__])
    with engine.begin() as connection:
        connection.exec_driver_sql("DROP INDEX uq_tenant_domains_primary_active")
        connection.exec_driver_sql("DROP INDEX uq_tenants_single_legacy")
        connection.exec_driver_sql("PRAGMA foreign_keys=ON")
    db = sessionmaker(bind=engine, expire_on_commit=False)()
    now = ssl_service.utcnow()
    tenant = Tenant(id="tenant-a", slug="tenant-a", name="A", status="active")
    admin = AdminUser(id="master", email="master@example.com", name="Master", password_hash="unused")
    domain = TenantDomain(id="domain-a", tenant_id="tenant-a", hostname="store.example.com", kind="custom",
        status="verified", verified_at=now, verification_token_hash="a" * 64, ssl_status="pending")
    db.add_all([tenant, admin])
    db.commit()
    db.add(domain)
    db.commit()
    settings = SimpleNamespace(TENANT_DOMAIN_SSL_ENABLED=True, TENANT_DOMAIN_SSL_PUBLIC_IPS="8.8.8.8",
        TENANT_DOMAIN_SSL_LEASE_SECONDS=900, TENANT_DOMAIN_SSL_COOLDOWN_SECONDS=3600,
        TENANT_DOMAIN_SSL_HEARTBEAT_SECONDS=300, TENANT_DOMAINS_PLATFORM_HOSTNAMES="app.example.com")
    monkeypatch.setattr(ssl_service, "get_settings", lambda: settings)
    monkeypatch.setattr(ssl_service, "resolve_public_addresses", lambda host, **kwargs: frozenset([ipaddress.ip_address("8.8.8.8")]))
    certificate = {"issued_at": now, "expires_at": now + timedelta(days=90), "fingerprint": "b" * 64}
    installed = {"value": False}
    def probe(host, **kwargs):
        if not installed["value"]:
            raise ssl_service.CertificateError("TLS_INVALID")
        return certificate
    monkeypatch.setattr(ssl_service, "probe_certificate", probe)
    service = ssl_service.TenantDomainSSLService(db)
    assert service.claim() is None
    yield SimpleNamespace(db=db, domain=domain, tenant=tenant, admin=admin, service=service,
        settings=settings, certificate=certificate, installed=installed)
    db.close()
    engine.dispose()


def request_job(s, key=None, email="admin@example.com"):
    return s.service.enqueue(s.domain.id, CertificateRequestIn(email=email, accept_terms=True), key or uuid4(), actor=s.admin)


def test_input_requires_valid_email_and_consent_and_worker_rejects_tls_claims():
    for body in ({"email": "invalid", "accept_terms": True}, {"email": "a@example.com", "accept_terms": False},
                 {"email": "o'brien@example.com", "accept_terms": True}):
        with pytest.raises(ValidationError):
            CertificateRequestIn(**body)
    from backend.schemas.tenant_domain_ssl import WorkerLeaseIn
    with pytest.raises(ValidationError):
        WorkerLeaseIn(job_id=uuid4(), lease_token="x" * 40, expires_at="2099")


def test_readiness_requires_config_and_recent_worker(scenario):
    s = scenario
    assert s.service.available()
    s.settings.TENANT_DOMAIN_SSL_ENABLED = False
    assert not s.service.available()
    s.settings.TENANT_DOMAIN_SSL_ENABLED = True
    s.db.query(PlatformWorkerHeartbeat).one().last_heartbeat_at = ssl_service.utcnow() - timedelta(hours=1)
    s.db.commit()
    assert not s.service.available()
    with pytest.raises(ssl_service.CertificateError) as error:
        request_job(s)
    assert error.value.http_status == 503


def test_auto_projection_drives_api_targets_with_default_flag_false(scenario, monkeypatch):
    from backend.core import domain_ssl_runtime
    s = scenario
    s.settings.TENANT_DOMAIN_SSL_MODE = "auto"
    s.settings.TENANT_DOMAIN_SSL_ENABLED = False
    projection = domain_ssl_runtime.DomainSSLRuntime(True, ("1.1.1.1",), ("master.example.com",))
    monkeypatch.setattr(domain_ssl_runtime, "read_runtime", lambda: projection)
    assert s.service.available()
    assert s.service.summary(s.domain.id)["dns_targets"] == ["1.1.1.1"]
    assert ssl_service.platform_hosts() == frozenset(["master.example.com"])
    s.settings.TENANT_DOMAIN_SSL_MODE = "disabled"
    assert not s.service.available()


def test_cli_heartbeat_does_not_claim_or_create_jobs(scenario):
    from backend.scripts.tenant_domain_ssl_queue import execute
    assert execute("heartbeat", {}, scenario.db) == {"status": "ready"}
    assert scenario.db.query(Job).count() == 0


def test_summary_exposes_only_approved_public_dns_targets_and_reserves_platform_host(scenario):
    s = scenario
    assert s.service.summary(s.domain.id)["dns_targets"] == ["8.8.8.8"]
    s.settings.TENANT_DOMAIN_SSL_PUBLIC_IPS = "127.0.0.1"
    summary = s.service.summary(s.domain.id)
    assert summary["dns_targets"] == [] and not summary["available"]
    s.settings.TENANT_DOMAIN_SSL_PUBLIC_IPS = "8.8.8.8"
    s.settings.TENANT_DOMAINS_PLATFORM_HOSTNAMES = ""
    assert not s.service.summary(s.domain.id)["available"]
    with pytest.raises(ssl_service.CertificateError) as error:
        request_job(s)
    assert error.value.http_status == 503


def test_completion_requires_live_tls_and_never_accepts_helper_claims(scenario):
    s = scenario
    request_job(s)
    claim = s.service.claim()
    with pytest.raises(ssl_service.CertificateError) as error:
        s.service.complete(claim["job_id"], claim["lease_token"])
    assert error.value.code == "TLS_INVALID"
    s.db.rollback()
    assert s.db.query(Job).one().status == "running"


def test_idempotency_and_single_open_job_do_not_duplicate_requests(scenario):
    s, key = scenario, uuid4()
    first = request_job(s, key)
    assert request_job(s, key)["job"]["id"] == first["job"]["id"]
    assert request_job(s)["job"]["id"] == first["job"]["id"]
    with pytest.raises(ssl_service.CertificateError, match="idempotencia"):
        request_job(s, key, email="different@example.com")
    assert s.db.query(Job).count() == 1
    public = CertificateSummaryOut.model_validate(first).model_dump_json()
    assert "lease_token" not in public and "email" not in public


def test_lease_fences_wrong_and_expired_worker_then_reconciles_installed_certificate(scenario):
    s = scenario
    request_job(s)
    claim = s.service.claim()
    assert claim["hostname"] == s.domain.hostname
    assert s.service.claim() is None
    with pytest.raises(ssl_service.CertificateError) as error:
        s.service.validate(claim["job_id"], "wrong" * 8)
    assert error.value.code == "CertificateLeaseInvalid"
    s.db.rollback()
    s.db.query(Job).one().lease_expires_at = ssl_service.utcnow() - timedelta(seconds=1)
    s.db.commit()
    with pytest.raises(ssl_service.CertificateError):
        s.service.complete(claim["job_id"], claim["lease_token"])
    s.db.rollback()
    s.installed["value"] = True
    assert s.service.reconcile()["reconciled"] == 1
    assert s.db.query(Job).one().status == "succeeded"


def test_completion_rechecks_suspension_and_never_publishes_domain(scenario):
    s = scenario
    request_job(s)
    claim = s.service.claim()
    s.domain.status = "suspended"
    s.db.commit()
    with pytest.raises(ssl_service.CertificateError) as error:
        s.service.complete(claim["job_id"], claim["lease_token"])
    assert error.value.code == "DOMAIN_INELIGIBLE"
    s.db.rollback()
    assert s.domain.status == "suspended"
    assert s.db.query(Job).one().status == "running"


def test_valid_served_certificate_is_reused_without_emission(scenario):
    s = scenario
    s.domain.status = "active"
    s.domain.ssl_status = "active"
    s.domain.ssl_issued_at = s.certificate["issued_at"]
    s.domain.ssl_expires_at = s.certificate["expires_at"]
    s.db.commit()
    s.installed["value"] = True
    result = request_job(s)
    assert result["job"]["status"] == "succeeded"
    assert s.service.claim() is None
    assert s.domain.status == "active"
    assert s.db.query(Job).one().attempts == 0


def test_renewal_reconcile_observes_dates_and_keeps_domain_active_on_failure(scenario, monkeypatch):
    s = scenario
    s.domain.status = "active"
    s.domain.ssl_status = "active"
    s.domain.ssl_issued_at = ssl_service.utcnow() - timedelta(days=60)
    s.domain.ssl_expires_at = ssl_service.utcnow() + timedelta(days=1)
    s.db.commit()
    s.installed["value"] = True
    assert s.service.reconcile()["refreshed"] == 1
    assert ssl_service.aware(s.domain.ssl_expires_at) == s.certificate["expires_at"]
    s.domain.last_checked_at = ssl_service.utcnow() - timedelta(hours=1)
    s.db.commit()
    def invalid(host, **kwargs):
        raise ssl_service.CertificateError("TLS_INVALID")
    monkeypatch.setattr(ssl_service, "probe_certificate", invalid)
    s.service.reconcile()
    assert s.domain.status == "active"
    assert s.domain.ssl_status == "error"
    assert s.domain.error_message == ssl_service.ERROR_MESSAGES["TLS_INVALID"]


def test_failure_and_later_retry_preserve_history_and_active_domain(scenario, monkeypatch):
    s = scenario
    request_job(s)
    claim = s.service.claim()
    s.domain.status, s.domain.ssl_status = "active", "active"
    s.db.commit()
    s.service.fail(claim["job_id"], claim["lease_token"], "CERTBOT_FAILED")
    assert s.domain.status == "active" and s.domain.ssl_status == "active"
    s.db.query(Job).one().created_at = ssl_service.utcnow() - timedelta(hours=2)
    s.db.commit()
    def invalid(host, **kwargs):
        raise ssl_service.CertificateError("TLS_INVALID")
    monkeypatch.setattr(ssl_service, "probe_certificate", invalid)
    assert request_job(s)["job"]["status"] == "queued"
    assert s.db.query(Job).count() == 2


def test_composite_fk_rejects_cross_tenant_owner(scenario):
    s = scenario
    request_job(s)
    s.db.add(Tenant(id="tenant-b", slug="tenant-b", name="B", status="active"))
    s.db.commit()
    s.db.query(Job).one().tenant_id = "tenant-b"
    with pytest.raises(IntegrityError):
        s.db.commit()
    s.db.rollback()


def test_existing_active_domain_activation_is_idempotent_without_tls(scenario, monkeypatch):
    scenario.domain.status = "active"
    def forbidden(host):
        raise AssertionError("Existing store must remain published")
    monkeypatch.setattr(ssl_service, "probe_certificate", forbidden)
    assert TenantDomainService(scenario.db).activate(scenario.domain).status == "active"


def test_master_ssl_error_filter_includes_active_domain_with_failed_certificate(scenario):
    from backend.models import customer, coupon, delivery, loyalty, payment, product, product_promotion, salao  # noqa: F401
    from backend.services.platform_master_service import PlatformMasterService
    s = scenario
    s.domain.status, s.domain.ssl_status = "active", "error"
    s.db.commit()
    result = PlatformMasterService(s.db).domain_page(page=1, page_size=20, status="ssl_error", q=None)
    assert result["total"] == 1
    assert result["items"][0]["status"] == "active"
    assert result["items"][0]["ssl_status"] == "error"
    assert PlatformMasterService(s.db).domain_page(page=1, page_size=20, status="dns_error", q=None)["total"] == 0


def test_forward_migration_has_composite_fk_partial_unique_and_safe_downgrade():
    spec = importlib.util.spec_from_file_location("ssl_migration", ROOT / "backend/migrations/versions/20261014_tenant_domain_ssl.py")
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    output = StringIO()
    context = MigrationContext.configure(dialect_name="postgresql", opts={"as_sql": True, "output_buffer": output})
    with Operations.context(context):
        migration.upgrade()
        with pytest.raises(RuntimeError, match="history"):
            migration.downgrade()
    assert "FOREIGN KEY(domain_id, tenant_id) REFERENCES tenant_domains (id, tenant_id)" in output.getvalue()
    assert "WHERE status IN ('queued','running')" in output.getvalue()
    assert migration.down_revision == "20261014_order_cancellation_tracking"


@pytest.mark.parametrize("records", [
    {"A": ["8.8.8.8", "127.0.0.1"], "AAAA": []},
    {"A": ["8.8.8.8"], "AAAA": ["::1"]},
    {"A": ["1.1.1.1"], "AAAA": []},
    {"A": [], "AAAA": []},
])
def test_dns_rejects_any_private_or_unconfigured_address(monkeypatch, records):
    monkeypatch.setattr(ssl_service, "get_settings", lambda: SimpleNamespace(TENANT_DOMAIN_SSL_MODE="manual",
        TENANT_DOMAIN_SSL_ENABLED=True, TENANT_DOMAIN_SSL_PUBLIC_IPS="8.8.8.8", TENANT_DOMAINS_PLATFORM_HOSTNAMES="app.example.com"))
    resolver = SimpleNamespace(resolve=lambda hostname, kind: records[kind])
    monkeypatch.setattr(ssl_service.dns.resolver, "Resolver", lambda: resolver)
    with pytest.raises(ssl_service.CertificateError) as error:
        ssl_service.resolve_public_addresses("store.example.com")
    assert error.value.code == "DNS_INVALID"


def test_tls_requires_ca_hostname_verification_and_pins_validated_address(monkeypatch):
    monkeypatch.setattr(ssl_service, "resolve_public_addresses", lambda host, **kwargs: frozenset([ipaddress.ip_address("8.8.8.8")]))
    calls = []
    def connect(target, timeout):
        calls.append(target)
        return contextlib.nullcontext(SimpleNamespace(settimeout=lambda timeout: None))
    monkeypatch.setattr(ssl_service.socket, "create_connection", connect)
    class Context:
        def wrap_socket(self, connection, server_hostname):
            assert server_hostname == "store.example.com"
            assert self.check_hostname is True
            assert self.verify_mode == ssl_service.ssl.CERT_REQUIRED
            assert self.hostname_checks_common_name is False
            raise ssl_service.ssl.SSLCertVerificationError("hostname mismatch")
    monkeypatch.setattr(ssl_service.ssl, "create_default_context", Context)
    with pytest.raises(ssl_service.CertificateError) as error:
        ssl_service.probe_certificate("store.example.com")
    assert error.value.code == "TLS_INVALID"
    assert calls == [("8.8.8.8", 443)]


def test_tls_accepts_wildcard_verified_by_ssl_context(monkeypatch):
    monkeypatch.setattr(ssl_service, "resolve_public_addresses", lambda host, **kwargs: frozenset([ipaddress.ip_address("8.8.8.8")]))
    monkeypatch.setattr(ssl_service.socket, "create_connection", lambda target, timeout: contextlib.nullcontext(SimpleNamespace(settimeout=lambda timeout: None)))
    class Context:
        def wrap_socket(self, connection, server_hostname):
            assert self.check_hostname and self.verify_mode == ssl_service.ssl.CERT_REQUIRED
            def cert(binary_form=False):
                return b"wildcard-certificate" if binary_form else {
                    "subjectAltName": [("DNS", "*.example.com")],
                    "notBefore": "Jan  1 00:00:00 2020 GMT", "notAfter": "Jan  1 00:00:00 2099 GMT"}
            return contextlib.nullcontext(SimpleNamespace(getpeercert=cert))
    monkeypatch.setattr(ssl_service.ssl, "create_default_context", Context)
    assert ssl_service.probe_certificate("store.example.com")["expires_at"].year == 2099


def test_existing_certificate_can_be_adopted_from_pending_metadata(scenario):
    scenario.installed["value"] = True
    assert scenario.domain.ssl_status == "pending"
    assert request_job(scenario)["job"]["status"] == "succeeded"
    assert scenario.service.claim() is None


def test_tls_rejects_expired_certificate_even_if_helper_claims_success(monkeypatch):
    monkeypatch.setattr(ssl_service, "resolve_public_addresses", lambda host, **kwargs: frozenset([ipaddress.ip_address("8.8.8.8")]))
    monkeypatch.setattr(ssl_service.socket, "create_connection", lambda target, timeout: contextlib.nullcontext(SimpleNamespace(settimeout=lambda timeout: None)))
    class Context:
        def wrap_socket(self, connection, server_hostname):
            return contextlib.nullcontext(SimpleNamespace(getpeercert=lambda **kw: {
                "subjectAltName": [("DNS", "store.example.com")],
                "notBefore": "Jan  1 00:00:00 2020 GMT", "notAfter": "Jan  1 00:00:00 2021 GMT"}))
    monkeypatch.setattr(ssl_service.ssl, "create_default_context", Context)
    with pytest.raises(ssl_service.CertificateError) as error:
        ssl_service.probe_certificate("store.example.com")
    assert error.value.code == "TLS_INVALID"


def add_second_request(s):
    domain = TenantDomain(id="domain-b", tenant_id=s.tenant.id, hostname="other.example.com", kind="custom",
        status="verified", verified_at=ssl_service.utcnow(), verification_token_hash="c" * 64, ssl_status="pending")
    s.db.add(domain)
    s.db.commit()
    return s.service.enqueue(domain.id, CertificateRequestIn(email="admin@example.com", accept_terms=True), uuid4(), actor=s.admin)


def test_claim_commits_failed_job_progress_before_later_worker_crash(scenario, monkeypatch):
    s = scenario
    request_job(s)
    add_second_request(s)
    calls = {"count": 0}
    def dns_failure(host, **kwargs):
        calls["count"] += 1
        if calls["count"] == 1:
            raise ssl_service.CertificateError("DNS_INVALID")
        raise RuntimeError("simulate worker crash")
    monkeypatch.setattr(ssl_service, "resolve_public_addresses", dns_failure)
    with pytest.raises(RuntimeError, match="worker crash"):
        s.service.claim()
    s.db.rollback()
    assert sorted(job.status for job in s.db.query(Job).all()) == ["failed", "queued"]


def test_reconcile_deadline_preserves_progress_and_leaves_next_job_for_next_run(scenario, monkeypatch):
    s = scenario
    request_job(s)
    add_second_request(s)
    s.service.claim()
    s.service.claim()
    for job in s.db.query(Job).all():
        job.lease_expires_at = ssl_service.utcnow() - timedelta(seconds=1)
    s.db.commit()
    clock = {"now": 0}
    monkeypatch.setattr(ssl_service.time, "monotonic", lambda: clock["now"])
    def timeout(host, **kwargs):
        assert kwargs["deadline"] == 60
        clock["now"] = 60
        raise ssl_service.CertificateError("TLS_INVALID")
    monkeypatch.setattr(ssl_service, "probe_certificate", timeout)
    assert s.service.reconcile()["reconciled"] == 1
    s.db.rollback()
    assert sorted(job.status for job in s.db.query(Job).all()) == ["failed", "running"]


def test_tls_deadline_fails_instead_of_accepting_partial_addresses(monkeypatch):
    clock = {"now": 0}
    monkeypatch.setattr(ssl_service.time, "monotonic", lambda: clock["now"])
    monkeypatch.setattr(ssl_service, "resolve_public_addresses", lambda host, **kwargs: frozenset([
        ipaddress.ip_address("8.8.8.8"), ipaddress.ip_address("1.1.1.1")]))
    calls = []
    def connect(target, timeout):
        calls.append(target)
        clock["now"] = 46
        return contextlib.nullcontext(SimpleNamespace(settimeout=lambda timeout: None))
    monkeypatch.setattr(ssl_service.socket, "create_connection", connect)
    with pytest.raises(ssl_service.CertificateError) as error:
        ssl_service.probe_certificate("store.example.com")
    assert error.value.code == "TLS_INVALID"
    assert len(calls) == 1
