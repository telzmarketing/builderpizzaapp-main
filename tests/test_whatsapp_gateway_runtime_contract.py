from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNTIME = (ROOT / "server" / "whatsapp-gateway-runtime.mjs").read_text(encoding="utf-8")


def test_runtime_reconnects_without_a_fixed_three_attempt_dead_end():
    assert "function scheduleReconnect(instanceId, state)" in RUNTIME
    assert "reconnectMaxDelayMs = 30000" in RUNTIME
    assert "scheduleReconnect(instanceId, state)" in RUNTIME
    assert "state.reconnectAttempts < 3" not in RUNTIME


def test_runtime_ignores_events_from_old_socket_after_restart_or_instance_swap():
    assert "function isCurrentSocket(state, generation, socket)" in RUNTIME
    assert "if (!isCurrentSocket(state, generation, socket)) return;" in RUNTIME
    assert "state.generation += 1" in RUNTIME


def test_runtime_disconnect_preserves_auth_and_delete_is_the_explicit_session_reset():
    assert "state.socket.logout" not in RUNTIME
    assert 'fs.rm(sessionDir, { recursive: true, force: true })' in RUNTIME
    assert 'const registryPath = path.join(dataDir, "instances.json")' in RUNTIME
    assert 'connectInstance(entry.instance_id, { reconnect: true })' in RUNTIME


def test_runtime_rejects_instance_ids_that_could_escape_the_session_directory():
    assert 'if (!/^[A-Za-z0-9][A-Za-z0-9._-]{0,119}$/.test(instanceId))' in RUNTIME
