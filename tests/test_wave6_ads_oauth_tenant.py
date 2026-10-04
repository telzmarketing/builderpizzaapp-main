"""Security-contract tests for the Wave 6 Ads OAuth tenant boundary.

Ads credentials are especially sensitive: a query scoped only by provider would
allow a company to synchronize campaigns or fire CAPI events with another
company's token.  These source-level tests keep that boundary explicit while
the module remains independently testable without external OAuth providers.
"""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _source() -> str:
    return (ROOT / "backend/routes/ads_oauth.py").read_text(encoding="utf-8")


def _section(source: str, marker: str, next_marker: str = "\ndef ") -> str:
    start = source.index(marker)
    end = source.find(next_marker, start + len(marker))
    return source[start:end if end != -1 else None]


def test_ads_routes_bind_the_trusted_panel_tenant_and_remove_the_wave6_guard():
    source = _source()

    assert "panel_wave6_context" in source
    assert "WAVE6_SESSION_TENANT_KEY" in source
    assert "wave6_tenant_id" in source
    assert "Depends(panel_wave6_context)" in source
    assert "block_unsafe_wave6_route" not in source


def test_ads_models_and_oauth_state_are_owned_by_the_request_tenant():
    source = _source()

    for model in ("AdsOAuthState", "AdsCampaign", "AdsUtmLink", "AdsPixel"):
        definition = _section(source, f"class {model}(", "\n\nclass ")
        assert "tenant_id = wave6_tenant_column" in definition, model

    connect = _section(source, "def get_connect_url(")
    assert "tenant_id=tenant_id" in connect

    callback = _section(source, "def oauth_callback(")
    assert "AdsOAuthState.tenant_id == tenant_id" in callback


def test_provider_credentials_are_selected_and_upserted_per_tenant():
    source = _source()

    get_creds = _section(source, "def _get_creds(")
    save_creds = _section(source, "def _save_creds(")

    assert "tenant_id: str" in get_creds
    assert "tenant_id = :tenant_id" in get_creds
    assert '"tenant_id": tenant_id' in get_creds

    assert "tenant_id: str" in save_creds
    assert "tenant_id = :tenant_id" in save_creds
    assert "tenant_id" in save_creds.split("INSERT INTO integration_connections", 1)[1]
    # ``scope`` is acceptable when it is derived only from the explicit helper
    # argument or the trusted session context.
    assert '"tenant_id": scope' in save_creds or '"tenant_id": tenant_id' in save_creds


def test_campaign_sync_and_capi_never_use_an_unscoped_campaign_or_pixel():
    source = _source()

    upsert = _section(source, "def _upsert_campaign(")
    assert "tenant_id: str" in upsert
    assert "AdsCampaign.tenant_id == tenant_id" in upsert
    assert "tenant_id=tenant_id" in upsert

    capi = _section(source, "def _fire_meta_capi_event(")
    assert "tenant_id: str" in capi
    assert "AdsPixel.tenant_id ==" in capi

    for helper in ("_sync_meta_campaigns", "_sync_google_campaigns", "_sync_tiktok_campaigns"):
        sync = _section(source, f"def {helper}(")
        assert "tenant_id: str" in sync, helper
        assert "tenant_id" in sync, helper


def test_utm_pixels_leads_and_roi_queries_are_tenant_scoped():
    source = _source()

    for route in ("list_utms", "create_utm", "delete_utm", "list_pixels", "create_pixel", "update_pixel", "delete_pixel"):
        handler = _section(source, f"def {route}(")
        assert "tenant_id" in handler, route

    assert "AdsUtmLink.tenant_id == _tenant_id(db)" in source
    assert "AdsPixel.tenant_id == _tenant_id(db)" in source
    assert "tenant_id=tenant_id" in source

    leads = _section(source, "def list_leads(")
    assert "c.tenant_id = :tenant_id" in leads

    roi = _section(source, "def get_roi(")
    assert "tenant_id = :tenant_id" in roi
