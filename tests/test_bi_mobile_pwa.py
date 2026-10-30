import pytest

from backend.core.exceptions import DomainError
from backend.services.site_config_service import PWA_MANIFESTS, SiteConfigService, SiteIdentity


def test_bi_mobile_manifest_is_scoped_and_does_not_expose_tenant_data():
    service = SiteConfigService(None)
    service.read = lambda _request: (
        {"brand": {"name": "Loja Tenant", "pageTitle": "Loja Tenant"}},
        None,
        SiteIdentity(platform=False, tenant_id="tenant-1"),
    )

    manifest = service.manifest(object(), app="bi-mobile")

    assert manifest["id"] == "/painel/bi-mobile"
    assert manifest["scope"] == "/painel/bi-mobile/"
    assert manifest["start_url"] == "/painel/bi-mobile/"
    assert manifest["name"] == "BI Mobile"
    assert "tenant-1" not in str(manifest)


def test_existing_manifest_contract_is_unchanged_without_app_selector():
    service = SiteConfigService(None)
    service.read = lambda _request: (
        {"brand": {"name": "Telz", "pageTitle": "Telz"}},
        None,
        SiteIdentity(platform=True),
    )

    manifest = service.manifest(object())

    assert manifest["id"] == "/painel"
    assert manifest["scope"] == "/painel"


def test_all_supported_pwa_manifests_have_unique_installation_boundaries():
    assert set(PWA_MANIFESTS) == {
        "motoboy", "bi-mobile", "kds-principal", "kds-pizzaiolo",
        "kds-preparo", "kds-expedicao", "kds-motoboys", "kds-pdv",
        "kds-analitico",
    }

    service = SiteConfigService(None)
    service.read = lambda _request: (
        {"brand": {"name": "Loja Tenant", "pageTitle": "Loja Tenant"}},
        None,
        SiteIdentity(platform=False, tenant_id="tenant-1"),
    )

    manifests = [service.manifest(object(), app=app) for app in PWA_MANIFESTS]

    assert len({manifest["id"] for manifest in manifests}) == len(PWA_MANIFESTS)
    assert len({manifest["start_url"] for manifest in manifests}) == len(PWA_MANIFESTS)
    assert len({manifest["scope"] for manifest in manifests}) == len(PWA_MANIFESTS)
    assert {manifest["name"] for manifest in manifests} >= {
        "Motoboy", "BI Mobile", "KDS Principal", "KDS Pizzaiolo",
        "KDS Cozinha Preparo", "KDS Expedição", "KDS Motoboys",
        "KDS PDV", "KDS Analítico",
    }
    assert all(manifest["icons"][0]["src"].startswith("/api/site-config/favicon?") for manifest in manifests)


def test_unknown_manifest_app_is_rejected_without_fallback():
    service = SiteConfigService(None)

    with pytest.raises(DomainError) as raised:
        service.manifest(object(), app="kds-desconhecido")

    assert raised.value.http_status == 400
    assert raised.value.code == "InvalidManifestApp"
