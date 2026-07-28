import re
from pathlib import Path


ROOT = Path(__file__).parents[1]
VERSIONS = ROOT / "backend/migrations/versions"
INITIAL_SCHEMA = VERSIONS / "20260422_initial_schema.py"


def test_initial_schema_expands_alembic_revision_capacity_before_baseline_ddl():
    migration = INITIAL_SCHEMA.read_text(encoding="utf-8")

    expand_at = migration.index(
        "ALTER COLUMN version_num TYPE VARCHAR(255)"
    )
    baseline_at = migration.index("for statement in _statements():")

    assert expand_at < baseline_at


def test_alembic_revision_capacity_covers_longest_repository_revision():
    revision_pattern = re.compile(
        r'^revision\s*(?::[^=]+)?=\s*["\']([^"\']+)["\']',
        re.MULTILINE,
    )
    revisions = []
    for migration_path in VERSIONS.glob("*.py"):
        match = revision_pattern.search(
            migration_path.read_text(encoding="utf-8")
        )
        if match:
            revisions.append(match.group(1))

    assert revisions
    assert max(map(len, revisions)) <= 255
