"""
UpsellEngine — engine isolada de upsell.

Responsabilidades:
- Analisar o carrinho atual (itens, categorias, total, quantidade)
- Verificar regras de gatilho de cada upsell ativo
- Retornar lista ordenada de upsells elegíveis
- Registrar eventos (view, accept, reject) e atualizar métricas

NÃO altera nenhuma lógica de pedido, pagamento, cupom ou frete.
"""
from datetime import datetime, timezone
from typing import Sequence
import uuid

from sqlalchemy.orm import Session

from backend.models.upsell import Upsell, UpsellEvent, UpsellMetric, OrderUpsell
from backend.schemas.upsell import UpsellCartItemIn, UpsellEventIn, UpsellOut, UpsellProductOut, UpsellProductSizeOut


def _serialize_product(product) -> UpsellProductOut | None:
    if product is None:
        return None
    sizes = []
    for s in (product.sizes or []):
        if s.active:
            sizes.append(UpsellProductSizeOut(
                id=s.id,
                label=s.label,
                price=s.price,
                is_default=s.is_default,
                active=s.active,
                sort_order=s.sort_order,
            ))
    sizes.sort(key=lambda s: s.sort_order)
    return UpsellProductOut(
        id=product.id,
        name=product.name,
        description=product.description or "",
        price=product.price,
        icon=product.icon or "",
        category=product.category,
        product_type=getattr(product, "product_type", None),
        active=product.active,
        sizes=sizes,
    )


def _serialize_upsell(row: Upsell) -> UpsellOut:
    from backend.schemas.upsell import UpsellMetricOut
    metrics_out = None
    if row.metrics:
        metrics_out = UpsellMetricOut(
            id=row.metrics.id,
            upsell_id=row.metrics.upsell_id,
            views=row.metrics.views,
            accepts=row.metrics.accepts,
            rejects=row.metrics.rejects,
            revenue=row.metrics.revenue,
            updated_at=row.metrics.updated_at,
        )
    return UpsellOut(
        id=row.id,
        internal_name=row.internal_name,
        product_id=row.product_id,
        image_url=row.image_url,
        main_text=row.main_text,
        secondary_text=row.secondary_text,
        promotional_price=row.promotional_price,
        trigger_type=row.trigger_type,
        trigger_product_id=row.trigger_product_id,
        trigger_category=row.trigger_category,
        trigger_min_value=row.trigger_min_value,
        trigger_min_quantity=row.trigger_min_quantity,
        allowed_weekdays=row.allowed_weekdays,
        start_time=row.start_time,
        end_time=row.end_time,
        priority=row.priority,
        display_limit=row.display_limit,
        active=row.active,
        created_at=row.created_at,
        updated_at=row.updated_at,
        product=_serialize_product(row.product),
        trigger_product=_serialize_product(row.trigger_product),
        metrics=metrics_out,
    )


def _ensure_metrics(db: Session, upsell_id: str) -> UpsellMetric:
    metric = db.query(UpsellMetric).filter(UpsellMetric.upsell_id == upsell_id).first()
    if metric is None:
        metric = UpsellMetric(id=str(uuid.uuid4()), upsell_id=upsell_id)
        db.add(metric)
        db.flush()
    return metric


def _time_in_range(now_str: str, start: str | None, end: str | None) -> bool:
    if start is None or end is None:
        return True
    return start <= now_str <= end


def _weekday_allowed(weekday: int, allowed: str | None) -> bool:
    if not allowed:
        return True
    return str(weekday) in allowed


class UpsellEngine:
    def __init__(self, db: Session):
        self._db = db

    def get_eligible(
        self,
        cart_items: list[UpsellCartItemIn],
        cart_total: float,
    ) -> list[UpsellOut]:
        now = datetime.now(timezone.utc)
        # weekday: 0=Mon … 6=Sun  → store as "0"=Mon "6"=Sun
        weekday = now.weekday()
        now_time = now.strftime("%H:%M")

        cart_product_ids = {item.product_id for item in cart_items}
        cart_categories = {item.category for item in cart_items if item.category}
        cart_quantity = sum(item.quantity for item in cart_items)

        rows: Sequence[Upsell] = (
            self._db.query(Upsell)
            .filter(Upsell.active.is_(True))
            .order_by(Upsell.priority.desc(), Upsell.created_at.asc())
            .all()
        )

        eligible: list[UpsellOut] = []

        for row in rows:
            # ── Time/weekday gate ─────────────────────────────────────────────
            if not _weekday_allowed(weekday, row.allowed_weekdays):
                continue
            if not _time_in_range(now_time, row.start_time, row.end_time):
                continue

            # ── Product availability ──────────────────────────────────────────
            if row.product is None or not row.product.active:
                continue

            # ── Don't upsell a product already in cart ────────────────────────
            if row.product_id in cart_product_ids:
                continue

            # ── Trigger evaluation ────────────────────────────────────────────
            triggered = False
            t = row.trigger_type

            if t == "min_value":
                triggered = cart_total >= (row.trigger_min_value or 0)

            elif t == "min_quantity":
                triggered = cart_quantity >= (row.trigger_min_quantity or 1)

            elif t == "product_in_cart":
                triggered = (row.trigger_product_id is not None) and (row.trigger_product_id in cart_product_ids)

            elif t == "category":
                triggered = (row.trigger_category is not None) and (row.trigger_category in cart_categories)

            if not triggered:
                continue

            eligible.append(_serialize_upsell(row))

            if len(eligible) >= (row.display_limit or 1):
                # respect per-upsell display_limit — aggregate limit handled client-side
                pass

        return eligible

    # ── Admin CRUD ────────────────────────────────────────────────────────────

    def list_upsells(self) -> list[UpsellOut]:
        rows = (
            self._db.query(Upsell)
            .order_by(Upsell.priority.desc(), Upsell.created_at.desc())
            .all()
        )
        return [_serialize_upsell(r) for r in rows]

    def get_upsell(self, upsell_id: str) -> UpsellOut | None:
        row = self._db.query(Upsell).filter(Upsell.id == upsell_id).first()
        if row is None:
            return None
        return _serialize_upsell(row)

    def create_upsell(self, data) -> UpsellOut:
        row = Upsell(
            id=str(uuid.uuid4()),
            **data.model_dump(exclude_none=False),
        )
        self._db.add(row)
        # create metrics row eagerly
        self._db.flush()
        _ensure_metrics(self._db, row.id)
        self._db.commit()
        self._db.refresh(row)
        return _serialize_upsell(row)

    def update_upsell(self, upsell_id: str, data) -> UpsellOut | None:
        row = self._db.query(Upsell).filter(Upsell.id == upsell_id).first()
        if row is None:
            return None
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(row, field, value)
        row.updated_at = datetime.now(timezone.utc)
        self._db.commit()
        self._db.refresh(row)
        return _serialize_upsell(row)

    def toggle_upsell(self, upsell_id: str) -> UpsellOut | None:
        row = self._db.query(Upsell).filter(Upsell.id == upsell_id).first()
        if row is None:
            return None
        row.active = not row.active
        row.updated_at = datetime.now(timezone.utc)
        self._db.commit()
        self._db.refresh(row)
        return _serialize_upsell(row)

    def delete_upsell(self, upsell_id: str) -> bool:
        row = self._db.query(Upsell).filter(Upsell.id == upsell_id).first()
        if row is None:
            return False
        self._db.delete(row)
        self._db.commit()
        return True

    def reorder(self, ordered_ids: list[str]) -> None:
        for idx, uid in enumerate(ordered_ids):
            row = self._db.query(Upsell).filter(Upsell.id == uid).first()
            if row:
                row.priority = len(ordered_ids) - idx
        self._db.commit()

    # ── Events & metrics ──────────────────────────────────────────────────────

    def log_event(self, data: UpsellEventIn) -> None:
        event = UpsellEvent(
            id=str(uuid.uuid4()),
            upsell_id=data.upsell_id,
            order_id=data.order_id,
            session_id=data.session_id,
            event_type=data.event_type,
            revenue=data.revenue,
        )
        self._db.add(event)

        metric = _ensure_metrics(self._db, data.upsell_id)
        if data.event_type == "viewed":
            metric.views = (metric.views or 0) + 1
        elif data.event_type == "accepted":
            metric.accepts = (metric.accepts or 0) + 1
            metric.revenue = (metric.revenue or 0.0) + data.revenue
        elif data.event_type == "rejected":
            metric.rejects = (metric.rejects or 0) + 1

        self._db.commit()

    def metrics_summary(self):
        from backend.schemas.upsell import UpsellMetricsSummary, UpsellMetricsSummaryItem
        rows = (
            self._db.query(Upsell)
            .order_by(Upsell.priority.desc())
            .all()
        )
        items = []
        total_views = total_accepts = total_rejects = 0
        total_revenue = 0.0
        for row in rows:
            m = row.metrics
            views = m.views if m else 0
            accepts = m.accepts if m else 0
            rejects = m.rejects if m else 0
            revenue = m.revenue if m else 0.0
            total_views += views
            total_accepts += accepts
            total_rejects += rejects
            total_revenue += revenue
            conv = round(accepts / views * 100, 1) if views > 0 else 0.0
            items.append(UpsellMetricsSummaryItem(
                upsell_id=row.id,
                internal_name=row.internal_name,
                product_name=row.product.name if row.product else "—",
                views=views,
                accepts=accepts,
                rejects=rejects,
                revenue=revenue,
                conversion_rate=conv,
            ))
        return UpsellMetricsSummary(
            total_views=total_views,
            total_accepts=total_accepts,
            total_rejects=total_rejects,
            total_revenue=total_revenue,
            items=items,
        )
