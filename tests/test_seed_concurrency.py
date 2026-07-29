from types import SimpleNamespace
from unittest.mock import Mock, call, patch

from backend.core import seed


def test_postgresql_seed_acquires_transaction_lock_before_writes():
    db = Mock()
    db.get_bind.return_value = SimpleNamespace(
        dialect=SimpleNamespace(name="postgresql")
    )

    seed_steps = (
        "_seed_multi_flavor_config",
        "_seed_products",
        "_seed_promotions",
        "_seed_loyalty",
        "_seed_coupons",
        "_seed_shipping",
        "_seed_admin",
        "_seed_chatbot_settings",
        "_seed_rbac",
    )
    with patch.multiple(seed, **{name: Mock() for name in seed_steps}):
        seed.seed_all(db)

    assert db.method_calls[0] == call.get_bind()
    assert db.method_calls[1][0] == "execute"
    statement, params = db.method_calls[1].args
    assert "pg_advisory_xact_lock" in str(statement)
    assert params == {"lock_key": "telz:seed_all:v1"}
    assert db.method_calls[-1] == call.commit()


def test_non_postgresql_seed_does_not_request_advisory_lock():
    db = Mock()
    db.get_bind.return_value = SimpleNamespace(
        dialect=SimpleNamespace(name="sqlite")
    )

    seed._acquire_seed_lock(db)

    db.execute.assert_not_called()
