from __future__ import annotations

import json
import uuid
from datetime import date, datetime, time, timedelta, timezone
from typing import Iterable

from sqlalchemy import distinct, func, text
from sqlalchemy.orm import Session

from backend.models.business_intelligence import BusinessInsight, ProductPerformance
from backend.models.customer import Address, Customer
from backend.models.customer_event import CustomerEvent
from backend.models.delivery import Delivery
from backend.models.order import Order, OrderItem, OrderStatus
from backend.models.paid_traffic import AdDailyMetric
from backend.models.payment import Payment, PaymentStatus
from backend.models.product import Product


class BusinessIntelligenceService:
    """Read-only BI aggregation layer.

    The service consumes canonical operational tables and returns derived
    analytics. It does not mutate customers, orders, campaigns, coupons or CRM.
    """

    CANCELLED_STATUSES = ("cancelled", "refunded")
    PAID_PAYMENT_STATUSES = (PaymentStatus.approved, PaymentStatus.paid)
    MOBILE_EFFECTIVE_ORDER_STATUSES = (
        OrderStatus.paid,
        OrderStatus.pago,
        OrderStatus.preparing,
        OrderStatus.ready_for_pickup,
        OrderStatus.on_the_way,
        OrderStatus.delivered,
    )
    MOBILE_STATUS_BUCKETS = {
        "aguardando_pagamento": (
            OrderStatus.pending.value,
            OrderStatus.waiting_payment.value,
            OrderStatus.aguardando_pagamento.value,
            OrderStatus.pagamento_recusado.value,
            OrderStatus.pagamento_expirado.value,
        ),
        "pedido_confirmado": (OrderStatus.paid.value, OrderStatus.pago.value),
        "em_preparacao": (OrderStatus.preparing.value,),
        "pronto_para_entrega": (OrderStatus.ready_for_pickup.value,),
        "em_entrega": (OrderStatus.on_the_way.value,),
        "entregue": (OrderStatus.delivered.value,),
        "cancelado": (OrderStatus.cancelled.value, OrderStatus.refunded.value),
    }
    PAYMENT_PROBLEM_STATUSES = (
        PaymentStatus.rejected,
        PaymentStatus.cancelled,
        PaymentStatus.expired,
        PaymentStatus.failed,
        PaymentStatus.refunded,
    )
    PERIOD_DAYS = {"7d": 7, "30d": 30, "90d": 90}

    def __init__(self, db: Session):
        self._db = db

    def dashboard(self, period: str = "30d", date_from: date | None = None, date_to: date | None = None) -> dict:
        bounds = self.resolve_bounds(period, date_from, date_to)
        overview = self.get_overview(**bounds)
        sales = self.get_sales(**bounds)
        products = self.get_products(**bounds, limit=8)
        customers = self.get_customers(**bounds)
        marketing = self.get_marketing(**bounds)
        neighborhoods = self.get_neighborhoods(**bounds)
        insights = self.get_insights(overview, products, customers, marketing)
        insights = self._merge_persisted_insights(insights, bounds)
        recommendations = self.get_recommendations(insights)
        return {
            **self._period_payload(bounds),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "kpis": overview["kpis"],
            "sales": sales["by_day"],
            "products": products["products"],
            "customer_segments": customers["segments"],
            "top_customers": customers["top_customers"],
            "funnel": marketing["funnel"],
            "neighborhoods": neighborhoods["neighborhoods"],
            "insights": insights,
            "recommendations": recommendations,
        }

    def mobile(self, selected_date: date) -> dict:
        bounds = self.resolve_bounds("today", selected_date, selected_date)
        start_dt = bounds["start_dt"]
        end_dt = bounds["end_dt"]
        orders_q = self._orders_in_period(start_dt, end_dt)
        paid_orders_q = self._paid_orders_in_period(start_dt, end_dt)

        status_counts = {key: 0 for key in self.MOBILE_STATUS_BUCKETS}
        status_rows = (
            orders_q.with_entities(Order.status, func.count(Order.id))
            .group_by(Order.status)
            .all()
        )
        for raw_status, total in status_rows:
            status = getattr(raw_status, "value", raw_status)
            for key, bucket in self.MOBILE_STATUS_BUCKETS.items():
                if status in bucket:
                    status_counts[key] += int(total or 0)
                    break

        forecast_revenue = self._round(
            orders_q
            .filter(~Order.status.in_(self.CANCELLED_STATUSES))
            .with_entities(func.coalesce(func.sum(Order.total), 0))
            .scalar()
        )
        confirmed_revenue = self._round(
            paid_orders_q.with_entities(func.coalesce(func.sum(Order.total), 0)).scalar()
        )
        visitors_today = self._visitor_access_count(start_dt, end_dt)
        online_counts = self._online_presence_counts()

        return {
            "date": selected_date.isoformat(),
            "visitorsToday": visitors_today,
            "visitorsOnline": online_counts["visitors"],
            "customersOnline": online_counts["customers"],
            "forecastRevenue": forecast_revenue,
            "confirmedRevenue": confirmed_revenue,
            "ordersToday": orders_q.count(),
            "confirmedOrders": orders_q.filter(Order.status.in_(self.MOBILE_EFFECTIVE_ORDER_STATUSES)).count(),
            "ordersByStatus": status_counts,
            "generatedAt": datetime.now(timezone.utc).isoformat(),
        }

    def get_overview(self, start_dt: datetime, end_dt: datetime, period: str) -> dict:
        paid_orders_q = self._paid_orders_in_period(start_dt, end_dt)
        all_orders = self._orders_in_period(start_dt, end_dt)

        total_orders = all_orders.count()
        paid_orders = paid_orders_q.count()
        estimated_revenue = self._round(all_orders.with_entities(func.coalesce(func.sum(Order.total), 0)).scalar())
        effective_revenue = self._round(paid_orders_q.with_entities(func.coalesce(func.sum(Order.total), 0)).scalar())
        avg_ticket = self._round(effective_revenue / paid_orders if paid_orders else 0)
        cancelled = all_orders.filter(Order.status.in_(self.CANCELLED_STATUSES)).count()
        new_customers = (
            self._db.query(Customer)
            .filter(Customer.created_at >= start_dt, Customer.created_at <= end_dt)
            .count()
        )
        recurring_customers = (
            paid_orders_q.with_entities(Order.customer_id)
            .filter(Order.customer_id.isnot(None))
            .group_by(Order.customer_id)
            .having(func.count(Order.id) > 1)
            .count()
        )
        payment_problems = (
            self._db.query(Payment)
            .filter(Payment.created_at >= start_dt, Payment.created_at <= end_dt)
            .filter(Payment.status.in_(self.PAYMENT_PROBLEM_STATUSES))
            .count()
        )
        delayed_deliveries = self._delayed_deliveries(start_dt, end_dt)
        loyalty_points = self._round(paid_orders_q.with_entities(func.coalesce(func.sum(Order.loyalty_points_earned), 0)).scalar())
        discounts = self._round(paid_orders_q.with_entities(func.coalesce(func.sum(Order.discount), 0)).scalar())

        return {
            "kpis": [
                self._kpi("estimated_revenue", "Receita estimada", estimated_revenue, "currency", "Todos os pedidos criados no periodo"),
                self._kpi("effective_revenue", "Receita efetivada", effective_revenue, "currency", "Pedidos com pagamento confirmado"),
                self._kpi("orders", "Pedidos totais", total_orders, "number", f"{paid_orders} pedidos com pagamento confirmado"),
                self._kpi("average_ticket", "Ticket medio", avg_ticket, "currency", "Receita efetivada / pedidos pagos"),
                self._kpi("new_customers", "Clientes novos", new_customers, "number", "Cadastros no periodo"),
                self._kpi("recurring_customers", "Clientes recorrentes", recurring_customers, "number", "Compraram mais de uma vez no periodo"),
                self._kpi("cancelled_orders", "Cancelamentos", cancelled, "number", "Pedidos cancelados/estornados"),
                self._kpi("payment_problems", "Pagamentos com problema", payment_problems, "number", "Falhas, recusas ou estornos"),
                self._kpi("delayed_deliveries", "Entregas atrasadas", delayed_deliveries, "number", "Pedidos acima do prazo alvo"),
                self._kpi("discounts", "Descontos aplicados", discounts, "currency", "Cupons e descontos em pedidos pagos"),
                self._kpi("loyalty_points", "Pontos fidelidade", loyalty_points, "number", "Pontos gerados por pedidos pagos"),
            ],
            "raw": {
                "revenue": effective_revenue,
                "estimated_revenue": estimated_revenue,
                "effective_revenue": effective_revenue,
                "paid_orders": paid_orders,
                "total_orders": total_orders,
                "avg_ticket": avg_ticket,
                "cancelled": cancelled,
                "new_customers": new_customers,
                "recurring_customers": recurring_customers,
                "payment_problems": payment_problems,
                "delayed_deliveries": delayed_deliveries,
            },
        }

    def get_sales(self, start_dt: datetime, end_dt: datetime, period: str, granularity: str = "day") -> dict:
        rows = (
            self._paid_orders_in_period(start_dt, end_dt)
            .with_entities(
                func.date(Order.created_at).label("metric_date"),
                func.count(Order.id).label("orders"),
                func.coalesce(func.sum(Order.total), 0).label("revenue"),
            )
            .group_by(func.date(Order.created_at))
            .order_by(func.date(Order.created_at))
            .all()
        )
        by_day = [
            {
                "label": str(row.metric_date),
                "date": str(row.metric_date),
                "orders": int(row.orders or 0),
                "revenue": self._round(row.revenue),
                "average_ticket": self._round((row.revenue or 0) / row.orders) if row.orders else 0,
            }
            for row in rows
        ]

        hour_rows = (
            self._paid_orders_in_period(start_dt, end_dt)
            .with_entities(
                func.extract("hour", Order.created_at).label("hour"),
                func.count(Order.id).label("orders"),
                func.coalesce(func.sum(Order.total), 0).label("revenue"),
            )
            .group_by(func.extract("hour", Order.created_at))
            .order_by(func.extract("hour", Order.created_at))
            .all()
        )
        by_hour = [
            {"hour": int(row.hour or 0), "orders": int(row.orders or 0), "revenue": self._round(row.revenue)}
            for row in hour_rows
        ]
        return {**self._period_payload({"period": period, "start_dt": start_dt, "end_dt": end_dt}), "by_day": by_day, "by_hour": by_hour}

    def get_products(self, start_dt: datetime, end_dt: datetime, period: str, limit: int = 20) -> dict:
        rows = (
            self._db.query(
                OrderItem.product_id,
                Product.name,
                Product.category,
                func.count(distinct(OrderItem.order_id)).label("total_orders"),
                func.coalesce(func.sum(OrderItem.quantity), 0).label("quantity_sold"),
                func.coalesce(func.sum(OrderItem.total_price), 0).label("total_revenue"),
            )
            .join(Order, Order.id == OrderItem.order_id)
            .join(Payment, Payment.order_id == Order.id)
            .outerjoin(Product, Product.id == OrderItem.product_id)
            .filter(Order.created_at >= start_dt, Order.created_at <= end_dt)
            .filter(Payment.status.in_(self.PAID_PAYMENT_STATUSES))
            .filter(~Order.status.in_(self.CANCELLED_STATUSES))
            .group_by(OrderItem.product_id, Product.name, Product.category)
            .order_by(func.coalesce(func.sum(OrderItem.total_price), 0).desc())
            .limit(limit)
            .all()
        )
        total_revenue = sum(float(row.total_revenue or 0) for row in rows)
        top_count = max(1, int(len(rows) * 0.2 + 0.999)) if rows else 0
        products = [
            {
                "product_id": row.product_id,
                "name": row.name or "Produto removido",
                "category": row.category,
                "total_orders": int(row.total_orders or 0),
                "quantity_sold": int(row.quantity_sold or 0),
                "total_revenue": self._round(row.total_revenue),
                "share_pct": self._round((float(row.total_revenue or 0) / total_revenue) * 100 if total_revenue else 0),
                "is_top_20_percent": index < top_count,
            }
            for index, row in enumerate(rows)
        ]
        return {**self._period_payload({"period": period, "start_dt": start_dt, "end_dt": end_dt}), "products": products}

    def get_customers(self, start_dt: datetime, end_dt: datetime, period: str) -> dict:
        now = datetime.now(timezone.utc)
        inactive_cutoff = now - timedelta(days=30)
        total_customers = self._db.query(Customer).count()
        new_customers = self._db.query(Customer).filter(Customer.created_at >= start_dt, Customer.created_at <= end_dt).count()
        inactive = (
            self._db.query(Customer)
            .filter((Customer.last_order_at.is_(None)) | (Customer.last_order_at < inactive_cutoff))
            .count()
        )
        high_value_threshold = self._db.query(func.coalesce(func.avg(Customer.total_spent), 0)).scalar() or 0
        high_value = self._db.query(Customer).filter(Customer.total_spent > high_value_threshold, Customer.total_orders > 1).count()
        recurring = self._db.query(Customer).filter(Customer.total_orders > 1).count()
        low_ticket = self._db.query(Customer).filter(Customer.total_orders > 0, Customer.avg_ticket < 50).count()

        top_rows = (
            self._db.query(Customer)
            .filter(Customer.total_orders > 0)
            .order_by(Customer.total_spent.desc())
            .limit(8)
            .all()
        )
        top_customers = [
            {
                "customer_id": customer.id,
                "name": customer.name,
                "total_orders": customer.total_orders or 0,
                "total_spent": self._round(customer.total_spent),
                "avg_ticket": self._round(customer.avg_ticket),
                "last_order_at": customer.last_order_at.isoformat() if customer.last_order_at else None,
            }
            for customer in top_rows
        ]
        segments = [
            self._segment("new", "Clientes novos", "Cadastros realizados no periodo", new_customers),
            self._segment("recurring", "Clientes recorrentes", "Clientes com mais de um pedido", recurring),
            self._segment("inactive", "Clientes inativos", "Sem pedido nos ultimos 30 dias", inactive),
            self._segment("high_value", "Alto valor", "Acima do gasto medio da base e recorrentes", high_value),
            self._segment("low_ticket", "Baixo ticket", "Clientes com ticket medio abaixo de R$ 50", low_ticket),
            self._segment("base", "Base total", "Total de clientes cadastrados", total_customers),
        ]
        return {
            **self._period_payload({"period": period, "start_dt": start_dt, "end_dt": end_dt}),
            "segments": segments,
            "top_customers": top_customers,
        }

    def get_marketing(self, start_dt: datetime, end_dt: datetime, period: str) -> dict:
        events_q = self._db.query(CustomerEvent).filter(CustomerEvent.created_at >= start_dt, CustomerEvent.created_at <= end_dt)
        events_rows = (
            events_q.with_entities(CustomerEvent.event_type, func.count(CustomerEvent.id))
            .group_by(CustomerEvent.event_type)
            .order_by(func.count(CustomerEvent.id).desc())
            .all()
        )
        events_by_type = [{"event_type": row[0], "total": int(row[1] or 0)} for row in events_rows]
        event_counts = {row["event_type"]: row["total"] for row in events_by_type}
        visitors = event_counts.get("site_opened", 0) + event_counts.get("page_view", 0)
        carts = event_counts.get("add_to_cart", 0) + event_counts.get("cart_opened", 0)
        checkout = event_counts.get("checkout_started", 0)

        paid_orders = self._paid_orders_in_period(start_dt, end_dt).count()
        revenue = self._round(
            self._paid_orders_in_period(start_dt, end_dt)
            .with_entities(func.coalesce(func.sum(Order.total), 0))
            .scalar()
        )
        spend = self._round(
            self._db.query(func.coalesce(func.sum(AdDailyMetric.spend), 0))
            .filter(AdDailyMetric.metric_date >= start_dt.date(), AdDailyMetric.metric_date <= end_dt.date())
            .scalar()
        )
        funnel = [
            self._funnel("visitors", "Visitantes/eventos de entrada", visitors, visitors),
            self._funnel("cart", "Carrinhos", carts, visitors),
            self._funnel("checkout", "Checkout iniciado", checkout, visitors),
            self._funnel("orders", "Pedidos com pagamento confirmado", paid_orders, visitors),
        ]
        return {
            **self._period_payload({"period": period, "start_dt": start_dt, "end_dt": end_dt}),
            "spend": spend,
            "revenue": revenue,
            "roas": self._round(revenue / spend if spend else 0),
            "events_by_type": events_by_type,
            "funnel": funnel,
        }

    def get_neighborhoods(self, start_dt: datetime, end_dt: datetime, period: str, limit: int = 12) -> dict:
        # Use raw SQL here because visitor_profiles is owned by the marketing route module.
        raw_visitor_rows = self._db.execute(
            text("""
            SELECT
                COALESCE(NULLIF(TRIM(neighborhood), ''), 'Sem bairro') AS name,
                MAX(city) AS city,
                COUNT(DISTINCT id) AS visitors,
                COALESCE(SUM(total_sessions), 0) AS sessions,
                COALESCE(SUM(total_pageviews), 0) AS pageviews
            FROM visitor_profiles
            WHERE last_seen_at >= :start_dt
              AND last_seen_at <= :end_dt
              AND neighborhood IS NOT NULL
              AND TRIM(neighborhood) <> ''
            GROUP BY COALESCE(NULLIF(TRIM(neighborhood), ''), 'Sem bairro')
            """),
            {"start_dt": start_dt, "end_dt": end_dt},
        ).fetchall()
        by_key: dict[str, dict] = {}
        for row in raw_visitor_rows:
            name = row[0] or "Sem bairro"
            key = name.strip().lower()
            by_key[key] = {
                "neighborhood": name,
                "city": row[1],
                "visitors": int(row[2] or 0),
                "sessions": int(row[3] or 0),
                "pageviews": int(row[4] or 0),
                "visitor_orders": 0,
                "orders": 0,
                "revenue": 0.0,
            }

        raw_visitor_order_rows = self._db.execute(
            text("""
            SELECT
                COALESCE(NULLIF(TRIM(vp.neighborhood), ''), 'Sem bairro') AS name,
                COUNT(ve.id) AS visitor_orders
            FROM visitor_events ve
            JOIN visitor_profiles vp ON vp.id = ve.visitor_id
            WHERE ve.created_at >= :start_dt
              AND ve.created_at <= :end_dt
              AND ve.event_type = 'order_created'
              AND vp.neighborhood IS NOT NULL
              AND TRIM(vp.neighborhood) <> ''
            GROUP BY COALESCE(NULLIF(TRIM(vp.neighborhood), ''), 'Sem bairro')
            """),
            {"start_dt": start_dt, "end_dt": end_dt},
        ).fetchall()
        for row in raw_visitor_order_rows:
            name = row[0] or "Sem bairro"
            key = name.strip().lower()
            item = by_key.setdefault(key, {
                "neighborhood": name,
                "city": None,
                "visitors": 0,
                "sessions": 0,
                "pageviews": 0,
                "visitor_orders": 0,
                "orders": 0,
                "revenue": 0.0,
            })
            item["visitor_orders"] = int(row[1] or 0)

        order_rows = (
            self._db.query(
                Address.neighborhood,
                func.count(Order.id).label("orders"),
                func.coalesce(func.sum(Order.total), 0).label("revenue"),
            )
            .join(Order, Order.address_id == Address.id)
            .join(Payment, Payment.order_id == Order.id)
            .filter(Order.created_at >= start_dt, Order.created_at <= end_dt)
            .filter(Payment.status.in_(self.PAID_PAYMENT_STATUSES))
            .filter(~Order.status.in_(self.CANCELLED_STATUSES))
            .filter(Address.neighborhood.isnot(None), func.trim(Address.neighborhood) != "")
            .group_by(Address.neighborhood)
            .all()
        )
        for row in order_rows:
            name = row.neighborhood or "Sem bairro"
            key = name.strip().lower()
            item = by_key.setdefault(key, {
                "neighborhood": name,
                "city": None,
                "visitors": 0,
                "sessions": 0,
                "pageviews": 0,
                "visitor_orders": 0,
                "orders": 0,
                "revenue": 0.0,
            })
            item["orders"] = int(row.orders or 0)
            item["revenue"] = self._round(row.revenue)

        neighborhoods = []
        for item in by_key.values():
            sessions = item["sessions"] or item["visitors"] or 0
            orders = item["orders"] or item["visitor_orders"] or 0
            neighborhoods.append({
                **item,
                "conversion_pct": self._round((orders / sessions) * 100 if sessions else 0),
            })
        neighborhoods.sort(key=lambda item: (item["orders"], item["visitor_orders"], item["visitors"], item["revenue"]), reverse=True)
        return {
            **self._period_payload({"period": period, "start_dt": start_dt, "end_dt": end_dt}),
            "neighborhoods": neighborhoods[:limit],
        }

    def get_operations(self, start_dt: datetime, end_dt: datetime, period: str) -> dict:
        orders_q = self._orders_in_period(start_dt, end_dt)
        status_rows = (
            orders_q.with_entities(Order.status, func.count(Order.id))
            .group_by(Order.status)
            .order_by(func.count(Order.id).desc())
            .all()
        )
        avg_total_time = orders_q.with_entities(func.coalesce(func.avg(Order.total_time_minutes), 0)).scalar()
        avg_delivery_time = orders_q.with_entities(func.coalesce(func.avg(Order.delivery_time_minutes), 0)).scalar()
        return {
            **self._period_payload({"period": period, "start_dt": start_dt, "end_dt": end_dt}),
            "delayed_deliveries": self._delayed_deliveries(start_dt, end_dt),
            "avg_total_time_minutes": self._round(avg_total_time),
            "avg_delivery_time_minutes": self._round(avg_delivery_time),
            "orders_by_status": [
                {"status": getattr(row[0], "value", row[0]), "total": int(row[1] or 0)}
                for row in status_rows
            ],
        }

    def get_insights(self, overview: dict, products: dict, customers: dict, marketing: dict) -> list[dict]:
        raw = overview["raw"]
        items: list[dict] = []
        top_products = [p for p in products["products"] if p["is_top_20_percent"]]
        inactive = next((s["total_customers"] for s in customers["segments"] if s["key"] == "inactive"), 0)
        base = next((s["total_customers"] for s in customers["segments"] if s["key"] == "base"), 0)

        if top_products and sum(p["share_pct"] for p in top_products) >= 60:
            share = self._round(sum(p["share_pct"] for p in top_products))
            items.append(self._insight(
                "pareto_products",
                "product",
                "Pareto forte no cardapio",
                f"{len(top_products)} produtos concentram {share}% do faturamento dos itens analisados.",
                "high",
                "Destacar estes produtos na home e criar combos com bebidas ou acompanhamentos.",
            ))
        if base and inactive / base >= 0.25:
            items.append(self._insight(
                "inactive_customers",
                "customer",
                "Base com muitos clientes inativos",
                f"{inactive} clientes estao sem comprar ha pelo menos 30 dias.",
                "high",
                "Criar campanha de reativacao com cupom controlado para clientes inativos.",
            ))
        if raw["payment_problems"] > 0:
            items.append(self._insight(
                "payment_problems",
                "sales",
                "Pagamentos com atrito",
                f"{raw['payment_problems']} pagamentos tiveram falha, recusa, expiracao ou estorno.",
                "medium",
                "Revisar meios de pagamento e acompanhar pedidos pendentes rapidamente.",
            ))
        if raw["delayed_deliveries"] > 0:
            items.append(self._insight(
                "delayed_deliveries",
                "operations",
                "Risco operacional em entregas",
                f"{raw['delayed_deliveries']} entregas passaram do prazo alvo.",
                "medium",
                "Investigar gargalos de cozinha, despacho e disponibilidade de motoboys.",
            ))
        if raw["paid_orders"] == 0:
            items.append(self._insight(
                "insufficient_sales",
                "sales",
                "Dados insuficientes para recomendacoes comerciais",
                "Nao ha pedidos com pagamento confirmado no periodo selecionado.",
                "low",
                "Aumentar o periodo de analise ou validar se existem pedidos concluídos.",
                actionable=False,
            ))
        if marketing["spend"] > 0 and marketing["roas"] < 1:
            items.append(self._insight(
                "low_roas",
                "marketing",
                "Campanhas com retorno baixo",
                f"O ROAS estimado esta em {marketing['roas']}x no periodo.",
                "high",
                "Pausar campanhas sem conversao e realocar verba para canais/produtos com venda comprovada.",
            ))
        return items

    def get_recommendations(self, insights: Iterable[dict]) -> list[dict]:
        module_by_type = {
            "customer": "CRM",
            "product": "Produtos",
            "sales": "Pedidos",
            "operations": "Logistica",
            "marketing": "Marketing",
        }
        return [
            {
                "id": f"rec_{item['id']}",
                "insight_id": item["id"],
                "title": item["title"],
                "priority": item["impact_level"],
                "action": item["recommendation"],
                "reason": item["description"],
                "expected_impact": self._expected_impact(item["impact_level"]),
                "target_module": module_by_type.get(item["insight_type"], "Painel"),
                "persisted": bool(item.get("persisted", False)),
            }
            for item in insights
            if item.get("actionable", True)
        ]

    def run_analysis(self, period: str = "30d", date_from: date | None = None, date_to: date | None = None) -> dict:
        bounds = self.resolve_bounds(period, date_from, date_to)
        overview = self.get_overview(**bounds)
        products = self.get_products(**bounds, limit=100)
        customers = self.get_customers(**bounds)
        marketing = self.get_marketing(**bounds)
        insights = self.get_insights(overview, products, customers, marketing)
        saved_insights = self._save_insights(insights, bounds)
        self._save_product_performance(products["products"], bounds)
        recommendations = self.get_recommendations(saved_insights)
        return {
            "status": "completed",
            "message": "Analise BI executada em modo read-only. Nenhuma acao foi aplicada automaticamente.",
            "insights": saved_insights,
            "recommendations": recommendations,
        }

    def latest_insights(self, status: str | None = None, limit: int = 50) -> list[dict]:
        q = self._db.query(BusinessInsight)
        if status:
            q = q.filter(BusinessInsight.status == status)
        rows = q.order_by(BusinessInsight.created_at.desc()).limit(limit).all()
        return [self._insight_row_to_dict(row) for row in rows]

    def update_insight_status(self, insight_id: str, status: str) -> dict:
        row = self._db.query(BusinessInsight).filter(BusinessInsight.id == insight_id).first()
        if not row:
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail="Insight nao encontrado.")
        row.status = status
        row.updated_at = datetime.now(timezone.utc)
        row.resolved_at = datetime.now(timezone.utc) if status in ("resolved", "ignored") else None
        self._db.commit()
        self._db.refresh(row)
        return self._insight_row_to_dict(row)

    def resolve_bounds(self, period: str, date_from: date | None = None, date_to: date | None = None) -> dict:
        return self._bounds(period, date_from, date_to)

    def period_payload(self, bounds: dict) -> dict:
        return self._period_payload(bounds)

    def _orders_in_period(self, start_dt: datetime, end_dt: datetime):
        return self._db.query(Order).filter(Order.created_at >= start_dt, Order.created_at <= end_dt)

    def _paid_orders_in_period(self, start_dt: datetime, end_dt: datetime):
        return (
            self._orders_in_period(start_dt, end_dt)
            .join(Payment, Payment.order_id == Order.id)
            .filter(Payment.status.in_(self.PAID_PAYMENT_STATUSES))
            .filter(~Order.status.in_(self.CANCELLED_STATUSES))
        )

    def _online_presence_counts(self) -> dict[str, int]:
        # visitor_profiles and marketing_settings are owned by the marketing route module.
        online_minutes = self._db.execute(
            text("""
            SELECT COALESCE(online_visitor_minutes, 5)
            FROM marketing_settings
            WHERE id = 'default'
            """)
        ).scalar() or 5
        try:
            online_minutes = max(int(online_minutes), 1)
        except (TypeError, ValueError):
            online_minutes = 5

        online_since = datetime.now(timezone.utc) - timedelta(minutes=online_minutes)
        visitors = self._db.execute(
            text("""
            SELECT COUNT(*)
            FROM visitor_profiles
            WHERE last_seen_at >= :online_since
            """),
            {"online_since": online_since},
        ).scalar() or 0
        customers = self._db.execute(
            text("""
            SELECT COUNT(DISTINCT customer_id)
            FROM customer_events
            WHERE created_at >= :online_since
              AND customer_id IS NOT NULL
            """),
            {"online_since": online_since},
        ).scalar() or 0
        return {"visitors": int(visitors), "customers": int(customers)}

    def _visitor_access_count(self, start_dt: datetime, end_dt: datetime) -> int:
        # Mirrors Marketing > Visitantes so BI Mobile counts people who accessed the store in the selected day.
        total = self._db.execute(
            text("""
            SELECT COUNT(*)
            FROM (
                SELECT DISTINCT visitor_id
                FROM visitor_events
                WHERE created_at >= :start_dt AND created_at <= :end_dt
                UNION
                SELECT DISTINCT visitor_id
                FROM visitor_sessions
                WHERE started_at >= :start_dt AND started_at <= :end_dt
                UNION
                SELECT id AS visitor_id
                FROM visitor_profiles
                WHERE first_seen_at >= :start_dt AND first_seen_at <= :end_dt
                UNION
                SELECT id AS visitor_id
                FROM visitor_profiles
                WHERE last_seen_at >= :start_dt AND last_seen_at <= :end_dt
            ) period_visitors
            """),
            {"start_dt": start_dt, "end_dt": end_dt},
        ).scalar()
        return int(total or 0)

    def _merge_persisted_insights(self, insights: list[dict], bounds: dict) -> list[dict]:
        merged: list[dict] = []
        for item in insights:
            row = (
                self._db.query(BusinessInsight)
                .filter(BusinessInsight.dedupe_key == self._dedupe_key(item, bounds))
                .first()
            )
            if row and row.status in ("resolved", "ignored"):
                continue
            if row:
                item = {
                    **item,
                    "id": row.id,
                    "status": row.status,
                    "persisted": True,
                }
            merged.append(item)
        return merged

    def _save_insights(self, insights: list[dict], bounds: dict) -> list[dict]:
        saved: list[dict] = []
        for item in insights:
            dedupe_key = self._dedupe_key(item, bounds)
            row = self._db.query(BusinessInsight).filter(BusinessInsight.dedupe_key == dedupe_key).first()
            if row is None:
                row = BusinessInsight(
                    id=str(uuid.uuid4()),
                    dedupe_key=dedupe_key,
                    status="active",
                    created_at=datetime.now(timezone.utc),
                )
                self._db.add(row)
            row.insight_type = item["insight_type"]
            row.title = item["title"]
            row.description = item["description"]
            row.impact_level = item["impact_level"]
            row.recommendation = item["recommendation"]
            row.actionable = bool(item.get("actionable", True))
            row.period = bounds["period"]
            row.date_from = bounds["start_dt"].date()
            row.date_to = bounds["end_dt"].date()
            row.source = "rules"
            row.metadata_json = json.dumps({"generated_id": item["id"]}, ensure_ascii=False)
            row.updated_at = datetime.now(timezone.utc)
            self._db.flush()
            if row.status not in ("resolved", "ignored"):
                saved.append(self._insight_row_to_dict(row))
        self._db.commit()
        return saved

    def _save_product_performance(self, products: list[dict], bounds: dict) -> None:
        metric_date = bounds["end_dt"].date()
        self._db.query(ProductPerformance).filter(ProductPerformance.metric_date == metric_date).delete(synchronize_session=False)
        now = datetime.now(timezone.utc)
        for item in products:
            self._db.add(ProductPerformance(
                id=str(uuid.uuid4()),
                metric_date=metric_date,
                product_id=item.get("product_id"),
                product_name_snapshot=item["name"],
                category_snapshot=item.get("category"),
                total_orders=item.get("total_orders", 0),
                quantity_sold=item.get("quantity_sold", 0),
                total_revenue=item.get("total_revenue", 0),
                margin_estimate=None,
                is_top_20_percent=bool(item.get("is_top_20_percent", False)),
                last_updated=now,
            ))
        self._db.commit()

    def _dedupe_key(self, item: dict, bounds: dict) -> str:
        return "|".join([
            bounds["period"],
            bounds["start_dt"].date().isoformat(),
            bounds["end_dt"].date().isoformat(),
            item["insight_type"],
            item["title"].strip().lower(),
        ])[:300]

    def _insight_row_to_dict(self, row: BusinessInsight) -> dict:
        return {
            "id": row.id,
            "insight_type": row.insight_type,
            "title": row.title,
            "description": row.description,
            "impact_level": row.impact_level,
            "recommendation": row.recommendation,
            "actionable": row.actionable,
            "status": row.status,
            "persisted": True,
        }

    def _bounds(self, period: str, date_from: date | None, date_to: date | None) -> dict:
        today = datetime.now(timezone.utc).date()
        if date_from or date_to:
            start_date = date_from or today
            end_date = date_to or today
        elif period == "today":
            start_date = today
            end_date = today
        elif period == "month":
            start_date = today.replace(day=1)
            end_date = today
        elif period == "previous_month":
            first_this_month = today.replace(day=1)
            end_date = first_this_month - timedelta(days=1)
            start_date = end_date.replace(day=1)
        else:
            days = self.PERIOD_DAYS.get(period, 30)
            start_date = today - timedelta(days=days - 1)
            end_date = today

        return {
            "period": period,
            "start_dt": datetime.combine(start_date, time.min, tzinfo=timezone.utc),
            "end_dt": datetime.combine(end_date, time.max, tzinfo=timezone.utc),
        }

    def _period_payload(self, bounds: dict) -> dict:
        return {
            "period": bounds["period"],
            "date_from": bounds["start_dt"].date().isoformat(),
            "date_to": bounds["end_dt"].date().isoformat(),
        }

    def _delayed_deliveries(self, start_dt: datetime, end_dt: datetime) -> int:
        return (
            self._db.query(Delivery)
            .join(Order, Order.id == Delivery.order_id)
            .filter(Order.created_at >= start_dt, Order.created_at <= end_dt)
            .filter(Order.delivered_at.isnot(None))
            .filter(Order.total_time_minutes.isnot(None))
            .filter(Order.total_time_minutes > Order.target_delivery_minutes)
            .count()
        )

    def _kpi(self, key: str, label: str, value: float | int, unit: str, helper: str) -> dict:
        return {"key": key, "label": label, "value": self._round(value), "unit": unit, "helper": helper}

    def _segment(self, key: str, name: str, description: str, total: int) -> dict:
        return {"key": key, "name": name, "description": description, "total_customers": int(total or 0)}

    def _funnel(self, key: str, label: str, value: int, base: int) -> dict:
        return {
            "key": key,
            "label": label,
            "value": int(value or 0),
            "conversion_pct": self._round((value / base) * 100 if base else 0),
        }

    def _insight(
        self,
        insight_id: str,
        insight_type: str,
        title: str,
        description: str,
        impact_level: str,
        recommendation: str,
        actionable: bool = True,
    ) -> dict:
        return {
            "id": insight_id,
            "insight_type": insight_type,
            "title": title,
            "description": description,
            "impact_level": impact_level,
            "recommendation": recommendation,
            "actionable": actionable,
            "status": "active",
            "persisted": False,
        }

    def _expected_impact(self, impact_level: str) -> str:
        return {
            "critical": "Evitar perda financeira ou operacional imediata.",
            "high": "Aumentar receita, recorrencia ou reduzir perda relevante.",
            "medium": "Melhorar eficiencia e reduzir atritos do funil.",
            "low": "Apoiar acompanhamento gerencial.",
        }.get(impact_level, "Apoiar tomada de decisao.")

    def _round(self, value) -> float:
        return round(float(value or 0), 2)
