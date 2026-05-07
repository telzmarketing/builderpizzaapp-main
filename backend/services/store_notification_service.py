from __future__ import annotations

import json
import random
import re
import uuid
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session, joinedload, selectinload

from backend.models.customer import Address
from backend.models.order import Order, OrderItem, OrderStatus
from backend.models.payment import Payment, PaymentStatus
from backend.models.product import Product
from backend.models.store_notification import (
    StoreNotification,
    StoreNotificationDay,
    StoreNotificationImpression,
    StoreNotificationSettings,
)
from backend.schemas.store_notification import (
    StoreNotificationCreate,
    StoreNotificationPreviewIn,
    StoreNotificationSettingsIn,
    StoreNotificationUpdate,
)
from backend.services.store_operation_service import StoreOperationService


ALLOWED_PAGES = {"home", "cardapio", "product", "cart"}
DEFAULT_TEMPLATE = "{nome}, {bairro}, comprou {produto} - {tempo}"
PAID_ORDER_STATUSES = {
    OrderStatus.paid,
    OrderStatus.pago,
    OrderStatus.preparing,
    OrderStatus.ready_for_pickup,
    OrderStatus.on_the_way,
    OrderStatus.delivered,
}
PAID_PAYMENT_STATUSES = {PaymentStatus.approved, PaymentStatus.paid}
PRIORITY_SCORE = {"low": 1, "medium": 2, "high": 3}


class StoreNotificationService:
    def __init__(self, db: Session):
        self._db = db

    def get_settings(self) -> StoreNotificationSettings:
        settings = (
            self._db.query(StoreNotificationSettings)
            .filter(StoreNotificationSettings.id == "default")
            .first()
        )
        if settings:
            return settings
        settings = StoreNotificationSettings(id="default")
        self._db.add(settings)
        self._db.commit()
        self._db.refresh(settings)
        return settings

    def update_settings(self, payload: StoreNotificationSettingsIn) -> StoreNotificationSettings:
        settings = self.get_settings()
        values = payload.model_dump()
        for key, value in values.items():
            if key == "allowed_pages":
                value = json.dumps(value)
            setattr(settings, key, value)
        settings.updated_at = datetime.now(timezone.utc)
        self._db.commit()
        self._db.refresh(settings)
        return settings

    def list_notifications(self) -> list[dict]:
        notifications = (
            self._db.query(StoreNotification)
            .options(selectinload(StoreNotification.days), joinedload(StoreNotification.product))
            .order_by(StoreNotification.created_at.desc())
            .all()
        )
        return [self.serialize_notification(item) for item in notifications]

    def summary(self) -> dict:
        active = (
            self._db.query(func.count(StoreNotification.id))
            .filter(StoreNotification.status == "active")
            .scalar()
            or 0
        )
        manual = (
            self._db.query(func.count(StoreNotification.id))
            .filter(StoreNotification.type.in_(["manual", "fomento"]))
            .scalar()
            or 0
        )
        real_impressions = (
            self._db.query(func.count(StoreNotificationImpression.id))
            .filter(StoreNotificationImpression.source_type == "real")
            .scalar()
            or 0
        )
        total_impressions = self._db.query(func.count(StoreNotificationImpression.id)).scalar() or 0
        return {
            "active_notifications": active,
            "manual_notifications": manual,
            "real_impressions": real_impressions,
            "total_impressions": total_impressions,
        }

    def create_notification(self, payload: StoreNotificationCreate) -> StoreNotification:
        self._ensure_product(payload.product_id)
        values = payload.model_dump(exclude={"weekdays"})
        notification = StoreNotification(id=f"sn-{uuid.uuid4().hex[:10]}", **values)
        self._db.add(notification)
        self._replace_days(notification, payload.weekdays)
        self._db.commit()
        self._db.refresh(notification)
        return notification

    def update_notification(self, notification_id: str, payload: StoreNotificationUpdate) -> StoreNotification:
        notification = self._notification(notification_id)
        values = payload.model_dump(exclude_unset=True, exclude={"weekdays"})
        if "product_id" in values and values["product_id"]:
            self._ensure_product(values["product_id"])
        for key, value in values.items():
            setattr(notification, key, value)
        if payload.weekdays is not None:
            self._replace_days(notification, payload.weekdays)
        notification.updated_at = datetime.now(timezone.utc)
        self._db.commit()
        self._db.refresh(notification)
        return notification

    def duplicate_notification(self, notification_id: str) -> StoreNotification:
        notification = self._notification(notification_id)
        copy = StoreNotification(
            id=f"sn-{uuid.uuid4().hex[:10]}",
            type=notification.type,
            status="paused",
            internal_name=f"{notification.internal_name} - copia",
            display_name=notification.display_name,
            product_id=notification.product_id,
            neighborhood=notification.neighborhood,
            template_text=notification.template_text,
            priority=notification.priority,
            weight=notification.weight,
            display_seconds=notification.display_seconds,
            start_time=notification.start_time,
            end_time=notification.end_time,
            start_date=notification.start_date,
            end_date=notification.end_date,
        )
        self._db.add(copy)
        self._replace_days(copy, [day.weekday for day in notification.days])
        self._db.commit()
        self._db.refresh(copy)
        return copy

    def set_status(self, notification_id: str, status: str) -> StoreNotification:
        if status not in {"active", "paused"}:
            raise ValueError("Status invalido.")
        notification = self._notification(notification_id)
        notification.status = status
        notification.updated_at = datetime.now(timezone.utc)
        self._db.commit()
        self._db.refresh(notification)
        return notification

    def delete_notification(self, notification_id: str) -> None:
        notification = self._notification(notification_id)
        self._db.delete(notification)
        self._db.commit()

    def preview(self, payload: StoreNotificationPreviewIn) -> dict:
        product_name = self._safe_text(payload.product_name) or "Produto"
        message = self._render_template(
            payload.template_text,
            name=self._first_name(payload.display_name),
            product=product_name,
            neighborhood=self._safe_text(payload.neighborhood),
            relative_time=payload.relative_time,
        )
        return {"message": message}

    def next_notification(self, page: str = "home") -> dict:
        settings = self.get_settings()
        next_delay = self._next_delay(settings)
        page = self._normalize_page(page)

        if not settings.enabled or page not in self._settings_pages(settings):
            return {"notification": None, "next_delay_seconds": next_delay}

        now_utc = datetime.now(timezone.utc)
        if self._has_recent_impression(settings, now_utc):
            return {"notification": None, "next_delay_seconds": next_delay}

        if settings.only_during_store_hours:
            try:
                if not StoreOperationService(self._db).get_status()["is_open"]:
                    return {"notification": None, "next_delay_seconds": next_delay}
            except Exception:
                return {"notification": None, "next_delay_seconds": next_delay}

        last = self._last_impression()
        real_candidates = self._real_candidates(settings, last) if settings.real_orders_enabled else []
        manual_candidates = self._manual_candidates(settings, last)

        selected = self._select_candidate(settings, real_candidates, manual_candidates)
        if selected is None:
            return {"notification": None, "next_delay_seconds": next_delay}

        source_type, payload = selected
        impression = StoreNotificationImpression(
            id=f"sni-{uuid.uuid4().hex[:12]}",
            notification_id=payload.get("notification_id"),
            source_type=source_type,
            order_id=payload.get("order_id"),
            product_id=payload.get("product_id"),
            neighborhood=payload.get("neighborhood"),
            page=page,
            displayed_at=now_utc,
        )
        self._db.add(impression)
        self._db.commit()

        return {"notification": payload, "next_delay_seconds": next_delay}

    def serialize_settings(self, settings: StoreNotificationSettings) -> dict:
        return {
            "id": settings.id,
            "enabled": bool(settings.enabled),
            "real_orders_enabled": bool(settings.real_orders_enabled),
            "real_percentage": settings.real_percentage,
            "manual_percentage": settings.manual_percentage,
            "min_delay_seconds": settings.min_delay_seconds,
            "max_delay_seconds": settings.max_delay_seconds,
            "default_display_seconds": settings.default_display_seconds,
            "prevent_same_product_sequence": bool(settings.prevent_same_product_sequence),
            "prevent_same_neighborhood_sequence": bool(settings.prevent_same_neighborhood_sequence),
            "only_during_store_hours": bool(settings.only_during_store_hours),
            "allowed_pages": self._settings_pages(settings),
            "created_at": settings.created_at,
            "updated_at": settings.updated_at,
        }

    def serialize_notification(self, notification: StoreNotification) -> dict:
        last_displayed_at = (
            self._db.query(func.max(StoreNotificationImpression.displayed_at))
            .filter(StoreNotificationImpression.notification_id == notification.id)
            .scalar()
        )
        impressions_count = (
            self._db.query(func.count(StoreNotificationImpression.id))
            .filter(StoreNotificationImpression.notification_id == notification.id)
            .scalar()
            or 0
        )
        return {
            "id": notification.id,
            "type": notification.type,
            "status": notification.status,
            "internal_name": notification.internal_name,
            "display_name": notification.display_name,
            "product_id": notification.product_id,
            "product_name": notification.product.name if notification.product else None,
            "product_icon": notification.product.icon if notification.product else None,
            "neighborhood": notification.neighborhood,
            "template_text": notification.template_text,
            "priority": notification.priority,
            "weight": notification.weight,
            "display_seconds": notification.display_seconds,
            "start_time": notification.start_time,
            "end_time": notification.end_time,
            "start_date": notification.start_date,
            "end_date": notification.end_date,
            "weekdays": [day.weekday for day in notification.days],
            "impressions_count": impressions_count,
            "last_displayed_at": last_displayed_at,
            "created_at": notification.created_at,
            "updated_at": notification.updated_at,
        }

    def _manual_candidates(self, settings: StoreNotificationSettings, last: StoreNotificationImpression | None) -> list[dict]:
        current = self._local_now()
        notifications = (
            self._db.query(StoreNotification)
            .options(selectinload(StoreNotification.days), joinedload(StoreNotification.product))
            .filter(StoreNotification.status == "active")
            .filter(StoreNotification.type.in_(["manual", "fomento"]))
            .all()
        )
        candidates = []
        for item in notifications:
            if not self._manual_is_eligible(item, current):
                continue
            if not self._passes_sequence_rules(settings, last, item.product_id, item.neighborhood):
                continue
            product_name = self._product_display_name(item.product, "Produto")
            candidates.append({
                "source_type": "manual",
                "notification_id": item.id,
                "product_id": item.product_id,
                "product_name": product_name,
                "product_image": item.product.icon if item.product else None,
                "neighborhood": self._safe_text(item.neighborhood),
                "message": self._render_template(
                    item.template_text,
                    name=self._first_name(item.display_name),
                    product=product_name,
                    neighborhood=self._safe_text(item.neighborhood),
                    relative_time="2min",
                ),
                "display_seconds": item.display_seconds or settings.default_display_seconds,
                "_score": max(1, item.weight or 1) * PRIORITY_SCORE.get(item.priority, 2),
            })
        return candidates

    def _real_candidates(self, settings: StoreNotificationSettings, last: StoreNotificationImpression | None) -> list[dict]:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=72)
        orders = (
            self._db.query(Order)
            .options(
                joinedload(Order.customer),
                joinedload(Order.address),
                joinedload(Order.payment),
                selectinload(Order.items).selectinload(OrderItem.flavors),
            )
            .outerjoin(Payment, Payment.order_id == Order.id)
            .filter(Order.created_at >= cutoff)
            .filter(
                or_(
                    Order.status.in_(list(PAID_ORDER_STATUSES)),
                    Order.paid_at.is_not(None),
                    Payment.status.in_(list(PAID_PAYMENT_STATUSES)),
                )
            )
            .filter(~Order.status.in_([OrderStatus.cancelled, OrderStatus.refunded]))
            .order_by(Order.created_at.desc())
            .limit(40)
            .all()
        )
        product_lookup = self._product_lookup(orders)
        candidates = []
        for order in orders:
            product_id, product_name, product_image = self._main_product(order, product_lookup)
            if not product_id or not product_name:
                continue
            neighborhood = self._order_neighborhood(order)
            if not self._passes_sequence_rules(settings, last, product_id, neighborhood):
                continue
            name = self._first_name(order.customer.name if order.customer else order.delivery_name)
            relative = self._relative_time(order.paid_at or order.created_at)
            candidates.append({
                "source_type": "real",
                "notification_id": None,
                "order_id": order.id,
                "product_id": product_id,
                "product_name": product_name,
                "product_image": product_image,
                "neighborhood": neighborhood,
                "message": self._render_template(
                    DEFAULT_TEMPLATE,
                    name=name,
                    product=product_name,
                    neighborhood=neighborhood,
                    relative_time=relative,
                ),
                "display_seconds": settings.default_display_seconds,
                "_score": 1,
            })
        return candidates

    def _select_candidate(self, settings, real_candidates: list[dict], manual_candidates: list[dict]):
        if real_candidates and not manual_candidates:
            return "real", real_candidates[0]
        if manual_candidates and not real_candidates:
            return "manual", self._weighted_manual(manual_candidates)
        if not real_candidates and not manual_candidates:
            return None

        real_percentage = max(0, min(100, settings.real_percentage or 0))
        manual_percentage = max(0, min(100, settings.manual_percentage or 0))
        total = real_percentage + manual_percentage
        if total <= 0:
            return "real", real_candidates[0]
        pick_real = random.randint(1, total) <= real_percentage
        if pick_real:
            return "real", real_candidates[0]
        return "manual", self._weighted_manual(manual_candidates)

    def _weighted_manual(self, candidates: list[dict]) -> dict:
        total = sum(item["_score"] for item in candidates)
        cursor = random.randint(1, max(1, total))
        running = 0
        for item in sorted(candidates, key=lambda candidate: candidate["_score"], reverse=True):
            running += item["_score"]
            if cursor <= running:
                item.pop("_score", None)
                return item
        candidates[0].pop("_score", None)
        return candidates[0]

    def _manual_is_eligible(self, notification: StoreNotification, current: datetime) -> bool:
        if current.weekday() not in [day.weekday for day in notification.days]:
            return False
        today = current.date()
        if notification.start_date and notification.start_date > today:
            return False
        if notification.end_date and notification.end_date < today:
            return False
        now_time = current.time()
        if notification.start_time <= notification.end_time:
            return notification.start_time <= now_time <= notification.end_time
        return now_time >= notification.start_time or now_time <= notification.end_time

    def _passes_sequence_rules(
        self,
        settings: StoreNotificationSettings,
        last: StoreNotificationImpression | None,
        product_id: str | None,
        neighborhood: str | None,
    ) -> bool:
        if not last:
            return True
        if settings.prevent_same_product_sequence and product_id and last.product_id == product_id:
            return False
        if (
            settings.prevent_same_neighborhood_sequence
            and neighborhood
            and last.neighborhood
            and last.neighborhood.lower() == neighborhood.lower()
        ):
            return False
        return True

    def _has_recent_impression(self, settings: StoreNotificationSettings, now: datetime) -> bool:
        since = now - timedelta(seconds=max(5, settings.min_delay_seconds or 45))
        return (
            self._db.query(StoreNotificationImpression.id)
            .filter(StoreNotificationImpression.displayed_at >= since)
            .first()
            is not None
        )

    def _last_impression(self) -> StoreNotificationImpression | None:
        return (
            self._db.query(StoreNotificationImpression)
            .order_by(StoreNotificationImpression.displayed_at.desc())
            .first()
        )

    def _replace_days(self, notification: StoreNotification, weekdays: list[int]) -> None:
        if notification.id:
            self._db.query(StoreNotificationDay).filter(
                StoreNotificationDay.notification_id == notification.id
            ).delete(synchronize_session=False)
        for weekday in sorted(set(weekdays)):
            self._db.add(StoreNotificationDay(
                id=f"snd-{uuid.uuid4().hex[:10]}",
                notification_id=notification.id,
                weekday=weekday,
            ))

    def _notification(self, notification_id: str) -> StoreNotification:
        notification = (
            self._db.query(StoreNotification)
            .options(selectinload(StoreNotification.days), joinedload(StoreNotification.product))
            .filter(StoreNotification.id == notification_id)
            .first()
        )
        if not notification:
            raise LookupError("Notificacao nao encontrada.")
        return notification

    def _ensure_product(self, product_id: str) -> None:
        exists = self._db.query(Product.id).filter(Product.id == product_id).first()
        if not exists:
            raise LookupError("Produto vinculado nao encontrado.")

    def _settings_pages(self, settings: StoreNotificationSettings) -> list[str]:
        try:
            pages = json.loads(settings.allowed_pages or "[]")
        except Exception:
            pages = []
        clean = [page for page in pages if page in ALLOWED_PAGES]
        return clean or ["home", "cardapio", "product", "cart"]

    def _normalize_page(self, page: str) -> str:
        page = (page or "home").strip().lower()
        aliases = {
            "/": "home",
            "catalog": "cardapio",
            "cardápio": "cardapio",
            "produto": "product",
            "carrinho": "cart",
        }
        return aliases.get(page, page if page in ALLOWED_PAGES else "home")

    def _next_delay(self, settings: StoreNotificationSettings) -> int:
        min_delay = max(5, settings.min_delay_seconds or 45)
        max_delay = max(min_delay, settings.max_delay_seconds or min_delay)
        return random.randint(min_delay, max_delay)

    def _local_now(self) -> datetime:
        return datetime.now(ZoneInfo("America/Sao_Paulo"))

    def _product_lookup(self, orders: list[Order]) -> dict[str, Product]:
        product_ids: set[str] = set()
        for order in orders:
            for item in order.items:
                product_ids.add(item.product_id)
                for flavor in item.flavors:
                    product_ids.add(flavor.product_id)
        if not product_ids:
            return {}
        products = self._db.query(Product).filter(Product.id.in_(product_ids)).all()
        return {product.id: product for product in products}

    def _main_product(self, order: Order, product_lookup: dict[str, Product]) -> tuple[str | None, str | None, str | None]:
        if not order.items:
            return None, None, None
        item = sorted(order.items, key=lambda candidate: candidate.total_price or 0, reverse=True)[0]
        if item.flavors:
            flavor = sorted(item.flavors, key=lambda candidate: candidate.position or 0)[0]
            product = product_lookup.get(flavor.product_id)
            return flavor.product_id, self._product_display_name(product, flavor.flavor_name), product.icon if product else None
        product = product_lookup.get(item.product_id)
        return item.product_id, self._product_display_name(product, product.name if product else None), product.icon if product else None

    def _order_neighborhood(self, order: Order) -> str | None:
        if order.address and order.address.neighborhood:
            return self._safe_text(order.address.neighborhood)
        if order.customer_id:
            address = (
                self._db.query(Address)
                .filter(Address.customer_id == order.customer_id)
                .order_by(Address.is_default.desc(), Address.created_at.desc())
                .first()
            )
            if address and address.neighborhood:
                return self._safe_text(address.neighborhood)
        return None

    def _render_template(self, template: str, *, name: str, product: str, neighborhood: str | None, relative_time: str) -> str:
        template = template or DEFAULT_TEMPLATE
        if not neighborhood:
            template = re.sub(r",?\s*\{bairro\},?", "", template, flags=re.IGNORECASE)
            template = re.sub(r",?\s*do bairro\s*\{bairro\},?", "", template, flags=re.IGNORECASE)
            template = re.sub(r",?\s*do\s+\{bairro\},?", "", template, flags=re.IGNORECASE)
        rendered = (
            template.replace("{nome}", name or "Cliente")
            .replace("{produto}", product or "um produto")
            .replace("{bairro}", neighborhood or "")
            .replace("{tempo}", relative_time or "2min")
        )
        rendered = re.sub(r",\s*do bairro\s+", ", ", rendered, flags=re.IGNORECASE)
        rendered = re.sub(r"\bdo bairro\s+", "", rendered, flags=re.IGNORECASE)
        rendered = re.sub(r"\bpediu\b", "comprou", rendered, flags=re.IGNORECASE)
        rendered = re.sub(r"\s+h[aá]\s+(agora|\d+\s*min|\d+\s*h)", r" - \1", rendered, flags=re.IGNORECASE)
        rendered = re.sub(r"\s+h[aá]\s+alguns minutos", " - alguns min", rendered, flags=re.IGNORECASE)
        rendered = re.sub(r"\s+-\s+h[aá]\s+", " - ", rendered, flags=re.IGNORECASE)
        rendered = re.sub(r"\s+", " ", rendered).strip(" ,")
        return rendered

    def _product_display_name(self, product: Product | None, fallback: str | None) -> str | None:
        name = self._safe_text(product.name if product else fallback)
        if not name:
            return None
        if name.lower().startswith("pizza"):
            return name
        product_type = (product.product_type or "").lower() if product else ""
        category = " ".join(filter(None, [product.category, product.subcategory])).lower() if product else ""
        if product_type == "pizza" or "pizza" in category:
            return f"Pizza de {name}"
        return name

    def _first_name(self, value: str | None) -> str:
        clean = self._safe_text(value)
        if not clean:
            return "Cliente"
        return clean.split()[0][:40]

    def _safe_text(self, value: str | None) -> str | None:
        if not value:
            return None
        clean = re.sub(r"[\r\n\t]+", " ", str(value)).strip()
        clean = re.sub(r"\s+", " ", clean)
        return clean[:120] or None

    def _relative_time(self, value: datetime | None) -> str:
        if not value:
            return "2min"
        current = datetime.now(timezone.utc)
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        minutes = max(1, int((current - value.astimezone(timezone.utc)).total_seconds() // 60))
        if minutes <= 1:
            return "1min"
        if minutes < 60:
            return f"{minutes}min"
        hours = min(23, minutes // 60)
        return f"{hours}h"
