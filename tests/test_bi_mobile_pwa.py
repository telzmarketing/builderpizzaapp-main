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
        "storefront",
        "motoboy", "bi-mobile", "kds-principal", "kds-pizzaiolo", "kds-esfiha",
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
        "Loja Tenant",
        "Motoboy", "BI Mobile", "KDS Principal", "KDS Pizzaiolo",
        "KDS Cozinha Preparo", "KDS Expedição", "KDS Motoboys",
        "KDS PDV", "KDS Analítico",
    }
    assert all(manifest["icons"][0]["src"].startswith("/api/site-config/favicon?") for manifest in manifests)


def test_storefront_manifest_uses_the_public_origin_as_installation_boundary():
    service = SiteConfigService(None)
    service.read = lambda _request: ({"brand": {"name": "Pizzaria", "pageTitle": "Pizzaria"}}, None, SiteIdentity(tenant_id="tenant-1"))

    manifest = service.manifest(object(), app="storefront")

    assert manifest["id"] == "/"
    assert manifest["start_url"] == "/"
    assert manifest["scope"] == "/"
    assert manifest["name"] == "Pizzaria"
    assert manifest["short_name"] == "Pizzaria"


def test_storefront_manifest_uses_safe_branding_fallback_and_short_name_limit():
    service = SiteConfigService(None)
    service.read = lambda _request: ({"brand": {"name": "N" * 40, "pageTitle": ""}}, None, SiteIdentity(tenant_id="tenant-1"))

    manifest = service.manifest(object(), app="storefront")

    assert manifest["name"] == "NNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNN"
    assert manifest["short_name"] == "N" * 24


def test_kds_manifests_start_from_the_operational_routes():
    service = SiteConfigService(None)
    service.read = lambda _request: ({"brand": {}}, None, SiteIdentity(tenant_id="tenant-1"))

    expected = {
        "kds-principal": ("/app/kds/principal", "/painel/kds/"),
        "kds-pizzaiolo": ("/app/kds/pizzaiolo", "/painel/cozinha/"),
        "kds-esfiha": ("/app/kds/esfiha", "/painel/esfiha/"),
        "kds-preparo": ("/app/kds/preparo", "/painel/preparo/"),
        "kds-expedicao": ("/app/kds/expedicao", "/painel/expedicao/"),
        "kds-motoboys": ("/app/kds/motoboys", "/painel/kds/sala-motoboy/"),
        "kds-pdv": ("/app/kds/pdv", "/painel/kds/pdv/"),
        "kds-analitico": ("/app/kds/analitico", "/painel/kds/analitico/"),
    }

    for app, (manifest_id, start_url) in expected.items():
        manifest = service.manifest(object(), app=app)
        assert manifest["id"] == manifest_id
        assert manifest["start_url"] == start_url
        assert manifest["scope"] == start_url
        assert manifest["orientation"] == "landscape"


def test_unknown_manifest_app_is_rejected_without_fallback():
    service = SiteConfigService(None)

    with pytest.raises(DomainError) as raised:
        service.manifest(object(), app="kds-desconhecido")

    assert raised.value.http_status == 400
    assert raised.value.code == "InvalidManifestApp"
