from pathlib import Path
from unittest.mock import MagicMock
import importlib.util

import pytest
from sqlalchemy.exc import SQLAlchemyError


SCRIPT = Path("scripts/audit_finance_reconciliation.py")


def _load_module():
    spec = importlib.util.spec_from_file_location("finance_reconciliation_audit", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


AUDIT = _load_module()


@pytest.fixture
def simulated_audit(monkeypatch):
    connection = MagicMock()
    engine = MagicMock()
    engine.connect.return_value.__enter__.return_value = connection
    monkeypatch.setattr(AUDIT, "create_engine", MagicMock(return_value=engine))
    tables = set(AUDIT.REQUIRED_TABLES)
    rows_by_query = {}

    def execute(statement, parameters=None):
        query = str(statement)
        result = MagicMock()
        if query == "SHOW transaction_read_only":
            result.scalar.return_value = "on"
        elif "information_schema.tables" in query:
            assert parameters == {"schema": "finance_audit"}
            return [(table,) for table in sorted(tables)]
        else:
            result.mappings.return_value.fetchmany.return_value = rows_by_query.get(query, [])
        return result

    connection.execute.side_effect = execute
    return engine, connection, tables, rows_by_query


def test_all_checks_are_select_only_and_cover_requested_cases():
    forbidden = AUDIT.re.compile(r"\b(INSERT|UPDATE|DELETE|MERGE|DROP|ALTER|CREATE|TRUNCATE|CALL|COPY)\b", AUDIT.re.IGNORECASE)
    names = {check["name"] for check in AUDIT.CHECKS}
    assert names == {
        "approved_payment_on_cancelled_order",
        "approved_payment_without_financial_projection",
        "multiple_financial_projections_per_payment",
        "confirmed_purchase_with_zero_value",
        "confirmed_purchase_without_supplier",
        "confirmed_purchase_without_financial_obligation",
        "operational_and_financial_value_divergence",
    }
    for check in AUDIT.CHECKS:
        query = check["query"]
        assert query.lstrip().startswith(("SELECT", "WITH"))
        assert not forbidden.search(query)
        assert ";" not in query
        assert "LIMIT 101" in query
        assert check["classification"] in {"pending_decision", "inconsistent", "blocked_auto_fix"}


def test_reconciliation_runs_read_only_with_timeouts_and_returns_clean_report(simulated_audit):
    engine, connection, _, _ = simulated_audit
    report = AUDIT.run("postgresql://unused/telz", "finance_audit")
    statements = [str(call.args[0]) for call in connection.execute.call_args_list]
    assert statements[:5] == [
        "SET TRANSACTION READ ONLY",
        "SET LOCAL statement_timeout = '30s'",
        "SET LOCAL lock_timeout = '2s'",
        'SET LOCAL search_path TO "finance_audit"',
        "SHOW transaction_read_only",
    ]
    assert report["audit"] == "finance-reconciliation"
    assert report["status"] == "PASS"
    assert report["read_only"] is True
    assert report["findings"] == []
    assert all(check["status"] == "PASS" for check in report["checks"])
    connection.rollback.assert_called_once_with()
    connection.commit.assert_not_called()
    engine.dispose.assert_called_once_with()


def test_reconciliation_reports_and_classifies_findings(simulated_audit):
    _, _, _, rows_by_query = simulated_audit
    check = AUDIT.CHECKS[0]
    rows_by_query[check["query"]] = [{"payment_id": "pay-1", "tenant_id": "tenant-1"}]
    report = AUDIT.run("postgresql://unused/telz", "finance_audit")
    assert report["status"] == "FAIL"
    assert report["findings"] == [{
        "name": "approved_payment_on_cancelled_order",
        "classification": "pending_decision",
        "status": "FAIL",
        "count": 1,
        "truncated": False,
        "sample": [{"payment_id": "pay-1", "tenant_id": "tenant-1"}],
    }]


def test_missing_required_table_blocks_without_running_reconciliation_queries(simulated_audit):
    _, connection, tables, _ = simulated_audit
    tables.remove("finance_obligations")
    report = AUDIT.run("postgresql://unused/telz", "finance_audit")
    assert report["status"] == "BLOCKED"
    assert report["checks"] == [{
        "status": "BLOCKED",
        "missing_tables": ["finance_obligations"],
    }]
    assert not any("FROM payments" in str(call.args[0]) for call in connection.execute.call_args_list)


@pytest.mark.parametrize("schema", ["public; DROP SCHEMA public", 'public"', "", "a schema"])
def test_schema_is_validated_before_engine_creation(monkeypatch, schema):
    create_engine = MagicMock()
    monkeypatch.setattr(AUDIT, "create_engine", create_engine)
    with pytest.raises(ValueError, match="schema PostgreSQL valido"):
        AUDIT.run("postgresql://unused/telz", schema)
    create_engine.assert_not_called()


def test_readonly_confirmation_failure_releases_engine(monkeypatch):
    connection = MagicMock()
    engine = MagicMock()
    engine.connect.return_value.__enter__.return_value = connection
    monkeypatch.setattr(AUDIT, "create_engine", MagicMock(return_value=engine))

    def execute(statement, parameters=None):
        result = MagicMock()
        if str(statement) == "SHOW transaction_read_only":
            result.scalar.return_value = "off"
        return result

    connection.execute.side_effect = execute
    with pytest.raises(RuntimeError, match="transaction_read_only=on"):
        AUDIT.run("postgresql://unused/telz")
    connection.commit.assert_not_called()
    engine.dispose.assert_called_once_with()


def test_query_failure_is_propagated_without_commit(simulated_audit):
    engine, connection, _, _ = simulated_audit
    original = connection.execute.side_effect
    failure = SQLAlchemyError("statement timeout")

    def fail(statement, parameters=None):
        if str(statement) == AUDIT.CHECKS[0]["query"]:
            raise failure
        return original(statement, parameters)

    connection.execute.side_effect = fail
    with pytest.raises(SQLAlchemyError, match="statement timeout"):
        AUDIT.run("postgresql://unused/telz", "finance_audit")
    connection.commit.assert_not_called()
    engine.dispose.assert_called_once_with()
