from datetime import date, datetime, timedelta, timezone
from collections import defaultdict
import uuid
from sqlalchemy import func
from backend.core.exceptions import DomainError
from backend.models.order import Order, OrderItem, OrderStatus
from backend.models.pcp import PcpWeeklyPlan
from backend.models.product import Product


class PcpService:
    def __init__(self, db, actor):
        self.db, self.tenant_id, self.actor_id = db, actor.tenant_id, actor.user_id

    def _query(self, model):
        return self.db.query(model).filter(model.tenant_id == self.tenant_id)

    def _out(self, row):
        return {"id": row.id, "tenant_id": row.tenant_id, "week_start": row.week_start,
                "status": row.status, "source_window_start": row.source_window_start,
                "source_window_end": row.source_window_end, "suggestions": row.suggestions_json or [],
                "approved_by": row.approved_by, "approved_at": row.approved_at}

    def generate(self, body):
        source_end = body.week_start - timedelta(days=1)
        source_start = source_end - timedelta(weeks=body.source_weeks) + timedelta(days=1)
        rows = self._query(OrderItem).join(Order).filter(
            Order.created_at >= datetime.combine(source_start, datetime.min.time(), tzinfo=timezone.utc),
            Order.created_at < datetime.combine(source_end + timedelta(days=1), datetime.min.time(), tzinfo=timezone.utc),
            Order.status.in_((OrderStatus.delivered,)),
        ).all()
        counts = defaultdict(int)
        for row in rows:
            counts[row.product_id] += int(row.quantity or 0)
        suggestions = [{"product_id": product_id, "suggested_quantity": round(quantity / body.source_weeks, 2),
                        "source": "completed_orders", "approved": False} for product_id, quantity in sorted(counts.items())]
        plan = self._query(PcpWeeklyPlan).filter(PcpWeeklyPlan.week_start == body.week_start).with_for_update().first()
        if plan and plan.status == "approved":
            raise DomainError("Plano aprovado nao pode ser sobrescrito.", code="PcpPlanAlreadyApproved")
        if plan is None:
            plan = PcpWeeklyPlan(id=str(uuid.uuid4()), tenant_id=self.tenant_id, week_start=body.week_start,
                status="draft", source_window_start=source_start, source_window_end=source_end, suggestions_json=suggestions)
            self.db.add(plan)
        else:
            plan.source_window_start, plan.source_window_end, plan.suggestions_json = source_start, source_end, suggestions
        self.db.commit(); self.db.refresh(plan)
        return self._out(plan)

    def get(self, week_start):
        plan = self._query(PcpWeeklyPlan).filter(PcpWeeklyPlan.week_start == week_start).first()
        if not plan:
            raise DomainError("Previsao semanal nao encontrada.", code="PcpPlanNotFound")
        return self._out(plan)

    def approve(self, week_start, body):
        plan = self._query(PcpWeeklyPlan).filter(PcpWeeklyPlan.week_start == week_start).with_for_update().first()
        if not plan:
            raise DomainError("Previsao semanal nao encontrada.", code="PcpPlanNotFound")
        if plan.status != body.expected_status or plan.status != "draft":
            raise DomainError("Somente previsoes em rascunho podem ser aprovadas.", code="PcpPlanVersionConflict")
        plan.status, plan.approved_by, plan.approved_at = "approved", self.actor_id, datetime.now(timezone.utc)
        plan.suggestions_json = [{**row, "approved": True} for row in (plan.suggestions_json or [])]
        self.db.commit(); self.db.refresh(plan)
        return self._out(plan)
