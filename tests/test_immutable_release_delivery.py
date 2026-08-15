from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_runtime_units_separate_immutable_code_from_persistent_state():
    api = read("installer/templates/telz-api.service")
    web = read("installer/templates/telz-web.service")
    gateway = read("installer/templates/telz-whatsapp-gateway.service")
    installer = read("installer/lib/systemd.sh")

    for unit in (api, web, gateway):
        assert "WorkingDirectory=__INSTALL_DIR__" in unit
        assert "Environment=TELZ_PROJECT_ROOT=__INSTALL_DIR__" in unit
        assert "__CODE_DIR__" in unit
    assert "ExecStart=__CODE_DIR__/.venv/bin/uvicorn --app-dir __CODE_DIR__" in api
    assert "EnvironmentFile=__INSTALL_DIR__/backend/.env" in api
    assert "ExecStart=/usr/bin/node __CODE_DIR__/dist/server/node-build.mjs" in web
    assert "ExecStart=/usr/bin/node __CODE_DIR__/server/whatsapp-gateway-runtime.mjs" in gateway
    assert "WHATSAPP_GATEWAY_RUNTIME_DATA_DIR=__INSTALL_DIR__/.runtime/baileys" in gateway
    assert installer.count('s#__CODE_DIR__#${INSTALL_DIR}#g') == 3


def test_backend_and_gateway_resolve_persistent_project_root_from_environment():
    config = read("backend/config.py")
    gateway = read("server/whatsapp-gateway-runtime.mjs")

    assert 'os.environ.get("TELZ_PROJECT_ROOT", SOURCE_PROJECT_ROOT)' in config
    assert 'PERSISTENT_BACKEND_DIR = PROJECT_ROOT / "backend"' in config
    assert config.count('env_path = PERSISTENT_BACKEND_DIR / ".env"') == 2
    assert "process.env.TELZ_PROJECT_ROOT" in gateway
    assert 'path.resolve(process.env.TELZ_PROJECT_ROOT)' in gateway


def test_updater_builds_immutable_release_before_short_maintenance_window():
    updater = read("scripts/update-telz.sh")

    assert 'RELEASES_DIR="/var/lib/telz/releases"' in updater
    assert 'CURRENT_LINK="/var/lib/telz/current"' in updater
    assert 'STAGE_RELEASE_DIR="$(mktemp -d "$RELEASES_DIR/.staging-$EXPECTED_COMMIT.XXXXXX")"' in updater
    assert 'git -C "$1" archive --format=tar "$2" | tar -xf - -C "$3"' in updater
    assert 'as_service pnpm -C "$STAGE_APP_DIR" run build' in updater
    assert 'find "$STAGE_APP_DIR" -xdev -type d -exec chmod 0555 {} +' in updater
    assert 'find "$STAGE_APP_DIR" -xdev -type f ! -perm /111 -exec chmod 0444 {} +' in updater
    assert '"status": "validated"' in updater
    assert "snapshot_runtime" not in updater
    assert "runtime-rollback" not in updater

    build = updater.index('as_service pnpm -C "$STAGE_APP_DIR" run build')
    preflight = updater.index('echo "[update] preflight completo da release ativa antes de qualquer mutacao"')
    backup = updater.index('echo "[update] criando backup coerente antes da janela de manutencao"')
    armed = updater.index("RECOVERY_REQUIRED=true")
    stopped = updater.index("quiesce_services", armed)
    fast_forward = updater.index('as_service git -C "$INSTALL_DIR" merge --ff-only "$EXPECTED_COMMIT"')
    migration = updater.index('alembic_at "$FINAL_APP_DIR" upgrade "$ALEMBIC_TARGET"')
    swap = updater.index("activate_release", migration)
    assert build < preflight < backup < armed < stopped < fast_forward < migration < swap


def test_updater_validates_release_and_recovers_first_deploy_without_downgrade():
    updater = read("scripts/update-telz.sh")

    assert '[[ "$app_dir" == "$RELEASES_DIR/$expected_commit/app" ]]' in updater
    assert r'\( -type d -o -type f \) -perm /022' in updater
    assert "resolved.relative_to(root)" in updater
    assert '[[ -x "$STAGE_APP_DIR/.venv/bin/uvicorn" ]]' in updater
    assert '[[ -f "$STAGE_APP_DIR/dist/server/node-build.mjs" ]]' in updater
    assert '[[ -f "$STAGE_APP_DIR/dist/spa/index.html" ]]' in updater
    assert '[[ -f "$STAGE_APP_DIR/server/whatsapp-gateway-runtime.mjs" ]]' in updater
    assert "20260816_master_completion:20260818_platform_operations" in updater
    assert "20260817_platform_wave0:20260818_platform_operations" in updater
    assert "restore_previous_release" in updater
    assert "/etc/systemd/system/telz-api.service" in updater
    assert "/etc/systemd/system/telz-web.service" in updater
    assert "/etc/systemd/system/telz-whatsapp-gateway.service" in updater
    assert "nenhum downgrade automatico foi executado" in updater
    assert "rollback_code ||" not in updater
    assert "restore_previous_release ||" not in updater


def test_deploy_materializes_verified_root_owned_bundle_from_pinned_checkout():
    workflow = read(".github/workflows/deploy.yml")

    assert "actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683" in workflow
    assert "appleboy/ssh-action@029f5b4aeeeb58fdfe1410a5d17f967dacf36262" in workflow
    assert "OPERATION_BUNDLE_SHA256" in workflow
    assert "OPERATION_BUNDLE_BASE64" in workflow
    assert 'member.isreg()' in workflow
    assert 'if seen != expected:' in workflow
    assert 'sudo chown -R root:root "$BUNDLE_STAGE"' in workflow
    assert 'TELZ_OPERATION_BUNDLE_DIR="$BUNDLE_STAGE"' in workflow
    assert 'flock -n /var/lock/telz-maintenance.lock' in workflow
    assert '/usr/local/sbin/telz-finish-ssl' in workflow
    assert 'ACTIVE_APP="$(sudo readlink -f /var/lib/telz/current)"' in workflow
    assert 'git show "$TARGET_COMMIT:scripts/update-telz.sh"' not in workflow
    assert 'as_telz_git checkout' not in workflow
