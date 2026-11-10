from pathlib import Path
from unittest.mock import MagicMock
import importlib.util

import pytest


SCRIPT = Path("scripts/investigate_finance_findings.py")


def _load_module():
    spec = importlib.util.spec_from_file_location("finance_findings_investigation", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


INVESTIGATOR = _load_module()


@pytest.fixture
def simulated_investigation(monkeypatch):
    connection = MagicMock()
    engine = MagicMock()
    engine.connect.return_value.__enter__.return_value = connection
    monkeypatch.setattr(INVESTIGATOR, "create_engine", MagicMock(return_value=engine))
    tables = set(INVESTIGATOR.REQUIRED_TABLES)
    result_by_marker = {}

    def execute(statement, parameters=None):
        query = str(statement)
        result = MagicMock()
        if query == "SHOW transaction_read_only":
            result.scalar.return_value = "on"
        elif "information_schema.tables" in query:
            assert parameters == {"schema": "finance_audit"}
            return [(table,) for table in sorted(tables)]
        elif "FROM finance_audit.payments" in query:
            result.mappings.return_value.all.return_value = result_by_marker["payments"]
        elif "FROM finance_audit.inventory_purchases" in query:
            result.mappings.return_value.all.return_value = result_by_marker["purchases"]
        return result

    connection.execute.side_effect = execute
    result_by_marker["payments"] = []
    result_by_marker["purchases"] = []
    return engine, connection, tables, result_by_marker


def test_queries_are_select_only_and_include_requested_evidence():
    forbidden = INVESTIGATOR.re.compile(
        r"\b(INSERT|UPDATE|DELETE|MERGE|DROP|ALTER|CREATE|TRUNCATE|CALL|COPY)\b",
        INVESTIGATOR.re.IGNORECASE,
    )
    payment_query = INVESTIGATOR._payment_evidence.__code__.co_consts
    purchase_query = INVESTIGATOR._purchase_evidence.__code__.co_consts
    source = " ".join(str(value) for value in (*payment_query, *purchase_query))
    assert "SELECT" in source
    assert not forbidden.search(source)
    for token in (
        "gateway", "provider", "provider_status", "paid_at", "cancelled_at",
        "refunded_at", "inventory_purchase_items", "inventory_suppliers",
        "finance_transactions", "finance_obligations",
    ):
        assert token in source


def test_investigation_is_read_only_and_returns_empty_evidence(simulated_investigation):
    engine, connection, _, _ = simulated_investigation
    report = INVESTIGATOR.run("postgresql://unused/telz", "finance_audit")
    statements = [str(call.args[0]) for call in connection.execute.call_args_list]
    assert statements[:5] == [
        "SET TRANSACTION READ ONLY",
        "SET LOCAL statement_timeout = '30s'",
        "SET LOCAL lock_timeout = '2s'",
        'SET LOCAL search_path TO "finance_audit"',
        "SHOW transaction_read_only",
    ]
    assert report["audit"] == "finance-findings-investigation"
    assert report["status"] == "PASS"
    assert report["read_only"] is True
    assert report["inference"] is False
    assert report["counts"] == {"payments": 0, "purchases": 0}
    connection.commit.assert_not_called()
    connection.rollback.assert_called_once_with()
    engine.dispose.assert_called_once_with()


def test_investigation_returns_payment_and_purchase_evidence(simulated_investigation):
    _, _, _, results = simulated_investigation
    results["payments"] = [{"payment_id": "pay-1", "paid_at": "2026-11-10T20:00:00+00:00"}]
    results["purchases"] = [{"purchase_id": "pur-1", "items": [], "finance_obligations": []}]
    report = INVESTIGATOR.run("postgresql://unused/telz", "finance_audit")
    assert report["counts"] == {"payments": 1, "purchases": 1}
    assert report["payments"][0]["payment_id"] == "pay-1"
    assert report["purchases"][0]["purchase_id"] == "pur-1"


def test_missing_table_blocks_without_running_detail_queries(simulated_investigation):
    _, connection, tables, _ = simulated_investigation
    tables.remove("inventory_purchase_items")
    report = INVESTIGATOR.run("postgresql://unused/telz", "finance_audit")
    assert report["status"] == "BLOCKED"
    assert report["missing_tables"] == ["inventory_purchase_items"]
    assert not any("FROM finance_audit.payments" in str(call.args[0]) for call in connection.execute.call_args_list)


@pytest.mark.parametrize("schema", ["public; DROP SCHEMA public", 'public"', "", "a schema"])
def test_schema_is_validated_before_engine_creation(monkeypatch, schema):
    create_engine = MagicMock()
    monkeypatch.setattr(INVESTIGATOR, "create_engine", create_engine)
    with pytest.raises(ValueError, match="schema PostgreSQL valido"):
        INVESTIGATOR.run("postgresql://unused/telz", schema)
    create_engine.assert_not_called()
