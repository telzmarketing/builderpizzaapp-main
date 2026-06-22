from __future__ import annotations

import json
import uuid
from datetime import date, datetime, timezone

from fastapi import HTTPException
from sqlalchemy import and_, distinct, func, or_
from sqlalchemy.orm import Session

from backend.models.campaign import Campaign
from backend.models.coupon import Coupon, CouponUsage
from backend.models.customer import Customer
from backend.models.customer_event import CustomerEvent
from backend.models.marketing_intelligence import MarketingGoal, MarketingTimelineEvent
from backend.models.order import Order, OrderItem
from backend.models.paid_traffic import AdDailyMetric, CampaignLink, TrackingEvent, TrackingSession, TrafficCampaign
from backend.models.payment import Payment, PaymentStatus
from backend.models.product import Product
from backend.schemas.marketing_intelligence import (
    MarketingGoalCreate,
    MarketingGoalStatusUpdate,
    MarketingGoalUpdate,
    MarketingTimelineEventCreate,
    MarketingTimelineEventUpdate,
)
from backend.services.business_intelligence_service import BusinessIntelligenceService


class MarketingIntelligenceService:
    """Marketing analytics, goals and timeline over existing ERP data."""

    CANCELLED_ORDER_STATUSES = ("cancelled", "refunded")
    PAID_PAYMENT_STATUSES = (PaymentStatus.approved, PaymentStatus.paid)

    CLICK_EVENT_TYPES = ("click", "link_click", "cta_click", "button_click")
    LEAD_EVENT_TYPES = ("lead", "lead_created", "form_submit", "whatsapp_lead", "newsletter_signup")
    PRODUCT_VIEW_EVENT_TYPES = ("product_view", "product_viewed", "view_content", "ViewContent")
    CART_EVENT_TYPES = ("add_to_cart", "cart_opened", "cart_item_added", "AddToCart")
    CHECKOUT_EVENT_TYPES = ("checkout_start", "checkout_started", "InitiateCheckout", "initiate_checkout")

    CHANNEL_LABELS = {
        "direct": "Direto",
        "organic": "Organico",
        "meta": "Meta Ads",
        "facebook": "Facebook",
        "instagram": "Instagram",
        "google": "Google",
        "tiktok": "TikTok",
        "whatsapp": "WhatsApp",
        "email": "E-mail",
        "manual": "Manual",
    }

    METRIC_LABELS = {
        "revenue": ("Receita", "currency"),
        "paid_orders": ("Pedidos pagos", "number"),
        "leads": ("Leads", "number"),
        "conversions": ("Conversoes", "number"),
        "roas": ("ROAS", "number"),
        "roi": ("ROI", "number"),
        "cac": ("CAC", "currency"),
        "cpa": ("CPA", "currency"),
        "cpl": ("CPL", "currency"),
        "average_ticket": ("Ticket medio", "currency"),
    }

    def __init__(self, db: Session):
        self._db = db
        self._bi = BusinessIntelligenceService(db)

    def dashboard(self, period: str = "30d", date_from: date | None = None, date_to: date | None = None) -> dict:
        bounds = self._bounds(period, date_from, date_to)
        revenue = self._revenue(bounds)
        spend = self._spend(bounds)
        paid_orders = self._paid_orders_query(bounds).count()
        all_orders = self._orders_query(bounds).count()
        visitors = self._visitor_count(bounds)
        leads = self._event_count(bounds, self.LEAD_EVENT_TYPES)
        new_customers = self._db.query(Customer).filter(
            Customer.created_at >= bounds["start_dt"],
            Customer.created_at <= bounds["end_dt"],
        ).count()
        avg_ticket = self._round(revenue / paid_orders if paid_orders else 0)

        payload = self._period_payload(bounds)
        return {
            **payload,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "kpis": [
                self._kpi("spend", "Investimento registrado", spend, "currency", "Soma de ad_daily_metrics.spend no periodo."),
                self._kpi("revenue", "Receita atribuida", revenue, "currency", "Pedidos com pagamento confirmado no periodo."),
                self._kpi("orders", "Pedidos pagos", paid_orders, "number", f"{all_orders} pedidos criados no periodo."),
                self._kpi("average_ticket", "Ticket medio", avg_ticket, "currency", "Receita atribuida / pedidos pagos."),
                self._kpi("visitors", "Visitantes rastreados", visitors, "number", "Sessoes/eventos de tracking registrados."),
                self._kpi("leads", "Leads registrados", leads, "number", "Eventos reais classificados como lead."),
                self._kpi("new_customers", "Clientes novos", new_customers, "number", "Clientes criados no periodo."),
                self._kpi("roas", "ROAS", self._ratio(revenue, spend), "number", "Receita atribuida / investimento registrado."),
                self._kpi("roi", "ROI", self._ratio(revenue - spend, spend), "number", "(Receita atribuida - investimento) / investimento."),
                self._kpi("cpa", "CPA", self._ratio(spend, paid_orders), "currency", "Investimento registrado / pedidos pagos."),
                self._kpi("cac", "CAC", self._ratio(spend, new_customers), "currency", "Investimento registrado / clientes novos."),
                self._kpi("cpl", "CPL", self._ratio(spend, leads), "currency", "Investimento registrado / leads registrados."),
            ],
            "campaigns": self.campaigns(period, date_from, date_to, limit=5)["campaigns"],
            "channels": self.channels(period, date_from, date_to, limit=8)["channels"],
            "funnel": self.funnel(period, date_from, date_to)["funnel"],
            "products": self.products(period, date_from, date_to, limit=8)["products"],
            "promotions": self.promotions(period, date_from, date_to, limit=8)["promotions"],
        }

    def campaigns(
        self,
        period: str = "30d",
        date_from: date | None = None,
        date_to: date | None = None,
        limit: int = 50,
    ) -> dict:
        bounds = self._bounds(period, date_from, date_to)
        items: list[dict] = []

        campaign_utms = self._campaign_utm_map()
        traffic_campaigns = (
            self._db.query(TrafficCampaign)
            .order_by(TrafficCampaign.created_at.desc())
            .limit(max(limit, 1))
            .all()
        )
        for campaign in traffic_campaigns:
            utms = campaign_utms.get(campaign.id, set())
            orders_q = self._campaign_orders_query(bounds, campaign.id, utms)
            revenue = self._round(orders_q.with_entities(func.coalesce(func.sum(Order.total), 0)).scalar())
            orders = orders_q.with_entities(func.count(distinct(Order.id))).scalar() or 0
            spend = self._round(
                self._db.query(func.coalesce(func.sum(AdDailyMetric.spend), 0))
                .filter(AdDailyMetric.traffic_campaign_id == campaign.id)
                .filter(AdDailyMetric.metric_date >= bounds["date_from"], AdDailyMetric.metric_date <= bounds["date_to"])
                .scalar()
            )
            visitors = self._campaign_visitors(bounds, campaign.id, utms)
            clicks = self._campaign_event_count(bounds, campaign.id, utms, self.CLICK_EVENT_TYPES)
            leads = self._campaign_event_count(bounds, campaign.id, utms, self.LEAD_EVENT_TYPES)
            items.append({
                "id": campaign.id,
                "name": campaign.name,
                "source_type": "traffic",
                "platform": campaign.platform,
                "status": campaign.status,
                "spend": spend,
                "revenue": revenue,
                "orders": int(orders),
                "visitors": visitors,
                "clicks": clicks,
                "leads": leads,
                "roas": self._ratio(revenue, spend),
                "roi": self._ratio(revenue - spend, spend),
                "cpa": self._ratio(spend, orders),
                "cpl": self._ratio(spend, leads),
            })

        promo_campaigns = (
            self._db.query(Campaign)
            .order_by(Campaign.created_at.desc())
            .limit(max(limit, 1))
            .all()
        )
        for campaign in promo_campaigns:
            orders_q = (
                self._paid_orders_query(bounds)
                .join(Coupon, Coupon.id == Order.coupon_id)
                .filter(Coupon.campaign_id == campaign.id)
            )
            orders = orders_q.with_entities(func.count(distinct(Order.id))).scalar() or 0
            revenue = self._round(orders_q.with_entities(func.coalesce(func.sum(Order.total), 0)).scalar())
            uses = (
                self._db.query(func.count(CouponUsage.id))
                .join(Coupon, Coupon.id == CouponUsage.coupon_id)
                .filter(Coupon.campaign_id == campaign.id)
                .filter(CouponUsage.created_at >= bounds["start_dt"], CouponUsage.created_at <= bounds["end_dt"])
                .scalar() or 0
            )
            if orders == 0 and uses == 0:
                continue
            items.append({
                "id": campaign.id,
                "name": campaign.name,
                "source_type": "promotion",
                "platform": "internal",
                "status": self._enum_value(campaign.status),
                "spend": 0.0,
                "revenue": revenue,
                "orders": int(orders),
                "visitors": 0,
                "clicks": 0,
                "leads": 0,
                "roas": 0.0,
                "roi": 0.0,
                "cpa": 0.0,
                "cpl": 0.0,
            })

        items = sorted(items, key=lambda item: (item["revenue"], item["orders"]), reverse=True)[:limit]
        return {**self._period_payload(bounds), "campaigns": items}

    def channels(
        self,
        period: str = "30d",
        date_from: date | None = None,
        date_to: date | None = None,
        limit: int = 50,
    ) -> dict:
        bounds = self._bounds(period, date_from, date_to)
        by_channel: dict[str, dict] = {}

        order_rows = (
            self._paid_orders_query(bounds)
            .outerjoin(TrafficCampaign, TrafficCampaign.id == Order.campaign_id)
            .with_entities(
                TrafficCampaign.platform,
                Order.utm_source,
                func.count(distinct(Order.id)).label("orders"),
                func.coalesce(func.sum(Order.total), 0).label("revenue"),
            )
            .group_by(TrafficCampaign.platform, Order.utm_source)
            .all()
        )
        for row in order_rows:
            key = self._channel_key(row.platform or row.utm_source)
            item = self._channel_item(by_channel, key)
            item["orders"] += int(row.orders or 0)
            item["revenue"] = self._round(item["revenue"] + float(row.revenue or 0))

        spend_rows = (
            self._db.query(
                AdDailyMetric.platform,
                func.coalesce(func.sum(AdDailyMetric.spend), 0).label("spend"),
            )
            .filter(AdDailyMetric.metric_date >= bounds["date_from"], AdDailyMetric.metric_date <= bounds["date_to"])
            .group_by(AdDailyMetric.platform)
            .all()
        )
        for row in spend_rows:
            key = self._channel_key(row.platform)
            item = self._channel_item(by_channel, key)
            item["spend"] = self._round(item["spend"] + float(row.spend or 0))

        session_rows = (
            self._db.query(
                TrackingSession.utm_source,
                func.count(distinct(TrackingSession.id)).label("visitors"),
            )
            .filter(TrackingSession.first_seen_at >= bounds["start_dt"], TrackingSession.first_seen_at <= bounds["end_dt"])
            .group_by(TrackingSession.utm_source)
            .all()
        )
        for row in session_rows:
            key = self._channel_key(row.utm_source)
            item = self._channel_item(by_channel, key)
            item["visitors"] += int(row.visitors or 0)

        for event_types, field in ((self.CLICK_EVENT_TYPES, "clicks"), (self.LEAD_EVENT_TYPES, "leads")):
            event_rows = (
                self._db.query(
                    TrackingEvent.utm_source,
                    func.count(TrackingEvent.id).label("total"),
                )
                .filter(TrackingEvent.created_at >= bounds["start_dt"], TrackingEvent.created_at <= bounds["end_dt"])
                .filter(TrackingEvent.event_type.in_(event_types))
                .group_by(TrackingEvent.utm_source)
                .all()
            )
            for row in event_rows:
                key = self._channel_key(row.utm_source)
                item = self._channel_item(by_channel, key)
                item[field] += int(row.total or 0)

        items = []
        for item in by_channel.values():
            item["roas"] = self._ratio(item["revenue"], item["spend"])
            item["conversion_rate"] = self._ratio(item["orders"], item["visitors"])
            items.append(item)

        items = sorted(items, key=lambda item: (item["revenue"], item["visitors"], item["spend"]), reverse=True)[:limit]
        return {**self._period_payload(bounds), "channels": items}

    def funnel(self, period: str = "30d", date_from: date | None = None, date_to: date | None = None) -> dict:
        bounds = self._bounds(period, date_from, date_to)
        visitors = self._visitor_count(bounds)
        steps = [
            ("visitors", "Visitantes rastreados", visitors),
            ("product_views", "Visualizacoes de produto", self._event_count(bounds, self.PRODUCT_VIEW_EVENT_TYPES)),
            ("carts", "Carrinhos", self._event_count(bounds, self.CART_EVENT_TYPES)),
            ("checkout", "Checkout iniciado", self._event_count(bounds, self.CHECKOUT_EVENT_TYPES)),
            ("orders", "Pedidos criados", self._orders_query(bounds).count()),
            ("paid_orders", "Pedidos pagos", self._paid_orders_query(bounds).count()),
        ]
        first_value = steps[0][2] or 0
        previous_value = first_value
        funnel = []
        for key, label, value in steps:
            funnel.append({
                "key": key,
                "label": label,
                "value": int(value or 0),
                "conversion_pct": self._round((value / first_value) * 100 if first_value else 0),
                "previous_conversion_pct": self._round((value / previous_value) * 100 if previous_value else 0),
            })
            previous_value = int(value or 0)
        return {**self._period_payload(bounds), "funnel": funnel}

    def products(
        self,
        period: str = "30d",
        date_from: date | None = None,
        date_to: date | None = None,
        limit: int = 50,
    ) -> dict:
        bounds = self._bounds(period, date_from, date_to)
        order_rows = (
            self._db.query(
                OrderItem.product_id,
                Product.name,
                Product.category,
                func.count(distinct(OrderItem.order_id)).label("orders"),
                func.coalesce(func.sum(OrderItem.quantity), 0).label("quantity_sold"),
                func.coalesce(func.sum(OrderItem.total_price), 0).label("revenue"),
            )
            .join(Order, Order.id == OrderItem.order_id)
            .join(Payment, Payment.order_id == Order.id)
            .outerjoin(Product, Product.id == OrderItem.product_id)
            .filter(Order.created_at >= bounds["start_dt"], Order.created_at <= bounds["end_dt"])
            .filter(Payment.status.in_(self.PAID_PAYMENT_STATUSES))
            .filter(~Order.status.in_(self.CANCELLED_ORDER_STATUSES))
            .group_by(OrderItem.product_id, Product.name, Product.category)
            .all()
        )
        by_product: dict[str, dict] = {}
        for row in order_rows:
            key = row.product_id or "removed"
            by_product[key] = {
                "product_id": row.product_id,
                "name": row.name or "Produto removido",
                "category": row.category,
                "views": 0,
                "carts": 0,
                "orders": int(row.orders or 0),
                "quantity_sold": int(row.quantity_sold or 0),
                "revenue": self._round(row.revenue),
                "average_ticket": self._round(float(row.revenue or 0) / row.orders if row.orders else 0),
                "conversion_rate": 0.0,
            }

        for event_types, field in ((self.PRODUCT_VIEW_EVENT_TYPES, "views"), (self.CART_EVENT_TYPES, "carts")):
            event_rows = (
                self._db.query(
                    CustomerEvent.product_id,
                    Product.name,
                    Product.category,
                    func.count(CustomerEvent.id).label("total"),
                )
                .outerjoin(Product, Product.id == CustomerEvent.product_id)
                .filter(CustomerEvent.created_at >= bounds["start_dt"], CustomerEvent.created_at <= bounds["end_dt"])
                .filter(CustomerEvent.product_id.isnot(None))
                .filter(CustomerEvent.event_type.in_(event_types))
                .group_by(CustomerEvent.product_id, Product.name, Product.category)
                .all()
            )
            for row in event_rows:
                key = row.product_id
                item = by_product.setdefault(key, {
                    "product_id": row.product_id,
                    "name": row.name or "Produto removido",
                    "category": row.category,
                    "views": 0,
                    "carts": 0,
                    "orders": 0,
                    "quantity_sold": 0,
                    "revenue": 0.0,
                    "average_ticket": 0.0,
                    "conversion_rate": 0.0,
                })
                item[field] += int(row.total or 0)

        items = []
        for item in by_product.values():
            item["conversion_rate"] = self._ratio(item["orders"], item["views"])
            items.append(item)

        items = sorted(items, key=lambda item: (item["revenue"], item["views"], item["orders"]), reverse=True)[:limit]
        return {**self._period_payload(bounds), "products": items}

    def promotions(
        self,
        period: str = "30d",
        date_from: date | None = None,
        date_to: date | None = None,
        limit: int = 50,
    ) -> dict:
        bounds = self._bounds(period, date_from, date_to)
        items: list[dict] = []

        coupon_order_rows = (
            self._paid_orders_query(bounds)
            .join(Coupon, Coupon.id == Order.coupon_id)
            .with_entities(
                Coupon.id,
                Coupon.code,
                Coupon.description,
                func.count(distinct(Order.id)).label("orders"),
                func.coalesce(func.sum(Order.total), 0).label("revenue"),
                func.coalesce(func.sum(Order.discount), 0).label("discount"),
            )
            .group_by(Coupon.id, Coupon.code, Coupon.description)
            .all()
        )
        coupon_usage_counts = dict(
            self._db.query(CouponUsage.coupon_id, func.count(CouponUsage.id))
            .filter(CouponUsage.created_at >= bounds["start_dt"], CouponUsage.created_at <= bounds["end_dt"])
            .group_by(CouponUsage.coupon_id)
            .all()
        )
        coupon_ids = {row.id for row in coupon_order_rows} | set(coupon_usage_counts)
        coupons = {coupon.id: coupon for coupon in self._db.query(Coupon).filter(Coupon.id.in_(coupon_ids)).all()} if coupon_ids else {}
        for row in coupon_order_rows:
            uses = int(coupon_usage_counts.get(row.id, 0) or 0)
            revenue = self._round(row.revenue)
            orders = int(row.orders or 0)
            items.append({
                "id": row.id,
                "name": row.description or row.code,
                "promotion_type": "coupon",
                "code": row.code,
                "uses": uses,
                "orders": orders,
                "revenue": revenue,
                "discount": self._round(row.discount),
                "average_ticket": self._round(revenue / orders if orders else 0),
            })
        for coupon_id, uses in coupon_usage_counts.items():
            if any(item["id"] == coupon_id for item in items):
                continue
            coupon = coupons.get(coupon_id)
            if not coupon:
                continue
            items.append({
                "id": coupon.id,
                "name": coupon.description or coupon.code,
                "promotion_type": "coupon",
                "code": coupon.code,
                "uses": int(uses or 0),
                "orders": 0,
                "revenue": 0.0,
                "discount": 0.0,
                "average_ticket": 0.0,
            })

        product_promo_rows = (
            self._db.query(
                OrderItem.promotion_id,
                OrderItem.promotion_name,
                func.count(distinct(OrderItem.order_id)).label("orders"),
                func.coalesce(func.sum(OrderItem.quantity), 0).label("uses"),
                func.coalesce(func.sum(OrderItem.total_price), 0).label("revenue"),
                func.coalesce(func.sum(OrderItem.promotion_discount), 0).label("discount"),
            )
            .join(Order, Order.id == OrderItem.order_id)
            .join(Payment, Payment.order_id == Order.id)
            .filter(Order.created_at >= bounds["start_dt"], Order.created_at <= bounds["end_dt"])
            .filter(Payment.status.in_(self.PAID_PAYMENT_STATUSES))
            .filter(~Order.status.in_(self.CANCELLED_ORDER_STATUSES))
            .filter(OrderItem.promotion_id.isnot(None))
            .group_by(OrderItem.promotion_id, OrderItem.promotion_name)
            .all()
        )
        for row in product_promo_rows:
            revenue = self._round(row.revenue)
            orders = int(row.orders or 0)
            items.append({
                "id": row.promotion_id,
                "name": row.promotion_name or "Promocao de produto",
                "promotion_type": "product_promotion",
                "code": None,
                "uses": int(row.uses or 0),
                "orders": orders,
                "revenue": revenue,
                "discount": self._round(row.discount),
                "average_ticket": self._round(revenue / orders if orders else 0),
            })

        items = sorted(items, key=lambda item: (item["revenue"], item["uses"], item["orders"]), reverse=True)[:limit]
        return {**self._period_payload(bounds), "promotions": items}

    def planning(
        self,
        status: str | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        limit: int = 100,
    ) -> dict:
        return {
            "goals": self.list_goals(status=status, limit=limit)["goals"],
            "timeline": self.list_timeline(date_from=date_from, date_to=date_to, limit=limit)["timeline"],
        }

    def list_goals(self, status: str | None = None, limit: int = 100) -> dict:
        query = self._db.query(MarketingGoal)
        if status:
            query = query.filter(MarketingGoal.status == status)
        rows = query.order_by(MarketingGoal.period_end.desc(), MarketingGoal.created_at.desc()).limit(limit).all()
        return {"goals": [self._goal_to_dict(row) for row in rows]}

    def create_goal(self, body: MarketingGoalCreate, created_by: str | None = None) -> dict:
        self._validate_goal_period(body.period_start, body.period_end)
        row = MarketingGoal(
            id=f"mg-{uuid.uuid4().hex[:12]}",
            created_by=created_by,
            completed_at=datetime.now(timezone.utc) if body.status == "completed" else None,
            **self._goal_payload(body.model_dump()),
        )
        self._db.add(row)
        self._db.commit()
        self._db.refresh(row)
        return self._goal_to_dict(row)

    def update_goal(self, goal_id: str, body: MarketingGoalUpdate) -> dict:
        row = self._get_goal(goal_id)
        data = body.model_dump(exclude_unset=True)
        period_start = data.get("period_start", row.period_start)
        period_end = data.get("period_end", row.period_end)
        self._validate_goal_period(period_start, period_end)

        payload = self._goal_payload(data, partial=True)
        for key, value in payload.items():
            setattr(row, key, value)
        if "status" in payload:
            row.completed_at = datetime.now(timezone.utc) if payload["status"] == "completed" else None
        self._db.commit()
        self._db.refresh(row)
        return self._goal_to_dict(row)

    def update_goal_status(self, goal_id: str, body: MarketingGoalStatusUpdate) -> dict:
        row = self._get_goal(goal_id)
        row.status = body.status
        row.completed_at = datetime.now(timezone.utc) if body.status == "completed" else None
        self._db.commit()
        self._db.refresh(row)
        return self._goal_to_dict(row)

    def delete_goal(self, goal_id: str) -> None:
        row = self._get_goal(goal_id)
        self._db.delete(row)
        self._db.commit()

    def list_timeline(
        self,
        date_from: date | None = None,
        date_to: date | None = None,
        event_type: str | None = None,
        category: str | None = None,
        impact_level: str | None = None,
        search: str | None = None,
        limit: int = 100,
    ) -> dict:
        query = self._db.query(MarketingTimelineEvent)
        if date_from:
            query = query.filter(MarketingTimelineEvent.event_date >= self._bi.resolve_bounds("today", date_from, date_from)["start_dt"])
        if date_to:
            query = query.filter(MarketingTimelineEvent.event_date <= self._bi.resolve_bounds("today", date_to, date_to)["end_dt"])
        if event_type:
            query = query.filter(MarketingTimelineEvent.event_type == event_type)
        if category:
            query = query.filter(MarketingTimelineEvent.category == category)
        if impact_level:
            query = query.filter(MarketingTimelineEvent.impact_level == impact_level)
        if search:
            pattern = f"%{search.strip()}%"
            query = query.filter(or_(MarketingTimelineEvent.title.ilike(pattern), MarketingTimelineEvent.description.ilike(pattern)))
        rows = query.order_by(MarketingTimelineEvent.event_date.desc(), MarketingTimelineEvent.created_at.desc()).limit(limit).all()
        return {"timeline": [self._timeline_to_dict(row) for row in rows]}

    def create_timeline_event(self, body: MarketingTimelineEventCreate, created_by: str | None = None) -> dict:
        row = MarketingTimelineEvent(
            id=f"mt-{uuid.uuid4().hex[:12]}",
            created_by=created_by,
            **self._timeline_payload(body.model_dump()),
        )
        self._db.add(row)
        self._db.commit()
        self._db.refresh(row)
        return self._timeline_to_dict(row)

    def update_timeline_event(self, event_id: str, body: MarketingTimelineEventUpdate) -> dict:
        row = self._get_timeline_event(event_id)
        payload = self._timeline_payload(body.model_dump(exclude_unset=True), partial=True)
        for key, value in payload.items():
            setattr(row, key, value)
        self._db.commit()
        self._db.refresh(row)
        return self._timeline_to_dict(row)

    def delete_timeline_event(self, event_id: str) -> None:
        row = self._get_timeline_event(event_id)
        self._db.delete(row)
        self._db.commit()

    def _get_goal(self, goal_id: str) -> MarketingGoal:
        row = self._db.query(MarketingGoal).filter(MarketingGoal.id == goal_id).first()
        if not row:
            raise HTTPException(status_code=404, detail="Meta de marketing nao encontrada.")
        return row

    def _get_timeline_event(self, event_id: str) -> MarketingTimelineEvent:
        row = self._db.query(MarketingTimelineEvent).filter(MarketingTimelineEvent.id == event_id).first()
        if not row:
            raise HTTPException(status_code=404, detail="Evento de timeline nao encontrado.")
        return row

    def _validate_goal_period(self, period_start: date, period_end: date) -> None:
        if period_end < period_start:
            raise HTTPException(status_code=400, detail="Periodo final deve ser maior ou igual ao periodo inicial.")

    def _goal_payload(self, data: dict, partial: bool = False) -> dict:
        payload = dict(data)
        if "metadata" in payload:
            payload["metadata_json"] = self._json_dump(payload.pop("metadata") or {})
        elif not partial:
            payload["metadata_json"] = "{}"
        return payload

    def _timeline_payload(self, data: dict, partial: bool = False) -> dict:
        payload = dict(data)
        if "tags" in payload:
            payload["tags"] = self._json_dump(payload.get("tags") or [])
        elif not partial:
            payload["tags"] = "[]"
        if "metadata" in payload:
            payload["metadata_json"] = self._json_dump(payload.pop("metadata") or {})
        elif not partial:
            payload["metadata_json"] = "{}"
        return payload

    def _goal_to_dict(self, row: MarketingGoal) -> dict:
        return {
            "id": row.id,
            "title": row.title,
            "description": row.description,
            "metric_key": row.metric_key,
            "target_value": self._round(row.target_value),
            "baseline_value": None if row.baseline_value is None else self._round(row.baseline_value),
            "comparison_direction": row.comparison_direction,
            "period_start": row.period_start,
            "period_end": row.period_end,
            "status": row.status,
            "priority": row.priority,
            "campaign_id": row.campaign_id,
            "traffic_campaign_id": row.traffic_campaign_id,
            "coupon_id": row.coupon_id,
            "promotion_id": row.promotion_id,
            "product_id": row.product_id,
            "channel": row.channel,
            "notes": row.notes,
            "metadata": self._json_load(row.metadata_json, {}),
            "created_by": row.created_by,
            "created_at": row.created_at,
            "updated_at": row.updated_at,
            "completed_at": row.completed_at,
            "progress": self._goal_progress(row),
        }

    def _timeline_to_dict(self, row: MarketingTimelineEvent) -> dict:
        return {
            "id": row.id,
            "title": row.title,
            "description": row.description,
            "event_type": row.event_type,
            "event_date": row.event_date,
            "impact_level": row.impact_level,
            "category": row.category,
            "tags": self._json_load(row.tags, []),
            "attachment_url": row.attachment_url,
            "attachment_type": row.attachment_type,
            "goal_id": row.goal_id,
            "campaign_id": row.campaign_id,
            "traffic_campaign_id": row.traffic_campaign_id,
            "coupon_id": row.coupon_id,
            "promotion_id": row.promotion_id,
            "product_id": row.product_id,
            "metadata": self._json_load(row.metadata_json, {}),
            "created_by": row.created_by,
            "created_at": row.created_at,
            "updated_at": row.updated_at,
        }

    def _goal_progress(self, row: MarketingGoal) -> dict:
        current_value = self._goal_metric_value(row)
        baseline = row.baseline_value
        target = float(row.target_value or 0)
        if row.comparison_direction == "decrease":
            reached = current_value <= target
            if baseline is not None and baseline > target:
                progress_pct = ((baseline - current_value) / (baseline - target)) * 100
                remaining = max(current_value - target, 0)
            elif current_value > 0:
                progress_pct = (target / current_value) * 100
                remaining = max(current_value - target, 0)
            else:
                progress_pct = 100 if target >= 0 else 0
                remaining = 0
        else:
            reached = current_value >= target
            if baseline is not None and target > baseline:
                progress_pct = ((current_value - baseline) / (target - baseline)) * 100
            elif target > 0:
                progress_pct = (current_value / target) * 100
            else:
                progress_pct = 100 if current_value >= target else 0
            remaining = max(target - current_value, 0)

        label, unit = self.METRIC_LABELS.get(row.metric_key, (row.metric_key, "number"))
        return {
            "current_value": self._round(current_value),
            "baseline_value": None if baseline is None else self._round(baseline),
            "target_value": self._round(target),
            "progress_pct": self._round(max(min(progress_pct, 100), 0)),
            "remaining_value": self._round(remaining),
            "reached": bool(reached),
            "metric_label": label,
            "unit": unit,
            "calculated_at": datetime.now(timezone.utc).isoformat(),
        }

    def _goal_metric_value(self, row: MarketingGoal) -> float:
        bounds = self._bounds("custom", row.period_start, row.period_end)
        if row.product_id:
            return self._metric_from_products(row.metric_key, bounds, row.product_id)
        if row.coupon_id or row.promotion_id:
            return self._metric_from_promotions(row.metric_key, bounds, row.coupon_id or row.promotion_id)
        if row.traffic_campaign_id or row.campaign_id:
            return self._metric_from_campaigns(row.metric_key, bounds, row.traffic_campaign_id or row.campaign_id)
        if row.channel:
            return self._metric_from_channels(row.metric_key, bounds, row.channel)
        return self._metric_from_dashboard(row.metric_key, bounds)

    def _metric_from_dashboard(self, metric_key: str, bounds: dict) -> float:
        dashboard = self.dashboard(period="custom", date_from=bounds["date_from"], date_to=bounds["date_to"])
        by_key = {item["key"]: item["value"] for item in dashboard["kpis"]}
        if metric_key == "paid_orders":
            return float(by_key.get("orders", 0))
        if metric_key == "conversions":
            return float(max(self._conversion_count(bounds), by_key.get("orders", 0)))
        return float(by_key.get(metric_key, 0))

    def _metric_from_campaigns(self, metric_key: str, bounds: dict, entity_id: str | None) -> float:
        rows = self.campaigns(period="custom", date_from=bounds["date_from"], date_to=bounds["date_to"], limit=200)["campaigns"]
        item = next((row for row in rows if row["id"] == entity_id), None)
        return self._metric_from_entity_item(metric_key, item)

    def _metric_from_channels(self, metric_key: str, bounds: dict, channel: str | None) -> float:
        rows = self.channels(period="custom", date_from=bounds["date_from"], date_to=bounds["date_to"], limit=200)["channels"]
        normalized = self._channel_key(channel)
        item = next((row for row in rows if row["channel"] == normalized), None)
        return self._metric_from_entity_item(metric_key, item)

    def _metric_from_products(self, metric_key: str, bounds: dict, product_id: str | None) -> float:
        rows = self.products(period="custom", date_from=bounds["date_from"], date_to=bounds["date_to"], limit=200)["products"]
        item = next((row for row in rows if row["product_id"] == product_id), None)
        return self._metric_from_entity_item(metric_key, item)

    def _metric_from_promotions(self, metric_key: str, bounds: dict, entity_id: str | None) -> float:
        rows = self.promotions(period="custom", date_from=bounds["date_from"], date_to=bounds["date_to"], limit=200)["promotions"]
        item = next((row for row in rows if row["id"] == entity_id), None)
        return self._metric_from_entity_item(metric_key, item)

    def _metric_from_entity_item(self, metric_key: str, item: dict | None) -> float:
        if not item:
            return 0
        mapping = {
            "revenue": item.get("revenue", 0),
            "paid_orders": item.get("orders", 0),
            "leads": item.get("leads", 0),
            "conversions": item.get("orders", item.get("conversions", 0)),
            "roas": item.get("roas", 0),
            "roi": item.get("roi", 0),
            "cac": item.get("cac", 0),
            "cpa": item.get("cpa", 0),
            "cpl": item.get("cpl", 0),
            "average_ticket": item.get("average_ticket", 0),
        }
        return float(mapping.get(metric_key, 0) or 0)

    def _conversion_count(self, bounds: dict) -> int:
        event_types = ("conversion", "purchase", "Purchase", "order_paid")
        return self._event_count(bounds, event_types)

    def _json_dump(self, value) -> str:
        try:
            return json.dumps(value, ensure_ascii=False)
        except TypeError:
            return "{}"

    def _json_load(self, raw: str | None, fallback):
        if not raw:
            return fallback
        try:
            return json.loads(raw)
        except (TypeError, ValueError):
            return fallback

    def _bounds(self, period: str, date_from: date | None, date_to: date | None) -> dict:
        return self._bi.resolve_bounds(period, date_from, date_to)

    def _period_payload(self, bounds: dict) -> dict:
        return self._bi.period_payload(bounds)

    def _orders_query(self, bounds: dict):
        return self._db.query(Order).filter(Order.created_at >= bounds["start_dt"], Order.created_at <= bounds["end_dt"])

    def _paid_orders_query(self, bounds: dict):
        return (
            self._orders_query(bounds)
            .join(Payment, Payment.order_id == Order.id)
            .filter(Payment.status.in_(self.PAID_PAYMENT_STATUSES))
            .filter(~Order.status.in_(self.CANCELLED_ORDER_STATUSES))
        )

    def _revenue(self, bounds: dict) -> float:
        return self._round(self._paid_orders_query(bounds).with_entities(func.coalesce(func.sum(Order.total), 0)).scalar())

    def _spend(self, bounds: dict) -> float:
        return self._round(
            self._db.query(func.coalesce(func.sum(AdDailyMetric.spend), 0))
            .filter(AdDailyMetric.metric_date >= bounds["date_from"], AdDailyMetric.metric_date <= bounds["date_to"])
            .scalar()
        )

    def _campaign_utm_map(self) -> dict[str, set[str]]:
        rows = self._db.query(CampaignLink.campaign_id, CampaignLink.utm_campaign).filter(CampaignLink.utm_campaign.isnot(None)).all()
        result: dict[str, set[str]] = {}
        for campaign_id, utm_campaign in rows:
            if campaign_id and utm_campaign:
                result.setdefault(campaign_id, set()).add(utm_campaign)
        return result

    def _campaign_filter(self, campaign_id: str, utms: set[str]):
        conditions = [Order.campaign_id == campaign_id]
        if utms:
            conditions.append(Order.utm_campaign.in_(utms))
        return or_(*conditions)

    def _campaign_orders_query(self, bounds: dict, campaign_id: str, utms: set[str]):
        return self._paid_orders_query(bounds).filter(self._campaign_filter(campaign_id, utms))

    def _campaign_tracking_filter(self, model, campaign_id: str, utms: set[str]):
        conditions = [model.campaign_id == campaign_id]
        if utms:
            conditions.append(model.utm_campaign.in_(utms))
        return or_(*conditions)

    def _campaign_visitors(self, bounds: dict, campaign_id: str, utms: set[str]) -> int:
        session_count = (
            self._db.query(func.count(distinct(TrackingSession.id)))
            .filter(TrackingSession.first_seen_at >= bounds["start_dt"], TrackingSession.first_seen_at <= bounds["end_dt"])
            .filter(self._campaign_tracking_filter(TrackingSession, campaign_id, utms))
            .scalar() or 0
        )
        event_session_count = (
            self._db.query(func.count(distinct(TrackingEvent.session_id)))
            .filter(TrackingEvent.created_at >= bounds["start_dt"], TrackingEvent.created_at <= bounds["end_dt"])
            .filter(TrackingEvent.session_id.isnot(None))
            .filter(self._campaign_tracking_filter(TrackingEvent, campaign_id, utms))
            .scalar() or 0
        )
        return int(max(session_count, event_session_count))

    def _campaign_event_count(self, bounds: dict, campaign_id: str, utms: set[str], event_types: tuple[str, ...]) -> int:
        return int(
            self._db.query(func.count(TrackingEvent.id))
            .filter(TrackingEvent.created_at >= bounds["start_dt"], TrackingEvent.created_at <= bounds["end_dt"])
            .filter(TrackingEvent.event_type.in_(event_types))
            .filter(self._campaign_tracking_filter(TrackingEvent, campaign_id, utms))
            .scalar() or 0
        )

    def _visitor_count(self, bounds: dict) -> int:
        session_count = (
            self._db.query(func.count(distinct(TrackingSession.id)))
            .filter(TrackingSession.first_seen_at >= bounds["start_dt"], TrackingSession.first_seen_at <= bounds["end_dt"])
            .scalar() or 0
        )
        event_session_count = (
            self._db.query(func.count(distinct(TrackingEvent.session_id)))
            .filter(TrackingEvent.created_at >= bounds["start_dt"], TrackingEvent.created_at <= bounds["end_dt"])
            .filter(TrackingEvent.session_id.isnot(None))
            .scalar() or 0
        )
        customer_event_sessions = (
            self._db.query(func.count(distinct(CustomerEvent.session_id)))
            .filter(CustomerEvent.created_at >= bounds["start_dt"], CustomerEvent.created_at <= bounds["end_dt"])
            .filter(CustomerEvent.session_id.isnot(None))
            .scalar() or 0
        )
        return int(max(session_count, event_session_count, customer_event_sessions))

    def _event_count(self, bounds: dict, event_types: tuple[str, ...]) -> int:
        tracking_total = (
            self._db.query(func.count(TrackingEvent.id))
            .filter(TrackingEvent.created_at >= bounds["start_dt"], TrackingEvent.created_at <= bounds["end_dt"])
            .filter(TrackingEvent.event_type.in_(event_types))
            .scalar() or 0
        )
        customer_total = (
            self._db.query(func.count(CustomerEvent.id))
            .filter(CustomerEvent.created_at >= bounds["start_dt"], CustomerEvent.created_at <= bounds["end_dt"])
            .filter(CustomerEvent.event_type.in_(event_types))
            .scalar() or 0
        )
        return int(tracking_total + customer_total)

    def _channel_item(self, by_channel: dict[str, dict], key: str) -> dict:
        return by_channel.setdefault(key, {
            "channel": key,
            "label": self.CHANNEL_LABELS.get(key, key.title()),
            "spend": 0.0,
            "revenue": 0.0,
            "orders": 0,
            "visitors": 0,
            "clicks": 0,
            "leads": 0,
            "roas": 0.0,
            "conversion_rate": 0.0,
        })

    def _channel_key(self, value: str | None) -> str:
        normalized = str(value or "").strip().lower()
        return normalized or "direct"

    def _kpi(self, key: str, label: str, value: float | int, unit: str, helper: str) -> dict:
        return {
            "key": key,
            "label": label,
            "value": self._round(value),
            "unit": unit,
            "helper": helper,
        }

    def _ratio(self, numerator: float | int, denominator: float | int) -> float:
        return self._round((float(numerator or 0) / float(denominator or 0)) if denominator else 0)

    def _round(self, value: float | int | None) -> float:
        return round(float(value or 0), 2)

    def _enum_value(self, value) -> str | None:
        if value is None:
            return None
        return getattr(value, "value", str(value))
