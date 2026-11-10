from pathlib import Path
from unittest.mock import MagicMock

import importlib.util

import pytest
from sqlalchemy.exc import SQLAlchemyError


SCRIPT = Path("scripts/audit_finance_baseline.py")


def _load_audit_module():
    spec = importlib.util.spec_from_file_location("finance_baseline_audit", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


AUDIT = _load_audit_module()
CHECK_IDS = [name for name, _, _ in AUDIT.CHECKS]


@pytest.mark.parametrize("name,query,required_tables", AUDIT.CHECKS, ids=CHECK_IDS)
def test_finance_baseline_final_sql_is_read_only_and_fully_interpolated(
    name, query, required_tables
):
    assert "{" not in query and "}" not in query, name
    assert "_NONFINITE_SQL" not in query
    assert query.lstrip().startswith(("SELECT ", "WITH "))
    assert not AUDIT.re.search(
        r"\b(INSERT|UPDATE|DELETE|MERGE|DROP|ALTER|CREATE|TRUNCATE|CALL|COPY)\b",
        query,
        flags=AUDIT.re.IGNORECASE,
    )
    assert ";" not in query
    assert "LIMIT 101" in query
    assert required_tables
    for table in required_tables:
        assert AUDIT.re.search(rf"\b{table}\b", query)


@pytest.mark.parametrize(
    "check_name,fields",
    [
        ("finance_transactions_invalid_amounts", (
            "amount", "paid_amount", "interest_amount", "fine_amount",
            "discount_amount", "fee_amount", "net_amount",
        )),
        ("finance_settlements_invalid_amounts", (
            "principal_amount", "interest_amount", "fine_amount",
            "discount_amount", "fee_amount", "net_amount",
        )),
        ("finance_obligations_invalid_amounts", (
            "total_amount", "product_amount", "freight_amount",
            "discount_amount", "tax_amount",
        )),
        ("finance_obligation_installments_invalid_amounts", (
            "amount", "paid_amount",
        )),
    ],
)
def test_finance_baseline_checks_nonfinite_values_for_every_monetary_field(
    check_name, fields
):
    query = next(query for name, query, _ in AUDIT.CHECKS if name == check_name)
    for field in fields:
        assert f"CAST({field} AS text) IN ('NaN', 'Infinity', '-Infinity')" in query
    assert query.count("AS text)") == len(fields)


@pytest.fixture
def simulated_audit(monkeypatch):
    """No engine or database is opened, even if DATABASE_URL is configured."""
    audit = _load_audit_module()
    connection = MagicMock()
    engine = MagicMock()
    engine.connect.return_value.__enter__.return_value = connection
    create_engine = MagicMock(return_value=engine)
    monkeypatch.setattr(audit, "create_engine", create_engine)
    tables = {table for _, _, required in audit.CHECKS for table in required}
    rows_by_query = {}

    def execute(statement, parameters=None):
        query = str(statement)
        result = MagicMock()
        if query == "SHOW transaction_read_only":
            result.scalar.return_value = "on"
        elif "information_schema.tables" in query:
            assert parameters == {"schema": "finance_audit"}
            return [(table,) for table in sorted(tables)]
        elif query in rows_by_query:
            result.mappings.return_value.fetchmany.return_value = rows_by_query[query]
        else:
            result.mappings.return_value.fetchmany.return_value = []
        return result

    connection.execute.side_effect = execute
    return audit, engine, connection, tables, rows_by_query


def test_finance_baseline_runs_all_checks_after_read_only_and_timeouts(simulated_audit):
    audit, engine, connection, _, _ = simulated_audit
    report = audit.run("postgresql://unused/audit", "finance_audit")

    statements = [str(call.args[0]) for call in connection.execute.call_args_list]
    assert statements[:5] == [
        "SET TRANSACTION READ ONLY",
        "SET LOCAL statement_timeout = '30s'",
        "SET LOCAL lock_timeout = '2s'",
        'SET LOCAL search_path TO "finance_audit"',
        "SHOW transaction_read_only",
    ]
    assert "information_schema.tables" in statements[5]
    assert statements[6:] == [query for _, query, _ in audit.CHECKS]
    assert len(CHECK_IDS) == len(set(CHECK_IDS)) == 23
    assert report["status"] == "PASS"
    assert report["read_only"] is True
    assert report["schema"] == "finance_audit"
    assert [check["name"] for check in report["checks"]] == CHECK_IDS
    assert all(check["count"] == 0 and check["sample"] == [] for check in report["checks"])
    connection.rollback.assert_called_once_with()
    connection.commit.assert_not_called()
    engine.dispose.assert_called_once_with()


@pytest.mark.parametrize("check_name", CHECK_IDS)
def test_finance_baseline_reports_each_existing_check_violation(simulated_audit, check_name):
    audit, _, connection, _, rows_by_query = simulated_audit
    query = next(query for name, query, _ in audit.CHECKS if name == check_name)
    rows_by_query[query] = [{"id": "example", "tenant_id": "tenant-example"}]

    report = audit.run("postgresql://unused/audit", "finance_audit")

    assert report["status"] == "FAIL"
    failed = [check for check in report["checks"] if check["status"] == "FAIL"]
    assert failed == [{
        "name": check_name, "status": "FAIL", "count": 1,
        "truncated": False, "sample": rows_by_query[query],
    }]
    connection.rollback.assert_called_once_with()


def test_finance_baseline_blocks_checks_with_missing_tables(simulated_audit):
    audit, _, connection, tables, _ = simulated_audit
    tables.remove("finance_settlements")

    report = audit.run("postgresql://unused/audit", "finance_audit")

    assert report["status"] == "BLOCKED"
    executed = [str(call.args[0]) for call in connection.execute.call_args_list]
    for check, (_, query, required) in zip(report["checks"], audit.CHECKS):
        if "finance_settlements" in required:
            assert check["status"] == "BLOCKED"
            assert check["missing_tables"] == ["finance_settlements"]
            assert query not in executed
        else:
            assert check["status"] == "PASS"


@pytest.mark.parametrize("row_count", [100, 101])
def test_finance_baseline_preserves_sample_and_truncation_limits(simulated_audit, row_count):
    audit, _, _, _, rows_by_query = simulated_audit
    _, query, _ = audit.CHECKS[0]
    rows_by_query[query] = [{"id": index} for index in range(row_count)]

    report = audit.run("postgresql://unused/audit", "finance_audit")

    check = report["checks"][0]
    assert check["count"] == 100
    assert check["truncated"] is (row_count > 100)
    assert check["sample"] == rows_by_query[query][:10]


def test_finance_baseline_stops_if_read_only_is_not_confirmed(simulated_audit):
    audit, engine, connection, _, _ = simulated_audit
    execute = connection.execute.side_effect

    def readonly_off(statement, parameters=None):
        result = execute(statement, parameters)
        if str(statement) == "SHOW transaction_read_only":
            result.scalar.return_value = "off"
        return result

    connection.execute.side_effect = readonly_off
    with pytest.raises(RuntimeError, match="transaction_read_only=on"):
        audit.run("postgresql://unused/audit", "finance_audit")

    assert connection.execute.call_count == 5
    engine.connect.return_value.__exit__.assert_called_once()
    connection.commit.assert_not_called()
    engine.dispose.assert_called_once_with()


def test_finance_baseline_releases_connection_on_query_failure(simulated_audit):
    audit, engine, connection, _, _ = simulated_audit
    execute = connection.execute.side_effect
    failure = SQLAlchemyError("simulated statement timeout")

    def failing_query(statement, parameters=None):
        if str(statement) == audit.CHECKS[0][1]:
            raise failure
        return execute(statement, parameters)

    connection.execute.side_effect = failing_query
    with pytest.raises(SQLAlchemyError, match="simulated statement timeout"):
        audit.run("postgresql://unused/audit", "finance_audit")

    # SQLAlchemy's connection context closes/rolls back on exceptions.
    # This safe test checks that the exceptional exit reaches that context.
    exit_args = engine.connect.return_value.__exit__.call_args.args
    assert exit_args[0] is SQLAlchemyError
    assert exit_args[1] is failure
    connection.commit.assert_not_called()
    engine.dispose.assert_called_once_with()


@pytest.mark.parametrize("schema", ["public; DROP SCHEMA public", 'public"', "", "a schema"])
def test_finance_baseline_validates_schema_before_creating_engine(simulated_audit, schema):
    audit, engine, _, _, _ = simulated_audit
    with pytest.raises(ValueError, match="schema PostgreSQL valido"):
        audit.run("postgresql://unused/audit", schema)
    audit.create_engine.assert_not_called()
    engine.connect.assert_not_called()


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
