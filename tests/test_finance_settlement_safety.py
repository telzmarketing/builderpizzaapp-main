from pathlib import Path


SERVICE = Path("backend/services/finance_service.py")


def _settlement_block() -> str:
    source = SERVICE.read_text(encoding="utf-8")
    start = source.index("    def settle_transaction(")
    end = source.index("    def _transaction_data(", start)
    return source[start:end]


def test_manual_settlement_locks_transaction_before_calculating_balance():
    block = _settlement_block()

    assert "row = self._get_transaction(transaction_id, for_update=True)" in block
    assert "with_for_update()" in SERVICE.read_text(encoding="utf-8")


def test_manual_settlement_rejects_terminal_state_and_non_finite_amounts():
    block = _settlement_block()

    assert 'if row.status == "cancelled"' in block
    assert 'if row.status == "paid"' in block
    assert "math.isfinite" in block
    assert "self._db.rollback()" in block


def test_settled_transactions_cannot_be_edited_or_cancelled():
    source = SERVICE.read_text(encoding="utf-8")

    assert "Lancamento com liquidacao nao pode ser alterado" in source
    assert "Lancamento com liquidacao nao pode ser cancelado" in source
