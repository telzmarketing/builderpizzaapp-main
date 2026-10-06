from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_origin_deploy_requires_explicit_commit_and_uses_hardened_updater():
    source = (ROOT / "scripts/deploy-telz-from-origin.sh").read_text(encoding="utf-8")

    assert 'TARGET_COMMIT="${1:-}"' in source
    assert '[[ "$TARGET_COMMIT" =~ ^[0-9a-f]{40}$ ]]' in source
    assert 'git -C "$INSTALL_DIR" fetch --prune origin "$BRANCH"' in source
    assert 'merge-base --is-ancestor "$PREVIOUS_COMMIT" "$TARGET_COMMIT"' in source
    assert 'merge-base --is-ancestor "$TARGET_COMMIT" "$REMOTE_COMMIT"' in source
    assert 'TELZ_EXPECTED_COMMIT="$TARGET_COMMIT"' in source
    assert 'TELZ_PREVIOUS_COMMIT="$PREVIOUS_COMMIT"' in source
    assert 'TELZ_OPERATION_BUNDLE_DIR="$OPERATION_BUNDLE"' in source
    assert 'TELZ_DEPENDENCY_ARCHIVE_SHA256="$DEPENDENCY_SHA"' in source
    assert 'BUNDLE_UPDATE="$OPERATION_BUNDLE/scripts/update-telz.sh"' in source
    assert 'PUBLIC_HEALTH_URL="https://app.telz.com.br/health"' in source
    assert '"VITE_PLATFORM_HOSTNAME":"app.telz.com.br"' in source


def test_origin_deploy_keeps_artifacts_root_owned_and_never_runs_checkout_scripts_as_root():
    source = (ROOT / "scripts/deploy-telz-from-origin.sh").read_text(encoding="utf-8")

    assert 'require_root_owned_executable "$SOURCE_SCRIPT"' in source
    assert 'TELZ_ORIGIN_DEPLOY_REEXEC' in source
    assert 'archive --format=tar --add-virtual-file=".telz-source-commit:$TARGET_COMMIT"' in source
    assert 'install -d -m 0700 -o "$BUILD_USER" -g "$BUILD_GROUP"' in source
    assert 'chmod 0711 "$STAGE_DIR"' in source
    assert '"$DEPENDENCIES/target-report.json"' in source
    assert 'env -i' in source
    assert 'NPM_CONFIG_GLOBALCONFIG=/dev/null' in source
    assert "cd -- \"$1\"; shift; exec \"$@\"" in source
    assert 'run_as_builder python3.12 -m pip download --only-binary=:all:' in source
    assert 'BUILD_TARGET_SOURCE="$STAGE_DIR/build-target-source"' in source
    assert 'BUILD_PREVIOUS_SOURCE="$STAGE_DIR/build-previous-source"' in source
    assert 'cp -a -- "$STAGE_DIR/target-source/." "$BUILD_TARGET_SOURCE/"' in source
    assert 'chown -R "$BUILD_USER:$BUILD_GROUP" "$BUILD_TARGET_SOURCE" "$BUILD_PREVIOUS_SOURCE"' in source
    assert 'fonte de build contem symlink' in source
    assert 'fonte de build contem tipo especial' in source
    assert 'run_as_builder_in "$BUILD_TARGET_SOURCE" pnpm fetch --frozen-lockfile --ignore-scripts' in source
    assert 'run_as_builder_in "$BUILD_PREVIOUS_SOURCE" pnpm fetch --frozen-lockfile --ignore-scripts' in source
    assert 'alembic upgrade' not in source
    assert 'systemctl restart' not in source
    assert 'git -C "$INSTALL_DIR" merge ' not in source
