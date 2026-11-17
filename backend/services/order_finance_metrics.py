"""Canonical order-level revenue expressions for BI and finance projections.

Delivery-app snapshots are additive.  A missing snapshot is deliberately
treated as a legacy/own order and falls back to the commercial order total.
These expressions must be used together so a snapshot is never counted once
as ``Order.total`` and again as an app deduction.
"""
from __future__ import annotations

from sqlalchemy import func

from backend.models.order import Order


def order_gross_expr():
    """Gross app base when available, otherwise the legacy order total."""
    return func.coalesce(Order.app_finance_gross_amount, Order.total)


def order_deductions_expr():
    """App deductions when available, otherwise zero for legacy orders."""
    return func.coalesce(Order.app_finance_deductions, 0)


def order_net_expr():
    """Net app revenue when available, otherwise the legacy order total."""
    return func.coalesce(Order.app_finance_net_amount, Order.total)


def order_has_app_snapshot_expr():
    """Whether an order carries the persisted app-finance projection."""
    return Order.app_finance_net_amount.isnot(None)
