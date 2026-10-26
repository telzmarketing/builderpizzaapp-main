"""Read-only projection of persisted payment facts for operational surfaces."""
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP


def cash_change_amount(payment, total) -> float | None:
    if not payment or not payment.cash_needs_change:
        return None
    method = getattr(payment.method, "value", payment.method)
    if method != "cash" and payment.delivery_payment_method != "cash":
        return None
    if payment.cash_change_for is None:
        return None
    try:
        received, due = Decimal(str(payment.cash_change_for)), Decimal(str(total))
        if not received.is_finite() or not due.is_finite() or due < 0 or received < due:
            return None
        return float((received - due).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
    except (InvalidOperation, ValueError, TypeError):
        return None
