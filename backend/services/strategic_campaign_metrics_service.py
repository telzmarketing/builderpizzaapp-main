from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation

from sqlalchemy import func
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from backend.models.cmv import OrderCmvSnapshot
from backend.models.order import Order, OrderItem, OrderStatus
from backend.models.paid_traffic import AdDailyMetric
from backend.models.payment import Payment, PaymentStatus
from backend.models.product import Product
from backend.models.strategic_campaign import StrategicCampaign, StrategicCapacitySlot, StrategicReservation
from backend.routes.marketing import VisitorEvent


class StrategicCampaignMetricsService:
    """Tenant-scoped read model for strategic campaign results.

    External advertising platforms are never called from this request. Their
    asynchronously synchronized ``ad_daily_metrics`` rows are an optional read
    source, so an unavailable source cannot block internal campaign metrics.
    """

    EVENT_TYPES = {
        "views": {"strategic_campaign_view"},
        "offer_clicks": {"strategic_campaign_offer_click"},
        "offer_scrolls": {"strategic_campaign_scroll_to_offers"},
        "checkout_starts": {"checkout_started", "checkout_start", "InitiateCheckout"},
    }
    ACTIVE_RESERVATION_STATUSES = ("held", "confirmed")
    EXCLUDED_ORDER_STATUSES = (OrderStatus.cancelled, OrderStatus.refunded)
    PAID_PAYMENT_STATUSES = (PaymentStatus.approved, PaymentStatus.paid)

    def __init__(self, db: Session, tenant_id: str):
        self.db = db
        self.tenant_id = tenant_id

    def get(self, campaign_id: str, date_from: date | None = None, date_to: date | None = None) -> dict:
        campaign = self.db.query(StrategicCampaign).filter(
            StrategicCampaign.id == campaign_id,
            StrategicCampaign.tenant_id == self.tenant_id,
        ).first()
        if not campaign:
            raise LookupError("Campanha estratégica não encontrada.")

        end_date = date_to or datetime.now(timezone.utc).date()
        start_date = date_from or (end_date - timedelta(days=29))
        if end_date < start_date:
            raise ValueError("date_to deve ser maior ou igual a date_from.")
        start_dt = datetime.combine(start_date, datetime.min.time(), tzinfo=timezone.utc)
        end_dt = datetime.combine(end_date + timedelta(days=1), datetime.min.time(), tzinfo=timezone.utc)

        event_metrics = self._event_metrics(campaign_id, start_dt, end_dt)
        order_metrics = self._order_metrics(campaign_id, start_dt, end_dt)
        operational = self._operational_metrics(campaign_id, start_dt, end_dt, order_metrics["order_ids"])

        config = campaign.marketing_config or {}
        planned_budget = self._optional_money(config.get("planned_budget"))
        traffic_campaign_id = str(config.get("traffic_campaign_id") or "").strip() or None
        warnings: list[str] = []
        if config.get("planned_budget") is not None and planned_budget is None:
            warnings.append("Orçamento planejado inválido; valor indisponível.")

        try:
            media = self._media_metrics(traffic_campaign_id, start_date, end_date)
        except SQLAlchemyError:
            media = self._empty_media_metrics("Falha ao consultar métricas de mídia sincronizadas.")
        if media["warning"]:
            warnings.append(media["warning"])

        financial = self._financial_metrics(
            revenue=order_metrics["revenue"], order_ids=order_metrics["order_ids"], spend=media["spend"]
        )
        warnings.extend(financial.pop("warnings"))

        paid_orders = order_metrics["paid_orders"]
        sessions = event_metrics["sessions"]
        revenue = order_metrics["revenue"]
        spend = media["spend"]
        roas = round(revenue / spend, 4) if spend is not None and spend > 0 else None
        conversion_rate = round(paid_orders / sessions * 100, 2) if sessions else None

        funnel = {
            "views": event_metrics["views"],
            "offer_clicks": event_metrics["offer_clicks"],
            "offer_scrolls": event_metrics["offer_scrolls"],
            "checkout_starts": event_metrics["checkout_starts"],
            "visitors": event_metrics["visitors"],
            "sessions": sessions,
            "paid_orders": paid_orders,
        }
        commercial = {
            "paid_orders": paid_orders,
            "revenue": revenue,
            "average_ticket": round(revenue / paid_orders, 2) if paid_orders else None,
            "scheduled_paid_orders": order_metrics["scheduled_paid_orders"],
            "pizzas_sold": operational["pizzas_sold"],
        }
        warning = " ".join(dict.fromkeys(warnings)) or None
        return {
            # Existing fields are preserved for published clients.
            "campaign_id": campaign.id,
            "campaign_name": campaign.name,
            "period": {"date_from": start_date.isoformat(), "date_to": end_date.isoformat()},
            "funnel": funnel,
            "revenue": revenue,
            "planned_budget": planned_budget,
            "spend": spend,
            "roas": roas,
            "conversion_rate": conversion_rate,
            "attribution": {
                "source": "strategic_campaign_id_on_order",
                "spend_source": "ad_daily_metrics" if traffic_campaign_id else None,
                "warning": warning,
            },
            # Additive C8 blocks with explicit, auditable definitions.
            "commercial": commercial,
            "marketing": {
                "spend": spend,
                "impressions": media["impressions"],
                "ad_clicks": media["clicks"],
                "platform_conversions": media["conversions"],
                "ctr": self._ratio_percent(media["clicks"], media["impressions"]),
                "cpc": self._ratio(media["spend"], media["clicks"]),
                "cpa": self._ratio(media["spend"], paid_orders),
                "cac": self._ratio(media["spend"], paid_orders),
                "roas": roas,
                "data_available": media["available"],
            },
            "financial": financial,
            "operational": operational,
            "definitions": self._definitions(),
            "data_quality": {
                "warnings": list(dict.fromkeys(warnings)),
                "external_sources_non_blocking": True,
            },
        }

    def _event_metrics(self, campaign_id: str, start_dt: datetime, end_dt: datetime) -> dict:
        events = self.db.query(
            VisitorEvent.event_type, VisitorEvent.visitor_id, VisitorEvent.session_id, VisitorEvent.metadata_json
        ).filter(
            VisitorEvent.tenant_id == self.tenant_id,
            VisitorEvent.created_at >= start_dt,
            VisitorEvent.created_at < end_dt,
            VisitorEvent.event_type.in_(tuple(event for values in self.EVENT_TYPES.values() for event in values)),
        ).all()
        counts = {key: 0 for key in self.EVENT_TYPES}
        visitor_ids: set[str] = set()
        session_ids: set[str] = set()
        for event_type, visitor_id, session_id, metadata_json in events:
            metadata = self._metadata(metadata_json)
            if str(metadata.get("campaign_id") or "") != campaign_id:
                continue
            for key, allowed in self.EVENT_TYPES.items():
                if event_type in allowed:
                    counts[key] += 1
            if visitor_id:
                visitor_ids.add(visitor_id)
            if session_id:
                session_ids.add(session_id)
        return {**counts, "visitors": len(visitor_ids), "sessions": len(session_ids)}

    def _paid_orders_query(self, campaign_id: str, start_dt: datetime, end_dt: datetime):
        return self.db.query(Order).join(
            Payment, (Payment.order_id == Order.id) & (Payment.tenant_id == self.tenant_id)
        ).filter(
            Order.tenant_id == self.tenant_id,
            Order.strategic_campaign_id == campaign_id,
            Order.created_at >= start_dt,
            Order.created_at < end_dt,
            Order.archived_at.is_(None),
            Order.status.notin_(self.EXCLUDED_ORDER_STATUSES),
            Payment.status.in_(self.PAID_PAYMENT_STATUSES),
        )

    def _order_metrics(self, campaign_id: str, start_dt: datetime, end_dt: datetime) -> dict:
        rows = self._paid_orders_query(campaign_id, start_dt, end_dt).with_entities(
            Order.id, Order.total, Order.is_scheduled
        ).all()
        return {
            "order_ids": [row.id for row in rows],
            "paid_orders": len(rows),
            "revenue": round(sum(float(row.total or 0) for row in rows), 2),
            "scheduled_paid_orders": sum(1 for row in rows if row.is_scheduled),
        }

    def _media_metrics(self, traffic_campaign_id: str | None, start_date: date, end_date: date) -> dict:
        if not traffic_campaign_id:
            return self._empty_media_metrics("Campanha de tráfego não configurada; mídia, ROAS e ROI indisponíveis.")
        row = self.db.query(
            func.count(AdDailyMetric.id),
            func.sum(AdDailyMetric.spend),
            func.sum(AdDailyMetric.impressions),
            func.sum(AdDailyMetric.clicks),
            func.sum(AdDailyMetric.conversions),
        ).filter(
            AdDailyMetric.tenant_id == self.tenant_id,
            AdDailyMetric.traffic_campaign_id == traffic_campaign_id,
            AdDailyMetric.metric_date >= start_date,
            AdDailyMetric.metric_date <= end_date,
        ).one()
        if not row[0]:
            return self._empty_media_metrics("Campanha de tráfego configurada sem dados sincronizados no período.")
        return {
            "available": True,
            "spend": round(float(row[1] or 0), 2),
            "impressions": int(row[2] or 0),
            "clicks": int(row[3] or 0),
            "conversions": round(float(row[4] or 0), 2),
            "warning": None,
        }

    @staticmethod
    def _empty_media_metrics(warning: str) -> dict:
        return {
            "available": False,
            "spend": None,
            "impressions": None,
            "clicks": None,
            "conversions": None,
            "warning": warning,
        }

    def _financial_metrics(self, *, revenue: float, order_ids: list[str], spend: float | None) -> dict:
        if not order_ids:
            cmv = 0.0
            cmv_complete = True
        else:
            snapshots = self.db.query(OrderCmvSnapshot).filter(
                OrderCmvSnapshot.tenant_id == self.tenant_id,
                OrderCmvSnapshot.order_id.in_(order_ids),
            ).all()
            cmv_complete = len(snapshots) == len(order_ids) and all(
                not row.missing_recipe and not row.missing_cost for row in snapshots
            )
            cmv = round(sum(float(row.cost_total or 0) for row in snapshots), 2) if cmv_complete else None

        warnings: list[str] = []
        if not cmv_complete:
            warnings.append("CMV incompleto para pedidos pagos; margem, resultado e ROI indisponíveis.")
        gross_margin = round(revenue - cmv, 2) if cmv is not None else None
        result = round(gross_margin - spend, 2) if gross_margin is not None and spend is not None else None
        invested_cost = round(cmv + spend, 2) if cmv is not None and spend is not None else None
        roi = round(result / invested_cost * 100, 2) if result is not None and invested_cost and invested_cost > 0 else None
        return {
            "cmv": cmv,
            "cmv_complete": cmv_complete,
            "gross_margin": gross_margin,
            "media_cost": spend,
            "invested_cost": invested_cost,
            "result": result,
            "roi": roi,
            "warnings": warnings,
        }

    def _operational_metrics(
        self, campaign_id: str, start_dt: datetime, end_dt: datetime, order_ids: list[str]
    ) -> dict:
        slot_row = self.db.query(
            func.count(StrategicCapacitySlot.id),
            func.sum(StrategicCapacitySlot.capacity_total),
            func.sum(StrategicCapacitySlot.capacity_used),
        ).filter(
            StrategicCapacitySlot.tenant_id == self.tenant_id,
            StrategicCapacitySlot.campaign_id == campaign_id,
            StrategicCapacitySlot.starts_at >= start_dt,
            StrategicCapacitySlot.starts_at < end_dt,
        ).one()
        slot_count = int(slot_row[0] or 0)
        capacity_total = int(slot_row[1] or 0)
        capacity_used = int(slot_row[2] or 0)

        reservation_rows = self.db.query(
            StrategicReservation.status,
            func.count(StrategicReservation.id),
            func.sum(StrategicReservation.quantity),
            func.sum(StrategicReservation.amount_total),
            func.sum(StrategicReservation.amount_paid),
        ).filter(
            StrategicReservation.tenant_id == self.tenant_id,
            StrategicReservation.campaign_id == campaign_id,
            StrategicReservation.created_at >= start_dt,
            StrategicReservation.created_at < end_dt,
        ).group_by(StrategicReservation.status).all()
        reservations_by_status = {str(row[0]): int(row[1] or 0) for row in reservation_rows}
        active_rows = [row for row in reservation_rows if str(row[0]) in self.ACTIVE_RESERVATION_STATUSES]

        pizzas_sold = 0
        if order_ids:
            pizzas_sold = int(self.db.query(func.coalesce(func.sum(OrderItem.quantity), 0)).join(
                Product, (Product.id == OrderItem.product_id) & (Product.tenant_id == self.tenant_id)
            ).filter(
                OrderItem.tenant_id == self.tenant_id,
                OrderItem.order_id.in_(order_ids),
                OrderItem.superseded_at.is_(None),
                Product.product_type == "pizza",
            ).scalar() or 0)

        return {
            "slot_count": slot_count,
            "capacity_total": capacity_total if slot_count else None,
            "capacity_used": capacity_used if slot_count else None,
            "capacity_available": capacity_total - capacity_used if slot_count else None,
            "capacity_utilization_rate": round(capacity_used / capacity_total * 100, 2) if capacity_total else None,
            "reservations_by_status": reservations_by_status,
            "active_reservations": sum(int(row[1] or 0) for row in active_rows),
            "reserved_quantity": sum(int(row[2] or 0) for row in active_rows),
            "reserved_value": round(sum(float(row[3] or 0) for row in active_rows), 2),
            "prepaid_value": round(sum(float(row[4] or 0) for row in active_rows), 2),
            "pizzas_sold": pizzas_sold,
        }

    @staticmethod
    def _definitions() -> dict:
        return {
            "paid_orders": "Pedidos da campanha com pagamento approved/paid, sem arquivados, cancelados ou estornados.",
            "revenue": "Soma de orders.total dos pedidos pagos atribuídos por strategic_campaign_id.",
            "conversion_rate": "paid_orders / sessões únicas internas * 100.",
            "roas": "receita atribuída / gasto real sincronizado em ad_daily_metrics.",
            "cmv": "Soma dos snapshots canônicos de CMV; indisponível se faltar receita, ficha ou custo em qualquer pedido pago.",
            "result": "receita atribuída - CMV - gasto real de mídia.",
            "roi": "resultado / (CMV + gasto real de mídia) * 100; somente com custos completos.",
            "capacity": "Soma dos slots cujo início pertence ao período selecionado.",
            "reservations": "Reservas criadas no período; valores ativos consideram held e confirmed.",
            "pizzas_sold": "Soma das quantidades de itens ativos cujo produto canônico tem product_type=pizza.",
        }

    @staticmethod
    def _ratio(numerator: float | int | None, denominator: float | int | None) -> float | None:
        if numerator is None or denominator is None or denominator <= 0:
            return None
        return round(float(numerator) / float(denominator), 4)

    @classmethod
    def _ratio_percent(cls, numerator: float | int | None, denominator: float | int | None) -> float | None:
        ratio = cls._ratio(numerator, denominator)
        return round(ratio * 100, 2) if ratio is not None else None

    @staticmethod
    def _optional_money(value) -> float | None:
        if value is None:
            return None
        try:
            parsed = Decimal(str(value))
            if not parsed.is_finite() or parsed < 0:
                return None
            return round(float(parsed), 2)
        except (InvalidOperation, TypeError, ValueError):
            return None

    @staticmethod
    def _metadata(raw: str | None) -> dict:
        if not raw:
            return {}
        try:
            value = json.loads(raw)
            return value if isinstance(value, dict) else {}
        except (TypeError, ValueError):
            return {}
