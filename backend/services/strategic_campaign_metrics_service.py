from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.models.order import Order, OrderStatus
from backend.models.paid_traffic import AdDailyMetric
from backend.models.payment import Payment, PaymentStatus
from backend.models.strategic_campaign import StrategicCampaign
from backend.routes.marketing import VisitorEvent


class StrategicCampaignMetricsService:
    EVENT_TYPES = {
        "views": {"strategic_campaign_view"},
        "offer_clicks": {"strategic_campaign_offer_click"},
        "offer_scrolls": {"strategic_campaign_scroll_to_offers"},
        "checkout_starts": {"checkout_started", "checkout_start", "InitiateCheckout"},
    }

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

        events = self.db.query(VisitorEvent.event_type, VisitorEvent.session_id, VisitorEvent.metadata_json).filter(
            VisitorEvent.tenant_id == self.tenant_id,
            VisitorEvent.created_at >= start_dt,
            VisitorEvent.created_at < end_dt,
            VisitorEvent.event_type.in_(tuple(event for values in self.EVENT_TYPES.values() for event in values)),
        ).all()
        counts = {key: 0 for key in self.EVENT_TYPES}
        session_ids: set[str] = set()
        for event_type, session_id, metadata_json in events:
            metadata = self._metadata(metadata_json)
            if str(metadata.get("campaign_id") or "") != campaign_id:
                continue
            for key, allowed in self.EVENT_TYPES.items():
                if event_type in allowed:
                    counts[key] += 1
            if session_id:
                session_ids.add(session_id)

        paid_orders_query = self.db.query(Order).join(Payment, Payment.order_id == Order.id).filter(
            Order.tenant_id == self.tenant_id,
            Order.strategic_campaign_id == campaign_id,
            Order.created_at >= start_dt,
            Order.created_at < end_dt,
            Order.archived_at.is_(None),
            Order.status.notin_((OrderStatus.cancelled, OrderStatus.refunded)),
            Payment.tenant_id == self.tenant_id,
            Payment.status.in_((PaymentStatus.approved, PaymentStatus.paid)),
        )
        paid_orders = paid_orders_query.count()
        revenue = float(paid_orders_query.with_entities(func.coalesce(func.sum(Order.total), 0)).scalar() or 0)

        config = campaign.marketing_config or {}
        planned_budget = config.get("planned_budget")
        traffic_campaign_id = config.get("traffic_campaign_id")
        spend = None
        if traffic_campaign_id:
            spend = float(self.db.query(func.coalesce(func.sum(AdDailyMetric.spend), 0)).filter(
                AdDailyMetric.tenant_id == self.tenant_id,
                AdDailyMetric.traffic_campaign_id == traffic_campaign_id,
                AdDailyMetric.metric_date >= start_date,
                AdDailyMetric.metric_date <= end_date,
            ).scalar() or 0)

        return {
            "campaign_id": campaign.id,
            "campaign_name": campaign.name,
            "period": {"date_from": start_date.isoformat(), "date_to": end_date.isoformat()},
            "funnel": {**counts, "sessions": len(session_ids), "paid_orders": paid_orders},
            "revenue": round(revenue, 2),
            "planned_budget": float(Decimal(str(planned_budget))) if planned_budget is not None else None,
            "spend": round(spend, 2) if spend is not None else None,
            "roas": round(revenue / spend, 4) if spend and spend > 0 else None,
            "conversion_rate": round(paid_orders / len(session_ids) * 100, 2) if session_ids else None,
            "attribution": {
                "source": "strategic_campaign_id_on_order",
                "spend_source": "ad_daily_metrics" if traffic_campaign_id else None,
                "warning": None if traffic_campaign_id else "Gasto de mídia não configurado; ROAS e ROI não calculados.",
            },
        }

    @staticmethod
    def _metadata(raw: str | None) -> dict:
        if not raw:
            return {}
        try:
            value = json.loads(raw)
            return value if isinstance(value, dict) else {}
        except (TypeError, ValueError):
            return {}
