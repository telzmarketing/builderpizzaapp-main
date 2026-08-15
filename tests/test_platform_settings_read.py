import json
from pathlib import Path

from backend.config import DEFAULT_JWT_SECRET_KEY, Settings
from backend.schemas.platform_settings import PlatformSettingsOut
from backend.services.platform_settings_service import PlatformSettingsService


ROOT = Path(__file__).parents[1]


def _settings(**overrides) -> Settings:
    base = {
        "JWT_SECRET_KEY": "configured-jwt-sentinel",
        "PLATFORM_RBAC_ENABLED": True,
        "TENANT_ENTITLEMENT_ENFORCEMENT_ENABLED": True,
    }
    base.update(overrides)
    return Settings(_env_file=None, **base)


def test_settings_snapshot_is_allowlisted_and_never_serializes_secrets():
    secret_values = {
        "DATABASE_URL": "postgresql://db-sentinel",
        "JWT_SECRET_KEY": "jwt-sentinel-private",
        "TENANT_DOMAINS_TRUSTED_PROXY_IPS": "192.0.2.123/32",
        "TENANT_PAYMENT_WEBHOOK_ENDPOINTS": "{\"token\":\"endpoint-sentinel-private\"}",
        "PAYMENT_SECRET_KEY": "payment-sentinel-private",
        "PAYMENT_WEBHOOK_SECRET": "webhook-sentinel-private",
        "MERCADO_PAGO_ACCESS_TOKEN": "mercado-sentinel-private",
        "ASAAS_API_KEY": "asaas-sentinel-private",
        "OPENAI_API_KEY": "openai-sentinel-private",
        "WHATSAPP_GATEWAY_RUNTIME_TOKEN": "runtime-sentinel-private",
        "WHATSAPP_GATEWAY_RUNTIME_URL": "http://runtime-url-sentinel.invalid",
    }
    payload = PlatformSettingsService(_settings(**secret_values)).get_settings()
    validated = PlatformSettingsOut.model_validate(payload)
    serialized = validated.model_dump_json()

    assert validated.source == "environment"
    assert validated.read_only is True
    assert validated.restart_required is True
    assert validated.security.jwt_secret_state == "configured"
    assert [flag.key for flag in validated.rollout_flags] == [
        "tenant_identity_catalog_enforcement",
        "tenant_customers_orders_enforcement",
        "multi_tenant_wave6_orm",
        "tenant_operations_enforcement",
        "tenant_payment_webhooks",
        "tenant_background_context",
        "tenant_upload_namespace",
        "tenant_credentials",
        "tenant_entitlement_enforcement",
    ]
    for secret in secret_values.values():
        assert secret not in serialized
    for protected_fragment in (
        "192.0.2.123",
        "endpoint-sentinel-private",
        "runtime-url-sentinel.invalid",
    ):
        assert protected_fragment not in serialized
    for forbidden_name in (
        "DATABASE_URL",
        "JWT_SECRET_KEY",
        "TENANT_DOMAINS_TRUSTED_PROXY_IPS",
        "TENANT_PAYMENT_WEBHOOK_ENDPOINTS",
        "PAYMENT_SECRET_KEY",
        "PAYMENT_WEBHOOK_SECRET",
        "MERCADO_PAGO_ACCESS_TOKEN",
        "ASAAS_API_KEY",
        "OPENAI_API_KEY",
        "WHATSAPP_GATEWAY_RUNTIME_TOKEN",
        "WHATSAPP_GATEWAY_RUNTIME_URL",
    ):
        assert forbidden_name not in serialized


def test_settings_normalizes_each_hostname_and_counts_invalid_inputs():
    settings = _settings(
        JWT_SECRET_KEY="",
        DEBUG=True,
        PLATFORM_RBAC_ENABLED=False,
        TENANT_DOMAINS_ENABLED=True,
        TENANT_DOMAINS_TRUST_PROXY_HEADERS=True,
        TENANT_DOMAINS_PLATFORM_HOSTNAMES=(
            " ERP.TELZ.COM.BR.,erp.telz.com.br,bad host,https://invalid"
        ),
        TENANT_DOMAINS_TRUSTED_PROXY_IPS=(
            "10.0.0.1,10.0.0.1/32,10.0.0.0/24,invalid-proxy"
        ),
        TENANT_ENTITLEMENT_ENFORCEMENT_ENABLED=False,
    )
    service = PlatformSettingsService(settings)

    first = service.get_settings()
    second = service.get_settings()
    domains = first["domains"]

    assert first == second
    assert domains == {
        "enabled": True,
        "trust_proxy_headers": True,
        "platform_hostnames": ["erp.telz.com.br"],
        "platform_hostname_count": 1,
        "invalid_platform_hostname_count": 2,
        "trusted_proxy_count": 2,
        "invalid_trusted_proxy_count": 1,
    }
    assert first["security"]["jwt_secret_state"] == "missing"
    assert first["status"] == "critical"
    assert [alert["key"] for alert in first["alerts"]] == [
        "jwt_secret_missing",
        "platform_rbac_disabled",
        "debug_enabled",
        "invalid_platform_hostnames",
        "invalid_trusted_proxies",
        "entitlement_enforcement_disabled",
    ]


def test_settings_detects_default_secret_with_hmac_and_derives_status():
    whitespace_payload = PlatformSettingsService(_settings(
        JWT_SECRET_KEY="   ",
    )).get_settings()
    assert whitespace_payload["security"]["jwt_secret_state"] == "missing"

    default_payload = PlatformSettingsService(_settings(
        JWT_SECRET_KEY=DEFAULT_JWT_SECRET_KEY,
    )).get_settings()
    assert default_payload["security"]["jwt_secret_state"] == "default"
    assert default_payload["status"] == "critical"

    attention_payload = PlatformSettingsService(_settings(
        TENANT_DOMAINS_PLATFORM_HOSTNAMES="invalid hostname",
    )).get_settings()
    assert attention_payload["status"] == "attention"
    assert [alert["key"] for alert in attention_payload["alerts"]] == [
        "invalid_platform_hostnames"
    ]

    ok_payload = PlatformSettingsService(_settings(
        TENANT_DOMAINS_PLATFORM_HOSTNAMES="ERP.TELZ.COM.BR.",
    )).get_settings()
    assert ok_payload["status"] == "ok"
    assert ok_payload["alerts"] == []

    service_source = (
        ROOT / "backend/services/platform_settings_service.py"
    ).read_text(encoding="utf-8")
    assert "hmac.compare_digest" in service_source
    assert "model_dump" not in service_source


def test_platform_settings_route_is_read_only_protected_and_registered():
    route = (ROOT / "backend/routes/platform_settings.py").read_text(
        encoding="utf-8"
    )
    main = (ROOT / "backend/main.py").read_text(encoding="utf-8")

    assert 'prefix="/admin/platform/settings"' in route
    assert '@router.get("", response_model=ApiEnvelope[PlatformSettingsOut])' in route
    assert 'require_platform_permission("platform_settings.view")' in route
    assert "@router.post" not in route
    assert "@router.put" not in route
    assert "@router.patch" not in route
    assert "@router.delete" not in route
    assert "from backend.routes import platform_settings as platform_settings_routes" in main
    assert 'app.include_router(platform_settings_routes.router, prefix="/api")' in main


def test_response_shape_contains_no_unplanned_top_level_fields():
    payload = PlatformSettingsService(_settings()).get_settings()
    assert set(payload) == {
        "source",
        "read_only",
        "restart_required",
        "status",
        "application",
        "security",
        "domains",
        "rollout_flags",
        "alerts",
    }
    # The raw JSON check catches accidental nested additions in future edits.
    serialized = json.dumps(payload, sort_keys=True)
    assert "password" not in serialized.lower()
    assert "token" not in serialized.lower()
