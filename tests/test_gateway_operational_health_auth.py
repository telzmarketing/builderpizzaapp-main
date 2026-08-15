from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_operational_gateway_probes_use_strict_authenticated_loopback_config():
    health = read("scripts/health-check.sh")
    collector = read("scripts/collect-telz-monitoring.sh")

    for script in (health, collector):
        assert "gateway_health_as_service()" in script
        assert 'sudo -u "$SERVICE_USER" -H /usr/bin/python3 -' in script
        assert "os.O_NOFOLLOW" in script
        assert 'allowed_keys = {"WHATSAPP_GATEWAY_RUNTIME_URL", "WHATSAPP_GATEWAY_RUNTIME_TOKEN"}' in script
        assert 'parsed.scheme != "http"' in script
        assert 'parsed.hostname not in {"127.0.0.1", "::1", "localhost"}' in script
        assert 'raise SystemExit("token do runtime WhatsApp ausente ou invalido")' in script
        assert '"WHATSAPP_GATEWAY_RUNTIME_TOKEN": runtime_token' in script
        assert "os.execvpe(" in script
        assert 'pnpm -C "$CODE_DIR" whatsapp-gateway:health' not in script


def test_gateway_token_is_never_forwarded_in_a_command_argument_or_logged():
    for relative in ("scripts/health-check.sh", "scripts/collect-telz-monitoring.sh"):
        script = read(relative)
        assert "--token" not in script
        assert "env WHATSAPP_GATEWAY_RUNTIME_TOKEN=" not in script
        assert 'WHATSAPP_GATEWAY_RUNTIME_TOKEN="$' not in script
        assert "print(runtime_token)" not in script
        exec_tail = script.split('"WHATSAPP_GATEWAY_RUNTIME_TOKEN": runtime_token', 1)[1]
        gateway_heredoc_body = exec_tail.split("\nPY\n", 1)[0]
        assert "sys.argv" not in gateway_heredoc_body


def test_health_and_collector_invoke_the_authenticated_wrapper():
    health = read("scripts/health-check.sh")
    collector = read("scripts/collect-telz-monitoring.sh")

    assert "gateway_health_as_service >/dev/null" in health
    assert "if gateway_health_as_service >/dev/null 2>&1; then" in collector
