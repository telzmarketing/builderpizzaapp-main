from pathlib import Path


ROOT = Path(__file__).parents[1]


def _read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_installer_enables_tenant_runtime_and_reserves_platform_hostname():
    defaults = _read("installer/config/defaults.env")
    backend = _read("installer/lib/backend.sh")
    example = _read("installer/templates/env.production.example")

    assert "MULTI_TENANT_AUTH_ENABLED=true" in defaults
    assert "TENANT_DOMAINS_ENABLED=true" in defaults
    assert "TENANT_DOMAINS_TRUST_PROXY_HEADERS=false" in defaults
    assert "TENANT_DOMAINS_PLATFORM_HOSTNAMES=" in defaults
    assert "PLATFORM_RBAC_ENABLED=true" in defaults
    assert (
        "TENANT_DOMAINS_PLATFORM_HOSTNAMES="
        "${TENANT_DOMAINS_PLATFORM_HOSTNAMES:-${PLATFORM_DOMAIN}}"
    ) in backend
    assert "PLATFORM_RBAC_ENABLED=${PLATFORM_RBAC_ENABLED:-true}" in backend
    assert "TENANT_DOMAINS_PLATFORM_HOSTNAMES=app.example.com" in example


def test_frontend_build_receives_platform_hostname_and_auth_flag():
    frontend = _read("installer/lib/frontend.sh")

    assert 'VITE_PLATFORM_HOSTNAME="${PLATFORM_DOMAIN}"' in frontend
    assert (
        'VITE_MULTI_TENANT_AUTH_ENABLED="${MULTI_TENANT_AUTH_ENABLED:-true}"'
        in frontend
    )
    assert 'bash -lc "cd \'$INSTALL_DIR\' && pnpm run build"' in frontend


def test_nginx_accepts_store_hosts_and_preserves_original_host():
    nginx = _read("installer/templates/nginx-telz.conf")

    assert "server_name __PLATFORM_DOMAIN__ ~^.+$;" in nginx
    assert nginx.count("proxy_set_header Host $host;") == 3
    assert "fail-closed" in nginx
    assert "SSL automatico cobre somente __PLATFORM_DOMAIN__" in nginx
