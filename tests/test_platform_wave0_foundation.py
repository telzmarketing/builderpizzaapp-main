import ast
from pathlib import Path


ROOT = Path(__file__).parents[1]
MIGRATION = ROOT / "backend/migrations/versions/20260817_platform_wave0_foundation.py"
BACKUP_SCRIPT = ROOT / "scripts/backup-telz.sh"


EXPECTED_PERMISSION_KEYS = {
    "platform_users.view",
    "platform_users.manage",
    "platform_settings.view",
    "platform_settings.manage",
    "monitoring.view",
    "integrations.view",
    "integrations.manage",
    "jobs.view",
    "jobs.manage",
    "gateway.view",
    "gateway.manage",
    "errors.view",
    "errors.manage",
    "storage.view",
    "backups.view",
}


def _assignment(tree: ast.Module, name: str):
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            target = node.targets[0]
            if isinstance(target, ast.Name) and target.id == name:
                return node.value
    raise AssertionError(f"assignment {name} is missing")


def test_wave0_migration_is_linear_idempotent_and_seeds_the_future_catalog():
    source = MIGRATION.read_text(encoding="utf-8")
    tree = ast.parse(source)

    revision = ast.literal_eval(_assignment(tree, "revision"))
    assert revision == "20260817_platform_wave0"
    assert len(revision) <= 32
    assert ast.literal_eval(_assignment(tree, "down_revision")) == "20260816_master_completion"

    permissions = ast.literal_eval(_assignment(tree, "PERMISSIONS"))
    assert {key for key, _name, _description in permissions} == EXPECTED_PERMISSION_KEYS
    assert ".on_conflict_do_nothing(index_elements=[\"key\"])" in source
    assert "ON CONFLICT (role_id, permission_id) DO NOTHING" in source
    assert "Platform system roles are incomplete" in source


def test_wave0_role_grants_follow_least_privilege_boundaries():
    source = MIGRATION.read_text(encoding="utf-8")
    assert '"platform_owner": tuple(key for key, _name, _description in PERMISSIONS)' in source

    tree = ast.parse(source)
    grants_node = _assignment(tree, "ROLE_GRANTS")
    assert isinstance(grants_node, ast.Dict)
    explicit = {
        ast.literal_eval(key): ast.literal_eval(value)
        for key, value in zip(grants_node.keys, grants_node.values)
        if ast.literal_eval(key) != "platform_owner"
    }

    admin = set(explicit["platform_admin"])
    support = set(explicit["platform_support"])
    assert "platform_settings.view" in admin
    assert "platform_settings.view" not in support
    assert {"platform_users.manage", "platform_settings.manage"}.isdisjoint(admin)
    assert support == {
        "monitoring.view",
        "integrations.view",
        "jobs.view",
        "gateway.view",
        "errors.view",
    }
    assert not any(permission.endswith(".manage") for permission in support)
    assert {"storage.view", "backups.view"}.isdisjoint(support)
    assert "NOT EXISTS" in source


def test_backup_validates_database_env_uploads_and_baileys_without_listing_secrets():
    script = BACKUP_SCRIPT.read_text(encoding="utf-8")

    assert "umask 077" in script
    assert 'pg_restore --list "$TEMP_DIR/database.dump" >/dev/null' in script
    assert 'cmp -s "$INSTALL_DIR/backend/.env" "$TEMP_DIR/environment.env"' in script
    assert 'tar -C "$INSTALL_DIR" -czf "$TEMP_DIR/baileys.tar.gz" .runtime/baileys' in script
    assert 'validate_archive "$TEMP_DIR/baileys.tar.gz" ".runtime/baileys"' in script
    assert "member.isdir() or member.isreg()" in script
    assert 'validate_archive "$TEMP_DIR/uploads.tar.gz" "uploads"' in script
    assert "sha256sum --check --status SHA256SUMS" in script
    assert 'chmod 0600 "$TEMP_DIR"/*' in script
    assert 'chown -R root:root "$TEMP_DIR"' in script
    assert 'echo "$DATABASE_URL"' not in script
    assert "tar -tv" not in script
