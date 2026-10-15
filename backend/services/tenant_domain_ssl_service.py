"""Unprivileged certificate queue with DNS/TLS checks and fenced worker leases."""
from __future__ import annotations

import hashlib
import hmac
import ipaddress
import json
import secrets
import socket
import ssl
import time
import uuid
from datetime import datetime, timedelta, timezone

import dns.exception
import dns.resolver
from sqlalchemy import or_

from backend.config import get_settings
from backend.core.exceptions import DomainError
from backend.core.tenant_context import normalize_hostname
from backend.models.platform_operations import PlatformWorkerHeartbeat
from backend.models.tenant import Tenant
from backend.models.tenant_domain import TenantDomain
from backend.models.tenant_domain_ssl import TenantDomainCertificateJob as Job
from backend.services.platform_audit_service import PlatformAuditService


WORKER_KEY = "tenant_domain_ssl"
ERROR_MESSAGES = {
    "DNS_INVALID": "DNS deve apontar exclusivamente para os IPs publicos configurados.",
    "DOMAIN_INELIGIBLE": "Dominio ou empresa nao esta elegivel para emissao.",
    "CERTBOT_FAILED": "A emissao do certificado falhou.",
    "NGINX_FAILED": "A configuracao HTTPS nao pode ser instalada.",
    "TLS_INVALID": "O certificado HTTPS servido nao passou na validacao.",
    "WORKER_ERROR": "O executor de certificados encontrou uma falha.",
    "LEASE_EXPIRED": "O prazo da execucao expirou; solicite novamente.",
    "CertificateWorkerUnavailable": "O executor HTTPS esta indisponivel. Verifique a configuracao e tente novamente.",
    "DomainNotFound": "Dominio nao encontrado.",
    "CertificateJobNotFound": "Solicitacao de certificado nao encontrada.",
    "IdempotencyConflict": "Esta chave de idempotencia ja foi utilizada com outro pedido.",
    "CertificateCooldown": "Aguarde o intervalo entre tentativas de emissao.",
    "CertificateLeaseInvalid": "A execucao nao possui uma lease valida.",
}


class CertificateError(DomainError):
    def __init__(self, code, status=409):
        self.http_status = status
        super().__init__(ERROR_MESSAGES.get(code, "Operacao de certificado indisponivel."), code=code)


def utcnow():
    return datetime.now(timezone.utc)


def aware(value):
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def remaining(deadline, maximum):
    budget = deadline - time.monotonic()
    if budget <= 0:
        raise CertificateError("TLS_INVALID")
    return min(maximum, budget)


def public_ips(settings=None):
    settings = settings or get_settings()
    try:
        addresses = frozenset(ipaddress.ip_address(x.strip()) for x in settings.TENANT_DOMAIN_SSL_PUBLIC_IPS.split(",") if x.strip())
    except ValueError as exc:
        raise CertificateError("DNS_INVALID", 503) from exc
    if not addresses or any(not x.is_global for x in addresses):
        raise CertificateError("DNS_INVALID", 503)
    return addresses


def platform_hosts():
    try:
        hosts = frozenset(normalize_hostname(item) for item in get_settings().TENANT_DOMAINS_PLATFORM_HOSTNAMES.split(",") if item.strip())
    except ValueError as exc:
        raise CertificateError("CertificateWorkerUnavailable", 503) from exc
    if not hosts:
        raise CertificateError("CertificateWorkerUnavailable", 503)
    return hosts


def resolve_public_addresses(hostname, *, deadline=None):
    deadline = deadline if deadline is not None else time.monotonic() + 10
    allowed = public_ips()
    addresses = set()
    resolver = dns.resolver.Resolver()
    try:
        for kind in ("A", "AAAA"):
            resolver.timeout = remaining(deadline, 3)
            resolver.lifetime = remaining(deadline, 5)
            try:
                answers = resolver.resolve(hostname, kind)
            except dns.resolver.NoAnswer:
                continue
            addresses.update(ipaddress.ip_address(str(answer)) for answer in answers)
    except (dns.exception.DNSException, ValueError) as exc:
        raise CertificateError("DNS_INVALID", 422) from exc
    if not addresses or any(not address.is_global or address not in allowed for address in addresses):
        raise CertificateError("DNS_INVALID", 422)
    return frozenset(addresses)


def probe_certificate(hostname, *, deadline=None):
    """Pin each validated DNS address, keeping normal CA and hostname checks."""
    deadline = min(deadline, time.monotonic() + 45) if deadline is not None else time.monotonic() + 45
    hostname = normalize_hostname(hostname)
    addresses = resolve_public_addresses(hostname, deadline=deadline)
    context = ssl.create_default_context()
    context.check_hostname = True
    context.verify_mode = ssl.CERT_REQUIRED
    context.hostname_checks_common_name = False
    certificates = []
    try:
        for address in sorted(addresses, key=str):
            with socket.create_connection((str(address), 443), timeout=remaining(deadline, 5)) as connection:
                connection.settimeout(remaining(deadline, 5))
                with context.wrap_socket(connection, server_hostname=hostname) as secure:
                    remaining(deadline, 45)
                    cert = secure.getpeercert()
                    issued = datetime.fromtimestamp(ssl.cert_time_to_seconds(cert["notBefore"]), timezone.utc)
                    expires = datetime.fromtimestamp(ssl.cert_time_to_seconds(cert["notAfter"]), timezone.utc)
                    if issued > utcnow() or expires <= utcnow():
                        raise CertificateError("TLS_INVALID")
                    certificates.append((issued, expires, hashlib.sha256(secure.getpeercert(binary_form=True)).hexdigest()))
    except (OSError, ValueError, KeyError) as exc:
        raise CertificateError("TLS_INVALID") from exc
    if resolve_public_addresses(hostname, deadline=deadline) != addresses:
        raise CertificateError("DNS_INVALID")
    return {"issued_at": max(x[0] for x in certificates), "expires_at": min(x[1] for x in certificates), "fingerprint": certificates[0][2]}


class TenantDomainSSLService:
    def __init__(self, db):
        self.db = db

    def _configured(self):
        if not get_settings().TENANT_DOMAIN_SSL_ENABLED:
            raise CertificateError("CertificateWorkerUnavailable", 503)
        platform_hosts()
        public_ips()

    def available(self):
        try:
            self._configured()
        except CertificateError:
            return False
        recent = utcnow() - timedelta(seconds=get_settings().TENANT_DOMAIN_SSL_HEARTBEAT_SECONDS)
        return self.db.query(PlatformWorkerHeartbeat.id).filter(
            PlatformWorkerHeartbeat.worker_key == WORKER_KEY,
            PlatformWorkerHeartbeat.queue_key == WORKER_KEY,
            PlatformWorkerHeartbeat.status.in_(("idle", "running")),
            PlatformWorkerHeartbeat.last_heartbeat_at >= recent,
        ).first() is not None

    def _domain(self, domain_id, *, lock=False):
        query = self.db.query(TenantDomain).filter(TenantDomain.id == str(domain_id))
        if lock:
            query = query.with_for_update()
        domain = query.first()
        if domain is None:
            raise CertificateError("DomainNotFound", 404)
        return domain

    def _eligible(self, domain):
        tenant = self.db.query(Tenant).filter(Tenant.id == domain.tenant_id).with_for_update().first()
        if tenant is None or tenant.status != "active" or tenant.deleted_at is not None:
            raise CertificateError("DOMAIN_INELIGIBLE")
        if domain.status not in ("verified", "active") or domain.verified_at is None:
            raise CertificateError("DOMAIN_INELIGIBLE")
        hostname = normalize_hostname(domain.hostname)
        platform = platform_hosts()
        if hostname != domain.hostname or hostname in platform:
            raise CertificateError("DOMAIN_INELIGIBLE")
        return hostname

    def summary(self, domain_id, *, job=None):
        domain = self._domain(domain_id)
        if job is None:
            job = self.db.query(Job).filter(Job.domain_id == domain.id, Job.tenant_id == domain.tenant_id).order_by(Job.created_at.desc()).first()
        public_job = None
        if job:
            public_job = {key: getattr(job, key) for key in ("id", "status", "attempts", "created_at", "started_at", "finished_at", "error_code")}
            public_job["error_message"] = ERROR_MESSAGES.get(job.error_code)
        try:
            dns_targets = sorted(str(address) for address in public_ips())
        except CertificateError:
            dns_targets = []
        return {"available": self.available(), "domain_id": domain.id, "hostname": domain.hostname,
                "dns_targets": dns_targets,
                "ssl_status": domain.ssl_status, "ssl_issued_at": domain.ssl_issued_at,
                "ssl_expires_at": domain.ssl_expires_at, "job": public_job}

    def activation_certificate(self, domain):
        return probe_certificate(self._eligible(domain))

    def enqueue(self, domain_id, body, key, *, actor, request=None):
        domain = self._domain(domain_id, lock=True)
        self._configured()
        if not self.available():
            raise CertificateError("CertificateWorkerUnavailable", 503)
        key_hash = digest(str(uuid.UUID(str(key))))
        payload_hash = digest(json.dumps({"email": str(body.email), "accept_terms": body.accept_terms}, sort_keys=True))
        existing = self.db.query(Job).filter(Job.domain_id == domain.id, Job.idempotency_key_hash == key_hash).first()
        if existing:
            if existing.request_hash != payload_hash:
                raise CertificateError("IdempotencyConflict")
            return self.summary(domain.id, job=existing)
        hostname = self._eligible(domain)
        resolve_public_addresses(hostname)
        open_job = self.db.query(Job).filter(Job.domain_id == domain.id, Job.status.in_(("queued", "running"))).first()
        if open_job:
            return self.summary(domain.id, job=open_job)
        latest = self.db.query(Job).filter(Job.domain_id == domain.id).order_by(Job.created_at.desc()).first()
        now = utcnow()
        certificate = None
        try:
            certificate = probe_certificate(hostname)
        except CertificateError:
            pass
        if certificate is None and latest and aware(latest.created_at) > now - timedelta(seconds=get_settings().TENANT_DOMAIN_SSL_COOLDOWN_SECONDS):
            raise CertificateError("CertificateCooldown", 429)
        job = Job(id=str(uuid.uuid4()), domain_id=domain.id, tenant_id=domain.tenant_id,
                  hostname=hostname, email=str(body.email), requested_by=actor.id,
                  terms_accepted_at=now, idempotency_key_hash=key_hash, request_hash=payload_hash,
                  status="queued", attempts=0, created_at=now, updated_at=now)
        self.db.add(job)
        # Existing valid certificates remain represented while renewal is queued.
        if domain.ssl_status != "active":
            domain.ssl_status = "pending"
        PlatformAuditService(self.db).record(action="domain_certificate_requested", actor=actor,
            tenant_id=domain.tenant_id, resource_type="tenant_domain", resource_id=domain.id,
            metadata={"job_id": job.id, "terms_accepted_at": now}, request=request)
        if certificate is not None:
            self._finish_success(job, domain, certificate)
        self.db.commit()
        return self.summary(domain.id, job=job)

    def _heartbeat(self):
        # Single root-owned runner is serialized by flock, so one stable identity suffices.
        now = utcnow()
        row = self.db.query(PlatformWorkerHeartbeat).filter(
            PlatformWorkerHeartbeat.worker_key == WORKER_KEY,
            PlatformWorkerHeartbeat.instance_key == "certificate-runner",
        ).with_for_update().first()
        if row is None:
            row = PlatformWorkerHeartbeat(id=str(uuid.uuid4()), worker_key=WORKER_KEY,
                instance_key="certificate-runner", queue_key=WORKER_KEY, started_at=now,
                created_at=now, updated_at=now)
            self.db.add(row)
        row.status = "idle"
        row.last_heartbeat_at = now
        row.updated_at = now

    @staticmethod
    def _payload(job, token):
        return {"job_id": job.id, "lease_token": token, "domain_id": job.domain_id,
                "tenant_id": job.tenant_id, "hostname": job.hostname, "email": job.email}

    def claim(self):
        self._configured()
        self._heartbeat()
        deadline = time.monotonic() + 60
        ids = self.db.query(Job.id, Job.domain_id).filter(Job.status == "queued").order_by(Job.created_at).limit(5).all()
        for job_id, domain_id in ids:
            if time.monotonic() >= deadline:
                break
            domain = self.db.query(TenantDomain).filter(TenantDomain.id == domain_id).with_for_update(skip_locked=True).first()
            if domain is None:
                continue
            job = self.db.query(Job).filter(Job.id == job_id, Job.status == "queued").with_for_update(skip_locked=True).first()
            if job is None:
                continue
            try:
                hostname = self._eligible(domain)
                if job.tenant_id != domain.tenant_id or job.hostname != hostname:
                    raise CertificateError("DOMAIN_INELIGIBLE")
                resolve_public_addresses(hostname, deadline=deadline)
            except CertificateError as exc:
                self._finish_failure(job, domain, exc.code if exc.code in ERROR_MESSAGES else "DOMAIN_INELIGIBLE")
                self.db.commit()
                continue
            token = secrets.token_urlsafe(32)
            now = utcnow()
            job.status = "running"
            job.attempts += 1
            job.started_at = now
            job.updated_at = now
            job.lease_token_hash = digest(token)
            job.lease_expires_at = now + timedelta(seconds=get_settings().TENANT_DOMAIN_SSL_LEASE_SECONDS)
            self.db.commit()
            return self._payload(job, token)
        self.db.commit()
        return None

    def _lease(self, job_id, token, *, expired=False):
        snapshot = self.db.query(Job).filter(Job.id == str(job_id)).first()
        if snapshot is None:
            raise CertificateError("CertificateJobNotFound", 404)
        domain = self._domain(snapshot.domain_id, lock=True)
        job = self.db.query(Job).filter(Job.id == snapshot.id).populate_existing().with_for_update().first()
        if (job.status != "running" or not job.lease_token_hash
                or not hmac.compare_digest(job.lease_token_hash, digest(token))
                or job.lease_expires_at is None or (not expired and aware(job.lease_expires_at) <= utcnow())):
            raise CertificateError("CertificateLeaseInvalid")
        return job, domain

    def _validate(self, job, domain, *, deadline=None):
        self._configured()
        hostname = self._eligible(domain)
        if job.tenant_id != domain.tenant_id or job.hostname != hostname:
            raise CertificateError("DOMAIN_INELIGIBLE")
        resolve_public_addresses(hostname, deadline=deadline)

    def validate(self, job_id, token):
        job, domain = self._lease(job_id, token)
        self._validate(job, domain)
        payload = self._payload(job, token)
        self.db.commit()
        return payload

    def _finish_success(self, job, domain, certificate):
        now = utcnow()
        job.status = "succeeded"
        job.finished_at = now
        job.updated_at = now
        job.error_code = None
        job.certificate_fingerprint = certificate["fingerprint"]
        job.certificate_issued_at = certificate["issued_at"]
        job.certificate_expires_at = certificate["expires_at"]
        job.lease_token_hash = None
        job.lease_expires_at = None
        domain.ssl_status = "active"
        domain.ssl_issued_at = certificate["issued_at"]
        domain.ssl_expires_at = certificate["expires_at"]
        domain.last_checked_at = now
        domain.error_message = None
        domain.updated_at = now
        PlatformAuditService(self.db).record(action="domain_certificate_completed", actor=None,
            tenant_id=job.tenant_id, resource_type="tenant_domain", resource_id=domain.id,
            metadata={"job_id": job.id, "fingerprint": certificate["fingerprint"]})

    def complete(self, job_id, token):
        job, domain = self._lease(job_id, token)
        self._validate(job, domain)
        certificate = probe_certificate(job.hostname)
        if aware(job.lease_expires_at) <= utcnow():
            raise CertificateError("CertificateLeaseInvalid")
        self._finish_success(job, domain, certificate)
        self.db.commit()
        return self.summary(domain.id, job=job)

    def _finish_failure(self, job, domain, code):
        job.status = "failed"
        job.error_code = code
        job.finished_at = utcnow()
        job.updated_at = job.finished_at
        job.lease_token_hash = None
        job.lease_expires_at = None
        if domain.ssl_status != "active":
            domain.ssl_status = "error"
        PlatformAuditService(self.db).record(action="domain_certificate_failed", actor=None,
            tenant_id=job.tenant_id, resource_type="tenant_domain", resource_id=domain.id,
            metadata={"job_id": job.id, "error_code": code})

    def fail(self, job_id, token, code):
        if code not in {"DNS_INVALID", "DOMAIN_INELIGIBLE", "CERTBOT_FAILED", "NGINX_FAILED", "TLS_INVALID", "WORKER_ERROR", "LEASE_EXPIRED"}:
            raise CertificateError("CertificateInvalidErrorCode", 422)
        job, domain = self._lease(job_id, token)
        self._finish_failure(job, domain, code)
        self.db.commit()
        return self.summary(domain.id, job=job)

    def reconcile(self):
        self._configured()
        deadline = time.monotonic() + 60
        ids = self.db.query(Job.id, Job.domain_id).filter(Job.status == "running", Job.lease_expires_at <= utcnow()).limit(5).all()
        count = 0
        for job_id, domain_id in ids:
            if time.monotonic() >= deadline:
                break
            domain = self.db.query(TenantDomain).filter(TenantDomain.id == domain_id).with_for_update(skip_locked=True).first()
            if domain is None:
                continue
            job = self.db.query(Job).filter(Job.id == job_id).populate_existing().with_for_update().first()
            if job.status != "running" or aware(job.lease_expires_at) > utcnow():
                continue
            try:
                self._validate(job, domain, deadline=deadline)
                self._finish_success(job, domain, probe_certificate(job.hostname, deadline=deadline))
            except CertificateError as exc:
                self._finish_failure(job, domain, "DOMAIN_INELIGIBLE" if exc.code == "DOMAIN_INELIGIBLE" else "LEASE_EXPIRED")
            count += 1
            self.db.commit()
        self.db.commit()
        # Certbot renewal runs outside the queue. Refresh observed certificates
        # independently of completed jobs, without unpublishing active stores.
        cutoff = utcnow() - timedelta(minutes=15)
        domains = self.db.query(TenantDomain).filter(
            TenantDomain.status.in_(("verified", "active")),
            TenantDomain.ssl_issued_at.isnot(None),
            or_(TenantDomain.last_checked_at.is_(None), TenantDomain.last_checked_at < cutoff),
        ).order_by(TenantDomain.last_checked_at.asc().nullsfirst()).limit(max(0, 5 - count)).all()
        refreshed = 0
        for candidate in domains:
            if time.monotonic() >= deadline:
                break
            domain = self.db.query(TenantDomain).filter(TenantDomain.id == candidate.id).with_for_update(skip_locked=True).first()
            if domain is None:
                continue
            if domain.last_checked_at is not None and aware(domain.last_checked_at) >= cutoff:
                continue
            try:
                self._eligible(domain)
                certificate = probe_certificate(domain.hostname, deadline=deadline)
                domain.ssl_status = "active"
                domain.ssl_issued_at = certificate["issued_at"]
                domain.ssl_expires_at = certificate["expires_at"]
                domain.error_message = None
            except CertificateError as exc:
                domain.ssl_status = "error"
                domain.error_message = ERROR_MESSAGES.get(exc.code, ERROR_MESSAGES["TLS_INVALID"])
            domain.last_checked_at = utcnow()
            domain.updated_at = domain.last_checked_at
            refreshed += 1
            self.db.commit()
        self.db.commit()
        return {"reconciled": count, "refreshed": refreshed}
