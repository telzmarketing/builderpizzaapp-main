from datetime import datetime, timezone
import pytest
from backend.models.tenant_domain import TenantDomain
from backend.services.tenant_domain_service import (
    TenantDomainService, parse_hostname_set, remote_is_trusted,
    trusted_request_hostname, verification_token_hash,
)


def test_proxy_header_is_ignored_by_default() -> None:
    assert trusted_request_hostname(direct_host="safe.example.com", forwarded_host="evil.example.com",
        remote_addr="10.0.0.5", trust_proxy_headers=False, trusted_proxy_ips="10.0.0.0/8") == "safe.example.com"


def test_proxy_header_requires_trusted_sender() -> None:
    assert trusted_request_hostname(direct_host="proxy.internal", forwarded_host="store.example.com",
        remote_addr="10.0.0.5", trust_proxy_headers=True, trusted_proxy_ips="10.0.0.0/8") == "store.example.com"
    assert not remote_is_trusted("203.0.113.9", "10.0.0.0/8")


def test_platform_hosts_are_normalized() -> None:
    assert parse_hostname_set("Painel.Example.com, login.example.com.") == {"painel.example.com", "login.example.com"}


def test_verification_then_activation_is_required() -> None:
    service = TenantDomainService(db=None)
    token = "proof"
    domain = TenantDomain(id="domain-1", tenant_id="tenant-1", hostname="store.example.com",
        kind="custom", status="pending", verification_token_hash=verification_token_hash(token),
        created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc))
    with pytest.raises(ValueError, match="verificado"):
        service.activate(domain)
    service.confirm_verification(domain, token)
    service.activate(domain)
    assert domain.status == "active"
    assert domain.verified_at is not None and domain.activated_at is not None


def test_wrong_verification_proof_does_not_publish() -> None:
    service = TenantDomainService(db=None)
    domain = TenantDomain(status="pending", verification_token_hash=verification_token_hash("correct"))
    with pytest.raises(ValueError, match="invalida"):
        service.confirm_verification(domain, "wrong")
    assert domain.status == "pending"
