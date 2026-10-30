"""Focused contracts for dashboard and BI revenue boundaries."""

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session


def test_dashboard_revenue_excludes_cancelled_and_requires_payment_for_effective_total():
    from backend.main import app  # noqa: F401
    from backend.routes.admin import _revenue_query

    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        connection.execute(text(
            "CREATE TABLE orders (id TEXT PRIMARY KEY, status TEXT, total FLOAT, tenant_id TEXT)"
        ))
        connection.execute(text(
            "CREATE TABLE payments (id TEXT PRIMARY KEY, order_id TEXT, status TEXT, tenant_id TEXT)"
        ))
        connection.execute(text(
            "INSERT INTO orders VALUES "
            "('paid','delivered',100,'tenant-a'),"
            "('pending','pending',50,'tenant-a'),"
            "('cancelled','cancelled',80,'tenant-a'),"
            "('refunded','refunded',70,'tenant-a'),"
            "('failed-payment','delivered',30,'tenant-a')"
        ))
        connection.execute(text(
            "INSERT INTO payments VALUES "
            "('p-paid','paid','paid','tenant-a'),"
            "('p-cancelled','cancelled','paid','tenant-a'),"
            "('p-refunded','refunded','paid','tenant-a'),"
            "('p-failed','failed-payment','failed','tenant-a')"
        ))

        with Session(bind=connection) as db:
            assert _revenue_query(db).scalar() == 180
            assert _revenue_query(db, require_eligible_payment=True).scalar() == 100

    engine.dispose()


def test_business_intelligence_estimated_revenue_has_non_cancelled_boundary():
    from pathlib import Path

    source = (Path(__file__).parents[1] / "backend/services/business_intelligence_service.py").read_text(encoding="utf-8")
    marker = "estimated_revenue = self._round("
    section = source[source.index(marker):source.index("effective_revenue", source.index(marker))]
    assert "~Order.status.in_(self.CANCELLED_STATUSES)" in section
