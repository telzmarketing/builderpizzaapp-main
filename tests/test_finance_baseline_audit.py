from pathlib import Path

import importlib.util


SCRIPT = Path("scripts/audit_finance_baseline.py")


def _load_audit_module():
    spec = importlib.util.spec_from_file_location("finance_baseline_audit", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_finance_baseline_audit_is_read_only_and_covers_false_passes():
    source = SCRIPT.read_text(encoding="utf-8")

    assert "SET TRANSACTION READ ONLY" in source
    assert "SET LOCAL search_path TO" in source
    assert "information_schema.tables" in source
    assert "WHERE table_schema = :schema" in source
    assert "SHOW transaction_read_only" in source
    assert "finance_settlements_missing_for_paid_transaction" in source
    assert "finance_settlements_orphan" in source
    assert "finance_settlement_mismatch" in source
    assert "IS DISTINCT FROM" in source
    assert "* 100" in source
    assert "finance_obligations_duplicate_origin" in source
    assert "finance_obligation_installments_orphan" in source
    assert "status IS NULL" in source
    assert "NaN" in source
    assert "Infinity" in source
    assert "tenant_id IS NULL" in source
    assert '"status": _overall_status(results)' in source
    assert "UPDATE" not in source
    assert "DELETE" not in source
    assert "INSERT" not in source


def test_finance_baseline_status_prioritizes_blocked_then_fail_then_pass():
    audit = _load_audit_module()

    assert audit._overall_status([]) == "BLOCKED"
    assert audit._overall_status([{"status": "PASS"}]) == "PASS"
    assert audit._overall_status([{"status": "FAIL"}, {"status": "PASS"}]) == "FAIL"
    assert audit._overall_status([{"status": "FAIL"}, {"status": "BLOCKED"}]) == "BLOCKED"


def test_finance_baseline_rejects_schema_identifier_injection():
    audit = _load_audit_module()

    assert audit._validated_schema("public") == "public"
    for invalid in ("public; DROP SCHEMA public", 'public"', "", "a schema"):
        try:
            audit._validated_schema(invalid)
        except ValueError:
            pass
        else:
            raise AssertionError(f"schema invalido aceito: {invalid!r}")
