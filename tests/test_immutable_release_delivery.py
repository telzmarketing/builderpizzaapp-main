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
        assert "TELZ_PROJECT_ROOT=__INSTALL_DIR__" in unit
        assert "__CODE_DIR__" in unit
    assert "__CODE_DIR__/.venv/bin/uvicorn --app-dir __CODE_DIR__" in api
    assert "EnvironmentFile=__INSTALL_DIR__/backend/.env" in api
    assert "/usr/bin/node __CODE_DIR__/dist/server/node-build.mjs" in web
    assert "/usr/bin/node __CODE_DIR__/server/whatsapp-gateway-runtime.mjs" in gateway
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
    builder = read("scripts/build-telz-release.sh")

    assert 'RELEASES_DIR="/var/lib/telz/releases"' in updater
    assert 'CURRENT_LINK="/var/lib/telz/current"' in updater
    assert 'install -m 0400 -o root -g root /dev/null "$release_dir/.building"' in updater
    assert 'rm -f -- "$release_dir/.building"' in updater
    assert 'os.execvpe("pnpm", ["pnpm", "-C", str(code_dir), "run", "build"], environment)' in builder
    assert 'find "$release_app" -xdev -type d -exec chmod 0555 {} +' in updater
    assert 'find "$release_app" -xdev -type f ! -perm /111 -exec chmod 0444 {} +' in updater
    assert '"status": "validated"' in updater
    assert "snapshot_runtime" not in updater
    assert "runtime-rollback" not in updater

    build = updater.index(
        'materialize_release "$EXPECTED_COMMIT" "$ALEMBIC_TARGET" "$SOURCE_ARCHIVE" false "$DATABASE_CURRENT"'
    )
    preflight = updater.index('echo "[update] preflight completo da release ativa antes de qualquer mutacao"')
    armed = updater.index("RECOVERY_REQUIRED=true")
    stopped = updater.index("quiesce_services", armed)
    backup = updater.index('echo "[update] criando backup coerente com os servicos quiescidos"')
    fast_forward = updater.index('as_service git -C "$INSTALL_DIR" merge --ff-only "$EXPECTED_COMMIT"')
    migration = updater.index('alembic_at "$FINAL_APP_DIR" upgrade "$ALEMBIC_TARGET"')
    swap = updater.index("activate_release", migration)
    assert build < preflight < armed < stopped < backup < fast_forward < migration < swap


def test_updater_validates_release_and_recovers_first_deploy_without_downgrade():
    updater = read("scripts/update-telz.sh")

    assert '[[ "$app_dir" == "$RELEASES_DIR/$expected_commit/app" ]]' in updater
    assert r'\( -type d -o -type f \) -perm /022' in updater
    assert "resolved.relative_to(root)" in updater
    assert '[[ -x "$app_dir/.venv/bin/uvicorn" && -x "$app_dir/.venv/bin/alembic" ]]' in updater
    assert '[[ -f "$app_dir/dist/server/node-build.mjs" ]]' in updater
    assert '[[ -f "$app_dir/dist/spa/index.html" ]]' in updater
    assert '[[ -f "$app_dir/server/whatsapp-gateway-runtime.mjs" ]]' in updater
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

    assert "actions/checkout@11d5960a326750d5838078e36cf38b85af677262" in workflow
    assert "appleboy/ssh-action@029f5b4aeeeb58fdfe1410a5d17f967dacf36262" in workflow
    assert "OPERATION_BUNDLE_SHA256" in workflow
    assert "OPERATION_BUNDLE_BASE64" in workflow
    assert 'member.isreg()' in workflow
    assert 'if seen != expected:' in workflow
    assert 'sudo chown -R root:root "$BUNDLE_STAGE"' in workflow
    assert 'TELZ_OPERATION_BUNDLE_DIR="$BUNDLE_STAGE"' in workflow
    assert 'lock_file="$lock_dir/maintenance.lock"' in workflow
    assert "flock -n 9" in workflow
    assert '/usr/local/sbin/telz-finish-ssl' in workflow
    assert 'ACTIVE_APP="$(sudo readlink -f /var/lib/telz/current)"' in workflow
    assert 'git show "$TARGET_COMMIT:scripts/update-telz.sh"' not in workflow
    assert 'as_telz_git checkout' not in workflow
