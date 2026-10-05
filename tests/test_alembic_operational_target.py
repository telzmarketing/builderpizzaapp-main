import ast
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_TARGET_FILES = {
    "installer/config/defaults.env",
    "scripts/update-telz.sh",
    ".github/workflows/deploy.yml",
    "docs/INSTALL_TELZ_VPS.md",
    "docs/TELZ_VPS_INSTALL_PHASED_METHOD.md",
    "docs/UPDATE_TELZ_VPS.md",
}
REVISION_PATTERN = re.compile(r"202\d{5}_[a-z0-9_]+")


def _migration_heads() -> set[str]:
    revisions: dict[str, tuple[str, ...]] = {}
    versions = ROOT / "backend/migrations/versions"

    for path in versions.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        assignments: dict[str, object] = {}
        for node in tree.body:
            if isinstance(node, ast.Assign) and len(node.targets) == 1:
                target = node.targets[0]
                if isinstance(target, ast.Name) and target.id in {"revision", "down_revision"}:
                    assignments[target.id] = ast.literal_eval(node.value)
            elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                if node.target.id in {"revision", "down_revision"} and node.value is not None:
                    assignments[node.target.id] = ast.literal_eval(node.value)

        revision = assignments.get("revision")
        if not isinstance(revision, str):
            continue
        down_revision = assignments.get("down_revision")
        parents = (
            tuple(down_revision)
            if isinstance(down_revision, (tuple, list))
            else ((down_revision,) if isinstance(down_revision, str) else ())
        )
        assert revision not in revisions, f"revision Alembic duplicada: {revision}"
        revisions[revision] = parents

    referenced = {parent for parents in revisions.values() for parent in parents}
    assert referenced <= revisions.keys(), f"parents Alembic ausentes: {referenced - revisions.keys()}"
    return set(revisions) - referenced


def _operational_targets() -> dict[str, set[str]]:
    targets: dict[str, set[str]] = {}
    candidates = {
        path
        for directory in ("installer", "scripts", ".github/workflows", "docs")
        for path in (ROOT / directory).rglob("*")
        if path.is_file() and path.suffix in {".env", ".md", ".sh", ".yaml", ".yml"}
    }
    for path in candidates:
        source = path.read_text(encoding="utf-8")
        values = {
            value
            for line in source.splitlines()
            if "ALEMBIC_TARGET" in line
            for value in REVISION_PATTERN.findall(line)
        }
        if values:
            targets[path.relative_to(ROOT).as_posix()] = values
    return targets


def test_every_operational_alembic_target_matches_the_single_repository_head():
    heads = _migration_heads()
    targets = _operational_targets()

    assert len(heads) == 1, f"esperado um unico head Alembic, encontrados: {sorted(heads)}"
    assert set(targets) == EXPECTED_TARGET_FILES
    for relative_path, values in targets.items():
        assert values == heads, (
            f"target Alembic de {relative_path} diverge do head do repositorio: "
            f"target={sorted(values)} head={sorted(heads)}"
        )


def test_update_and_rollback_compatibility_are_explicit_and_fail_closed():
    reviewed_pairs = {
        "20260816_master_completion:20260818_platform_operations",
        "20260817_platform_wave0:20260818_platform_operations",
        "20260924_kds_kitchen_dispatch:20260926_dispatch_labels",
        "20260924_kds_kitchen_dispatch:20260927_order_board_mvp",
        "20260926_dispatch_labels:20260927_order_board_mvp",
        "20260930_tenant_runtime_uniqueness:20261003_marketing_workflow_tenant_isolation",
        "20261003_marketing_workflow_tenant_isolation:20261003_chatbot_tenant_keys",
        "20261003_chatbot_tenant_keys:20261003_marketing_tenant_keys",
        "20261003_marketing_tenant_keys:20261003_whatsapp_meta_webhook_tenant_keys",
        "20261003_whatsapp_meta_webhook_tenant_keys:20261003_email_marketing_tenant_config",
        "20261003_email_marketing_tenant_config:20261003_agente_whatsapp_tenant_foundation",
        "20261003_agente_whatsapp_tenant_foundation:20261004_wave7_finance_contract",
        "20261004_wave7_finance_contract:20261004_wave7_fiscal_contract",
        "20261004_wave7_fiscal_contract:20261004_wave7_management_geocode_contract",
        "20261004_wave7_management_geocode_contract:20261004_wave7_logistics_identity_contract",
        "20261004_wave7_logistics_identity_contract:20261004_tenant_upload_ownership_contract",
    }

    sources = {
        "update": (
            ROOT / "scripts/update-telz.sh",
            "schema_is_rollback_compatible() {",
            "\n}\n\nvalidate_release_tree()",
        ),
        "rollback": (
            ROOT / "scripts/rollback-telz.sh",
            "schema_pair_is_compatible() {",
            "\n}\n\n[[ -L \"$CURRENT_LINK\"",
        ),
    }

    for label, (path, start_marker, end_marker) in sources.items():
        source = path.read_text(encoding="utf-8")
        start = source.index(start_marker)
        function = source[start : source.index(end_marker, start)]
        assert set(re.findall(r'"(202\d{5}_[a-z0-9_]+:202\d{5}_[a-z0-9_]+)"', function)) == reviewed_pairs, label
        assert "&& return 0" in function
        assert "*)\n      return 1" in function
