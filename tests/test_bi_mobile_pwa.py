from backend.services.site_config_service import SiteConfigService, SiteIdentity


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
