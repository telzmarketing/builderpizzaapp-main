from datetime import datetime, timezone
from importlib import import_module
from pkgutil import iter_modules
from types import SimpleNamespace

import pytest

from backend.core.events import PaymentConfirmed
from backend.core.exceptions import DomainError
from backend.models.order import OrderStatus
from backend.models.payment import PaymentMethod, PaymentStatus
from backend.services.payment_service import PaymentService
import backend.services.payment_service as payment_module
import backend.models


# Payment instantiation configures the SQLAlchemy registry. Load the model
# package first so relationships used by Order are available in this focused
# unit test.
for _module in iter_modules(backend.models.__path__):
    import_module(f"backend.models.{_module.name}")


class _Query:
    def __init__(self, row):
        self.row = row

    def filter(self, *args):
        return self

    def first(self):
        return self.row


class _Db:
    def __init__(self):
        self.added = []
        self.commits = 0
        self.order = None

    def add(self, value):
        self.added.append(value)

    def flush(self):
        for value in self.added:
            if getattr(value, "pay_on_delivery", None) is None:
                value.pay_on_delivery = False
            if getattr(value, "created_at", None) is None:
                value.created_at = datetime.now(timezone.utc)
            if getattr(value, "updated_at", None) is None:
                value.updated_at = datetime.now(timezone.utc)

    def commit(self):
        self.commits += 1

    def refresh(self, _value):
        pass

    def query(self, _model):
        return _Query(self.order)


def _payment(**overrides):
    values = {
        "id": "payment-cash-1",
        "tenant_id": "tenant-cash",
        "order_id": "order-cash-1",
        "method": PaymentMethod.cash,
        "status": PaymentStatus.pending,
        "amount": 42.5,
        "gateway": "mock",
        "provider": "cash",
        "provider_payment_id": None,
        "provider_customer_id": None,
        "provider_status": None,
        "mercado_pago_payment_id": None,
        "external_reference": "order-cash-1",
        "transaction_id": "CASH-ORIGINAL",
        "currency": "BRL",
        "installments": None,
        "card_brand": None,
        "card_brand_logo": None,
        "qr_code": None,
        "qr_code_text": None,
        "pix_payload": None,
        "pix_qr_code": None,
        "pix_expires_at": None,
        "payment_url": None,
        "provider_error_code": None,
        "provider_error_message": None,
        "pay_on_delivery": True,
        "delivery_payment_method": "cash",
        "cash_needs_change": False,
        "cash_change_for": None,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
        "paid_at": None,
        "cancelled_at": None,
        "refunded_at": None,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _order(payment=None):
    return SimpleNamespace(
        id="order-cash-1",
        tenant_id="tenant-cash",
        customer_id=None,
        external_reference="order-cash-1",
        total=42.5,
        status=OrderStatus.pending,
        payment=payment,
        session_id=None,
        campaign_id=None,
        landing_page=None,
        referrer=None,
        utm_source=None,
        utm_medium=None,
        utm_campaign=None,
        utm_content=None,
        utm_term=None,
        updated_at=None,
        paid_at=None,
        cancelled_by=None,
        cancellation_reason=None,
        cancelled_at=None,
    )


@pytest.fixture
def cash_service(monkeypatch):
    db = _Db()
    service = PaymentService(db, tenant_id="tenant-cash")
    service._cfg = lambda: SimpleNamespace(accept_cash=True)
    monkeypatch.setattr(
        "backend.services.automation_event_producer.AutomationEventProducer",
        lambda *_args: SimpleNamespace(
            order_status_changed=lambda *_args: None,
            payment_confirmed=lambda *_args: None,
        ),
    )
    monkeypatch.setattr(
        "backend.services.inventory_service.InventoryService",
        lambda *_args, **_kwargs: SimpleNamespace(
            consume_order_sale=lambda *_args: None,
            reverse_order_sale=lambda *_args: None,
        ),
    )
    monkeypatch.setattr(payment_module, "sync_customer_order_metrics", lambda *_args, **_kwargs: None)
    return service, db


def test_confirm_cash_approves_payment_and_publishes_finance_projection_event(
    cash_service, monkeypatch
):
    service, db = cash_service
    order = _order()
    db.order = order
    service._get_order = lambda _order_id: order
    published = []
    monkeypatch.setattr(
        payment_module.bus,
        "publish",
        lambda event: published.append((event, db.commits)),
    )

    result = service.confirm_cash(order.id)

    assert result.status is PaymentStatus.approved
    assert db.added and db.added[0].tenant_id == order.tenant_id
    assert db.commits == 1
    events = [event for event, commit_count in published if isinstance(event, PaymentConfirmed)]
    assert len(events) == 1
    assert next(commit_count for event, commit_count in published if isinstance(event, PaymentConfirmed)) == 1
    assert events[0].payment_id == result.id
    assert events[0].order_id == order.id
    assert events[0].tenant_id == order.tenant_id
    assert events[0].gateway == "cash"


def test_confirm_cash_is_idempotent_and_does_not_republish_projection(cash_service, monkeypatch):
    service, db = cash_service
    payment = _payment(status=PaymentStatus.approved, paid_at=datetime.now(timezone.utc))
    order = _order(payment)
    db.order = order
    service._get_order = lambda _order_id: order
    apply_status_calls = []
    service._apply_status = lambda *args, **kwargs: apply_status_calls.append((args, kwargs))
    published = []
    monkeypatch.setattr(payment_module.bus, "publish", published.append)

    result = service.confirm_cash(order.id)

    assert result.status is PaymentStatus.approved
    assert apply_status_calls == []
    assert published == []
    assert db.commits == 0


def test_paid_legacy_payment_reconfirms_finance_projection_without_transition(cash_service, monkeypatch):
    service, db = cash_service
    payment = _payment(status=PaymentStatus.paid, paid_at=datetime.now(timezone.utc))
    order = _order(payment)
    order.status = OrderStatus.paid
    db.order = order

    producer_calls = []
    monkeypatch.setattr(
        "backend.services.automation_event_producer.AutomationEventProducer",
        lambda *_args: SimpleNamespace(
            order_status_changed=lambda *_args: None,
            payment_confirmed=lambda *args: producer_calls.append(args),
        ),
    )
    transitions = []
    monkeypatch.setattr(
        payment_module.payment_sm,
        "transition",
        lambda *args: transitions.append(args),
    )
    published = []
    monkeypatch.setattr(payment_module.bus, "publish", published.append)

    result = service._apply_status(payment, PaymentStatus.approved, source="legacy_reconcile")

    assert result is True
    assert payment.status is PaymentStatus.paid
    assert transitions == []
    assert len(producer_calls) == 1
    assert producer_calls[0][0] is payment
    events = [event for event in published if isinstance(event, PaymentConfirmed)]
    assert len(events) == 1
    assert events[0].payment_id == payment.id
    assert events[0].tenant_id == payment.tenant_id
    assert db.commits == 1


@pytest.mark.parametrize("status", [PaymentStatus.rejected, PaymentStatus.failed, PaymentStatus.cancelled])
def test_confirm_cash_rejects_non_pending_payment_without_projecting(status, cash_service, monkeypatch):
    service, db = cash_service
    order = _order(_payment(status=status))
    db.order = order
    service._get_order = lambda _order_id: order
    published = []
    monkeypatch.setattr(payment_module.bus, "publish", published.append)

    with pytest.raises(DomainError) as exc:
        service.confirm_cash(order.id)

    assert exc.value.code == "PaymentNotPending"
    assert order.payment.status is status
    assert published == []
