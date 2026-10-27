"""Financial and calendar contracts exercised over real SQL aggregates."""
from datetime import date, datetime, timezone
import os
from uuid import uuid4
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from backend.core.local_time import STORE_TIMEZONE, local_period_bounds
from backend.schemas.bi import BIMobileQuery
from backend.services.bi_mobile_service import BIMobileService, InvalidBIQuery, previous_month, variation


@pytest.fixture
def service():
    # Register the project's ORM graph, without running ASGI startup.
    from backend.main import app  # noqa: F401
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE orders (id TEXT PRIMARY KEY, tenant_id TEXT, created_at TIMESTAMP, status TEXT, total FLOAT, subtotal FLOAT, shipping_fee FLOAT, discount FLOAT, sales_channel TEXT)"))
        connection.execute(text("CREATE TABLE payments (id TEXT, tenant_id TEXT, order_id TEXT, status TEXT, method TEXT)"))
        connection.execute(text("CREATE TABLE products (id TEXT, tenant_id TEXT, product_type TEXT, category TEXT)"))
        connection.execute(text("CREATE TABLE order_items (id TEXT, tenant_id TEXT, order_id TEXT, product_id TEXT, quantity INTEGER)"))
        with Session(bind=connection) as db:
            yield BIMobileService(db, "a")
    engine.dispose()


def test_calendar_clamping_leap_year_and_year_boundary():
    assert previous_month(date(2024, 3, 31)) == date(2024, 2, 29)
    assert previous_month(date(2025, 3, 31)) == date(2025, 2, 28)
    assert previous_month(date(2026, 1, 5)) == date(2025, 12, 5)
    assert variation(25, 0) == {"difference": 25, "percent": None}
    assert variation(150, 100) == {"difference": 50, "percent": 50}


def test_bounds_partial_equal_cutoff_and_rolling_duration(service):
    now = datetime(2026, 10, 27, 20, 30, tzinfo=STORE_TIMEZONE)
    b = service.bounds(BIMobileQuery(date=date(2026, 10, 27)), now)
    assert b["end_dt"] == now.astimezone(timezone.utc)
    assert b["previous_end_dt"].astimezone(STORE_TIMEZONE).isoformat() == "2026-09-27T20:30:00-03:00"
    b = service.bounds(BIMobileQuery(date=date(2026, 3, 31), period="30d"), now)
    assert (b["end"] - b["start"]).days == (b["previous_end"] - b["previous_start"]).days == 29
    assert b["previous_end"] == date(2026, 2, 28)
    assert b["partial"] is False
    with pytest.raises(InvalidBIQuery):
        service.bounds(BIMobileQuery(date=date(2026, 10, 28)), now)


def test_paid_orders_pizzas_cancelled_duplicate_payments_and_tenant_isolation(service):
    db = service.db
    for order_id, tenant, status, total, at in [
        ("paid", "a", "delivered", 100, "2026-10-27 03:30:00"),
        ("pending", "a", "pending", 50, "2026-10-27 04:00:00"),
        ("cancelled", "a", "cancelled", 80, "2026-10-27 05:00:00"),
        ("refunded", "a", "refunded", 70, "2026-10-27 06:00:00"),
        ("other", "b", "delivered", 1000, "2026-10-27 04:00:00"),
        ("previous-day", "a", "delivered", 40, "2026-10-27 02:59:00"),
        ("wrong-payment-tenant", "a", "paid", 700, "2026-10-27 04:00:00"),
    ]:
        db.execute(text("INSERT INTO orders VALUES (:id,:tenant,:at,:status,:total,:total,0,0,'delivery')"),
            dict(id=order_id, tenant=tenant, at=at, status=status, total=total))
    for payment_id, order_id, tenant in [("p1", "paid", "a"), ("p2", "paid", "a"),
        ("pc", "cancelled", "a"), ("pr", "refunded", "a"), ("po", "other", "b"),
        ("pp", "previous-day", "a"), ("wrong", "wrong-payment-tenant", "b")]:
        db.execute(text("INSERT INTO payments VALUES (:id,:tenant,:order,'paid','pix')"), dict(id=payment_id, tenant=tenant, order=order_id))
    db.execute(text("INSERT INTO products VALUES ('pizza','a','pizza','Pizzas'),('drink','a','drink','Bebidas'),('foreign','b','pizza','Pizzas')"))
    # A split-flavor pizza is one item; quantities represent physical units.
    db.execute(text("INSERT INTO order_items VALUES ('i1','a','paid','pizza',2),('i2','a','paid','drink',3),('i3','b','paid','pizza',90),('i4','a','paid','foreign',90)"))
    start, end = local_period_bounds(date(2026, 10, 27), date(2026, 10, 27))
    rows = service._rows(start, end)
    assert rows == [{"date": "2026-10-27", "created": 5, "orders": 1, "revenue": 100, "pizzas": 2}]
    totals = service._totals(start, end, rows, 1)
    assert totals["orders"] == 5
    assert totals["valid_orders"] == 1
    assert totals["revenue"] == totals["average_ticket"] == 100
    assert totals["cancelled_orders"] == 2
    assert totals["cancelled_value"] == 150
    assert totals["pizzas"] == 2
    assert service._rows(start, end, True)[0]["date"] == "2026-10-27 00"


def test_empty_period_is_real_zero_without_invented_history(service):
    start, end = local_period_bounds(date(2026, 10, 1), date(2026, 10, 7))
    assert service._rows(start, end) == []
    totals = service._totals(start, end, [], 7)
    assert totals["revenue"] == totals["valid_orders"] == totals["pizzas"] == 0
    assert totals["best_day"] is None


@pytest.mark.parametrize("answer,engine", [
    ('{"recommendation_ids":["peak","quiet"]}', "ai_assisted"),
    ('{"recommendation_ids":["invented"]}', "calculated"),
    ('{"recommendation_ids":["peak","peak"]}', "calculated"),
    ('{"recommendation_ids":[7,"quiet"]}', "calculated"),
    ('Receita inventada de R$ 999999', "calculated"),
])
def test_ai_only_prioritizes_known_actions_and_never_supplies_displayed_facts(monkeypatch, answer, engine):
    from backend.services.ai import factory
    from unittest.mock import MagicMock
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = SimpleNamespace(ativo=True, ia_ativo=True)
    provider = MagicMock()
    provider.is_configured.return_value = True
    provider.generate.return_value = SimpleNamespace(content=answer, error_reason="")
    monkeypatch.setattr(factory, "get_ai_provider", lambda settings: provider)
    service = BIMobileService(db, "trusted-tenant")
    data = {"period": {"date_from": "2026-10-20"}, "totals": {"revenue": 100}, "comparison": {}}
    result, actual_engine, note = service._prioritize_recommendations(data, {"quiet": "Ação validada A", "peak": "Ação validada B"})
    assert actual_engine == engine
    assert set(result) == {"Ação validada A", "Ação validada B"}
    assert "999999" not in " ".join(result)
    sent = provider.generate.call_args.kwargs["messages"][0].content
    assert "customer" not in sent and "phone" not in sent
    assert "100" in sent


def test_legacy_pizza_category_does_not_count_borders_or_addons(service):
    db = service.db
    db.execute(text("INSERT INTO orders VALUES ('legacy','a','2026-10-20 15:00:00','paid',100,100,0,0,'delivery')"))
    db.execute(text("INSERT INTO payments VALUES ('legacy','a','legacy','paid','pix')"))
    db.execute(text("INSERT INTO products VALUES ('lp','a',NULL,'Pizzas'),('lb','a',NULL,'Bordas de pizza'),('la','a','other','Adicionais pizza')"))
    db.execute(text("INSERT INTO order_items VALUES ('lp','a','legacy','lp',2),('lb','a','legacy','lb',5),('la','a','legacy','la',6)"))
    rows = service._rows(*local_period_bounds(date(2026, 10, 20), date(2026, 10, 20)))
    assert rows[0]["pizzas"] == 2


def test_full_mobile_projection_on_migrated_postgresql():
    url = os.environ.get("DRIVER_SCHEMA_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Requires a disposable, Alembic-migrated PostgreSQL database")
    from backend.main import app  # noqa: F401
    from backend.core.tenant_context import TenantContext, TenantSource
    from backend.core.wave6_tenant_context import bind_wave6_tenant_context
    engine = create_engine(url)
    suffix = uuid4().hex
    tenant = "bi-mobile-" + suffix
    with engine.connect() as connection:
        transaction = connection.begin()
        try:
            connection.execute(text("INSERT INTO tenants(id,slug,name) VALUES (:tenant,:tenant,'BI test')"), {"tenant": tenant})
            connection.execute(text("INSERT INTO products(id,tenant_id,name,description,price,product_type) VALUES (:id,:tenant,'Pizza','Test',50,'pizza')"), {"id": suffix, "tenant": tenant})
            for index, at, value in [(1, "2026-10-20 15:00:00+00", 100), (2, "2026-09-20 15:00:00+00", 50)]:
                oid = f"{suffix}-{index}"
                connection.execute(text("INSERT INTO orders(id,tenant_id,status,subtotal,total,shipping_fee,discount,created_at,fulfillment_type) VALUES (:id,:tenant,'delivered',:value,:value,0,0,:at,'delivery')"),
                    dict(id=oid, tenant=tenant, value=value, at=at))
                connection.execute(text("INSERT INTO payments(id,tenant_id,order_id,method,status,amount) VALUES (:id,:tenant,:id,'pix','paid',:value)"), dict(id=oid, tenant=tenant, value=value))
                connection.execute(text("INSERT INTO order_items(id,tenant_id,order_id,product_id,quantity,unit_price,total_price) VALUES (:id,:tenant,:id,:product,2,50,:value)"), dict(id=oid, tenant=tenant, product=suffix, value=value))
            now = datetime.now(timezone.utc)
            for kind, status, started, closed in [
                ("active", "aberta", now, None),
                ("closed", "encerrada", "2026-10-20 15:00:00+00", "2026-10-20 15:02:00+00"),
            ]:
                connection.execute(text("INSERT INTO chatbot_conversations(id,tenant_id,session_id,status,iniciada_em,encerrada_em) VALUES (:id,:tenant,:id,:status,:started,:closed)"),
                    dict(id=f"{suffix}-{kind}", tenant=tenant, status=status, started=started, closed=closed))
            connection.execute(text("INSERT INTO chatbot_messages(id,tenant_id,conversation_id,sender,mensagem,timestamp) VALUES (:id,:tenant,:conversation,'visitor','Teste local',:now)"),
                dict(id=f"{suffix}-message", tenant=tenant, conversation=f"{suffix}-active", now=now))
            connection.execute(text("INSERT INTO visitor_profiles(id,tenant_id,fingerprint) VALUES (:id,:tenant,:id)"), dict(id=suffix, tenant=tenant))
            for index in range(2):
                connection.execute(text("INSERT INTO visitor_sessions(id,tenant_id,visitor_id,landing_page,started_at) VALUES (:id,:tenant,:visitor,'/','2026-10-20 15:00:00+00')"),
                    dict(id=f"{suffix}-session-{index}", tenant=tenant, visitor=suffix))
            connection.execute(text("INSERT INTO visitor_events(id,tenant_id,visitor_id,event_type,page,metadata_json,created_at) VALUES (:id,:tenant,:visitor,'store_presence','/',:metadata,:now)"),
                dict(id=f"{suffix}-presence", tenant=tenant, visitor=suffix, metadata='{"tab_id":"test","sequence":1}', now=now))
            with Session(bind=connection, join_transaction_mode="create_savepoint") as db:
                bind_wave6_tenant_context(db, TenantContext(tenant_id=tenant, source=TenantSource.JOB))
                service = BIMobileService(db, tenant)
                query = BIMobileQuery(date=date(2026, 10, 20))
                data = service.analytics(query)
                assert data["totals"]["revenue"] == 100
                assert data["totals"]["pizzas"] == 2
                assert data["previous_totals"]["revenue"] == 50
                assert data["comparison"]["revenue"] == {"difference": 50, "percent": 100}
                assert sum(point["revenue"] for point in data["sales"]) == 100
                assert sum(point["previous_revenue"] or 0 for point in data["sales"]) == 50
                assert data["payments"] == [{"method": "pix", "orders": 1, "revenue": 100}]
                assert data["monthly"][-1]["revenue"] == 100
                assert data["attendance"]["visitors_online"] == 1
                assert data["attendance"]["unique_visitors"] == 1
                assert data["attendance"]["accesses"] == 2
                assert data["attendance"]["total_attendances"] == 1
                assert data["attendance"]["avg_attendance_seconds"] == 120
                assert data["attendance"]["chatbot"] == 1
                assert data["attendance"]["human_operators"] is None
                analysis = service.analyze(query.model_copy(update={"view": "general"}))
                assert analysis["engine"] == "calculated"
                assert "100.00" in analysis["summary"]
                assert any("12:00" in fact for fact in analysis["facts"])
                weekly = service.analytics(query.model_copy(update={"period": "90d", "grouping": "week", "view": "general"}))
                assert sum(point["revenue"] for point in weekly["sales"]) == weekly["totals"]["revenue"] == 150
                assert len(weekly["sales"]) == 13
        finally:
            transaction.rollback()
    engine.dispose()
