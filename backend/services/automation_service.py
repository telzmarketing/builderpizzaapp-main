from __future__ import annotations

import os
import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session


PAID_STATUSES = {
    "paid",
    "pago",
    "preparing",
    "ready_for_pickup",
    "on_the_way",
    "delivered",
}

WEEKDAY_NAMES = ["segunda", "terca", "quarta", "quinta", "sexta", "sabado", "domingo"]
VARIABLE_RE = re.compile(r"\{([a-zA-Z0-9_]+)\}")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _scalar(db: Session, sql: str, params: dict[str, Any] | None = None) -> Any:
    return db.execute(text(sql), params or {}).scalar()


def _row_dict(row: Any) -> dict[str, Any]:
    if row is None:
        return {}
    return dict(row._mapping)


def _safe_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _safe_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _iso_date(value: Any) -> str:
    if not value:
        return ""
    if isinstance(value, datetime):
        return value.strftime("%d/%m/%Y")
    return str(value)


def _first_name(name: str | None) -> str:
    return (name or "").strip().split(" ")[0] if (name or "").strip() else ""


def load_automation(db: Session, automation_id: str) -> dict[str, Any]:
    row = db.execute(
        text(
            """
            SELECT
                id, name, trigger, trigger_value, trigger_delay_hours, channel,
                template_id, message_body, active, runs_total, last_run_at,
                COALESCE(description, '') AS description,
                COALESCE(conditions_json, '[]') AS conditions_json,
                COALESCE(actions_json, '[]') AS actions_json,
                COALESCE(frequency, 'once') AS frequency,
                COALESCE(max_sends_per_customer, 1) AS max_sends_per_customer,
                COALESCE(cooldown_hours, 24) AS cooldown_hours,
                daily_limit, allowed_start_time, allowed_end_time, allowed_weekdays,
                COALESCE(priority, 100) AS priority,
                coupon_id, product_id, group_id, segment_id
            FROM marketing_automations
            WHERE id = :automation_id
            """
        ),
        {"automation_id": automation_id},
    ).fetchone()
    if not row:
        raise HTTPException(404, "Automacao nao encontrada.")
    return _row_dict(row)


def get_eligible_customers(db: Session, automation: dict[str, Any]) -> list[dict[str, Any]]:
    trigger = automation["trigger"]
    trigger_value = automation.get("trigger_value")
    now = _now()
    rows: list[Any]

    if trigger in {"reactivation", "inactive_customer", "days_after_last_order"}:
        days = _safe_int(trigger_value, 30)
        cutoff = now - timedelta(days=days)
        rows = db.execute(
            text(
                """
                SELECT id, name, phone, email, marketing_whatsapp_consent, marketing_email_consent
                FROM customers
                WHERE last_order_at IS NOT NULL AND last_order_at <= :cutoff
                """
            ),
            {"cutoff": cutoff},
        ).fetchall()

    elif trigger in {"birthday", "birthday_week"}:
        if trigger == "birthday":
            rows = db.execute(
                text(
                    """
                    SELECT id, name, phone, email, marketing_whatsapp_consent, marketing_email_consent
                    FROM customers
                    WHERE birth_date IS NOT NULL
                      AND EXTRACT(MONTH FROM birth_date) = :month
                      AND EXTRACT(DAY FROM birth_date) = :day
                    """
                ),
                {"month": now.month, "day": now.day},
            ).fetchall()
        else:
            rows = db.execute(
                text(
                    """
                    SELECT id, name, phone, email, marketing_whatsapp_consent, marketing_email_consent
                    FROM customers
                    WHERE birth_date IS NOT NULL
                      AND TO_CHAR(birth_date, 'MM-DD') BETWEEN :start_key AND :end_key
                    """
                ),
                {
                    "start_key": now.strftime("%m-%d"),
                    "end_key": (now + timedelta(days=7)).strftime("%m-%d"),
                },
            ).fetchall()

    elif trigger == "first_order":
        rows = db.execute(
            text(
                """
                SELECT id, name, phone, email, marketing_whatsapp_consent, marketing_email_consent
                FROM customers
                WHERE total_orders = 1
                """
            )
        ).fetchall()

    elif trigger in {"new_customer", "registered_no_order"}:
        hours = _safe_int(trigger_value, 24)
        since = now - timedelta(hours=hours)
        comparator = "<=" if trigger == "registered_no_order" else ">="
        total_filter = "AND COALESCE(total_orders, 0) = 0" if trigger == "registered_no_order" else ""
        rows = db.execute(
            text(
                f"""
                SELECT id, name, phone, email, marketing_whatsapp_consent, marketing_email_consent
                FROM customers
                WHERE created_at {comparator} :since
                {total_filter}
                """
            ),
            {"since": since},
        ).fetchall()

    elif trigger == "abandoned_cart":
        minutes = _safe_int(trigger_value, 60)
        since = now - timedelta(minutes=minutes)
        rows = db.execute(
            text(
                """
                SELECT DISTINCT c.id, c.name, c.phone, c.email,
                       c.marketing_whatsapp_consent, c.marketing_email_consent
                FROM customers c
                JOIN customer_events ce ON ce.customer_id = c.id
                WHERE ce.event_type IN ('cart_abandoned', 'add_to_cart')
                  AND ce.created_at >= :since
                  AND NOT EXISTS (
                      SELECT 1 FROM orders o
                      WHERE o.customer_id = c.id AND o.created_at >= ce.created_at
                  )
                """
            ),
            {"since": since},
        ).fetchall()

    elif trigger == "high_value_order":
        min_val = _safe_float(trigger_value, 100.0)
        since = now - timedelta(hours=24)
        rows = db.execute(
            text(
                """
                SELECT DISTINCT c.id, c.name, c.phone, c.email,
                       c.marketing_whatsapp_consent, c.marketing_email_consent
                FROM customers c
                JOIN orders o ON o.customer_id = c.id
                WHERE o.total >= :min_val AND o.created_at >= :since
                """
            ),
            {"min_val": min_val, "since": since},
        ).fetchall()

    elif trigger in {"order_completed", "repeat_order", "same_weekday_last_order", "preferred_purchase_time"}:
        since = now - timedelta(hours=24)
        rows = db.execute(
            text(
                """
                SELECT DISTINCT c.id, c.name, c.phone, c.email,
                       c.marketing_whatsapp_consent, c.marketing_email_consent
                FROM customers c
                JOIN orders o ON o.customer_id = c.id
                WHERE o.status = 'delivered' AND o.created_at >= :since
                """
            ),
            {"since": since},
        ).fetchall()

    elif trigger == "recurring_customer":
        min_orders = _safe_int(trigger_value, 3)
        rows = db.execute(
            text(
                """
                SELECT id, name, phone, email, marketing_whatsapp_consent, marketing_email_consent
                FROM customers
                WHERE COALESCE(total_orders, 0) >= :min_orders
                """
            ),
            {"min_orders": min_orders},
        ).fetchall()

    elif trigger in {"vip_customer", "vip_milestone"}:
        min_spent = _safe_float(trigger_value, 500.0)
        rows = db.execute(
            text(
                """
                SELECT id, name, phone, email, marketing_whatsapp_consent, marketing_email_consent
                FROM customers
                WHERE COALESCE(total_spent, 0) >= :min_spent
                """
            ),
            {"min_spent": min_spent},
        ).fetchall()

    elif trigger == "product_purchased":
        rows = db.execute(
            text(
                """
                SELECT DISTINCT c.id, c.name, c.phone, c.email,
                       c.marketing_whatsapp_consent, c.marketing_email_consent
                FROM customers c
                JOIN orders o ON o.customer_id = c.id
                JOIN order_items oi ON oi.order_id = o.id
                LEFT JOIN products p ON p.id = oi.product_id
                WHERE (:product_id IS NOT NULL AND oi.product_id = :product_id)
                   OR (:trigger_value IS NOT NULL AND LOWER(COALESCE(p.name, '')) = LOWER(:trigger_value))
                """
            ),
            {"product_id": automation.get("product_id"), "trigger_value": trigger_value},
        ).fetchall()

    elif trigger == "category_purchased":
        rows = db.execute(
            text(
                """
                SELECT DISTINCT c.id, c.name, c.phone, c.email,
                       c.marketing_whatsapp_consent, c.marketing_email_consent
                FROM customers c
                JOIN orders o ON o.customer_id = c.id
                JOIN order_items oi ON oi.order_id = o.id
                JOIN products p ON p.id = oi.product_id
                WHERE LOWER(COALESCE(p.category, p.subcategory, '')) = LOWER(:category)
                """
            ),
            {"category": trigger_value or ""},
        ).fetchall()

    elif trigger == "tag_match":
        rows = db.execute(
            text(
                """
                SELECT DISTINCT c.id, c.name, c.phone, c.email,
                       c.marketing_whatsapp_consent, c.marketing_email_consent
                FROM customers c
                JOIN customer_tag_assignments cta ON cta.customer_id = c.id
                JOIN customer_tags ct ON ct.id = cta.tag_id
                WHERE ct.id = :tag OR LOWER(ct.slug) = LOWER(:tag) OR LOWER(ct.name) = LOWER(:tag)
                """
            ),
            {"tag": trigger_value or ""},
        ).fetchall()

    elif trigger == "group_match":
        rows = db.execute(
            text(
                """
                SELECT DISTINCT c.id, c.name, c.phone, c.email,
                       c.marketing_whatsapp_consent, c.marketing_email_consent
                FROM customers c
                JOIN customer_group_members cgm ON cgm.customer_id = c.id
                WHERE cgm.group_id = :group_id
                """
            ),
            {"group_id": automation.get("group_id") or trigger_value or ""},
        ).fetchall()

    elif trigger == "segment_match":
        rows = db.execute(
            text(
                """
                SELECT DISTINCT c.id, c.name, c.phone, c.email,
                       c.marketing_whatsapp_consent, c.marketing_email_consent
                FROM customers c
                JOIN customer_ai_profiles cap ON cap.customer_id = c.id
                WHERE LOWER(cap.segment) = LOWER(:segment)
                """
            ),
            {"segment": trigger_value or ""},
        ).fetchall()

    else:
        rows = []

    return [_row_dict(row) for row in rows]


def resolve_message(db: Session, automation: dict[str, Any]) -> tuple[str | None, str]:
    channel = automation["channel"]
    subject = "Mensagem da Pizzaria"
    body = automation.get("message_body") or ""
    template_id = automation.get("template_id")

    if not template_id:
        return subject, body

    if channel == "whatsapp":
        row = db.execute(
            text("SELECT body FROM automation_templates WHERE id = :tid"),
            {"tid": template_id},
        ).fetchone()
        if row:
            return None, row[0]
        row = db.execute(
            text("SELECT body FROM whatsapp_templates WHERE id = :tid AND active = TRUE"),
            {"tid": template_id},
        ).fetchone()
        return (None, row[0]) if row else (None, body)

    row = db.execute(
        text("SELECT body, subject FROM automation_templates WHERE id = :tid"),
        {"tid": template_id},
    ).fetchone()
    if row:
        return row[1] or subject, row[0]
    row = db.execute(
        text("SELECT subject, body_html FROM email_templates WHERE id = :tid AND active = TRUE"),
        {"tid": template_id},
    ).fetchone()
    return (row[0], row[1]) if row else (subject, body)


def customer_allows_channel(customer: dict[str, Any], channel: str) -> tuple[bool, str | None]:
    if channel == "whatsapp":
        if not customer.get("phone"):
            return False, "Cliente sem telefone."
        if not customer.get("marketing_whatsapp_consent"):
            return False, "Cliente sem consentimento de WhatsApp."
        return True, None
    if channel == "email":
        if not customer.get("email"):
            return False, "Cliente sem e-mail."
        if not customer.get("marketing_email_consent"):
            return False, "Cliente sem consentimento de e-mail."
        return True, None
    return False, f"Canal '{channel}' nao suportado."


def daily_limit_reached(db: Session, automation: dict[str, Any]) -> bool:
    daily_limit = automation.get("daily_limit")
    if not daily_limit:
        return False
    today_start = _now().replace(hour=0, minute=0, second=0, microsecond=0)
    sent_today = _scalar(
        db,
        """
        SELECT COUNT(*)
        FROM automation_executions
        WHERE automation_id = :automation_id
          AND status = 'sent'
          AND created_at >= :since
        """,
        {"automation_id": automation["id"], "since": today_start},
    ) or 0
    return int(sent_today) >= int(daily_limit)


def already_sent(db: Session, automation: dict[str, Any], customer_id: str) -> bool:
    cooldown_hours = _safe_int(automation.get("cooldown_hours"), 24)
    max_sends = _safe_int(automation.get("max_sends_per_customer"), 1)
    since = _now() - timedelta(hours=cooldown_hours)
    sent_count = _scalar(
        db,
        """
        SELECT COUNT(*)
        FROM automation_executions
        WHERE automation_id = :automation_id
          AND customer_id = :customer_id
          AND status = 'sent'
        """,
        {"automation_id": automation["id"], "customer_id": customer_id},
    ) or 0
    if int(sent_count) >= max_sends:
        return True
    recent_sent = _scalar(
        db,
        """
        SELECT COUNT(*)
        FROM automation_executions
        WHERE automation_id = :automation_id
          AND customer_id = :customer_id
          AND status = 'sent'
          AND sent_at >= :since
        """,
        {"automation_id": automation["id"], "customer_id": customer_id, "since": since},
    ) or 0
    if int(recent_sent) > 0:
        return True
    legacy_recent = _scalar(
        db,
        """
        SELECT COUNT(*)
        FROM automation_logs
        WHERE automation_id = :automation_id
          AND customer_id = :customer_id
          AND status = 'sent'
          AND created_at >= :since
        """,
        {"automation_id": automation["id"], "customer_id": customer_id, "since": since},
    ) or 0
    return int(legacy_recent) > 0


def build_customer_variables(db: Session, customer: dict[str, Any], automation: dict[str, Any]) -> dict[str, str]:
    customer_id = customer["id"]
    full_customer = _row_dict(
        db.execute(
            text(
                """
                SELECT id, name, email, phone, total_orders, total_spent, avg_ticket,
                       last_order_at, birth_date
                FROM customers
                WHERE id = :customer_id
                """
            ),
            {"customer_id": customer_id},
        ).fetchone()
    )
    if not full_customer:
        full_customer = customer

    last_order = _row_dict(
        db.execute(
            text(
                """
                SELECT id, created_at, total, coupon_id
                FROM orders
                WHERE customer_id = :customer_id
                ORDER BY created_at DESC
                LIMIT 1
                """
            ),
            {"customer_id": customer_id},
        ).fetchone()
    )
    favorite_product = _scalar(
        db,
        """
        SELECT COALESCE(p.name, oi.selected_drink_variant, 'Produto')
        FROM order_items oi
        JOIN orders o ON o.id = oi.order_id
        LEFT JOIN products p ON p.id = oi.product_id
        WHERE o.customer_id = :customer_id
        GROUP BY COALESCE(p.name, oi.selected_drink_variant, 'Produto')
        ORDER BY COUNT(*) DESC
        LIMIT 1
        """,
        {"customer_id": customer_id},
    ) or ""
    last_product = _scalar(
        db,
        """
        SELECT COALESCE(p.name, oi.selected_drink_variant, 'Produto')
        FROM order_items oi
        JOIN orders o ON o.id = oi.order_id
        LEFT JOIN products p ON p.id = oi.product_id
        WHERE o.customer_id = :customer_id
        ORDER BY o.created_at DESC
        LIMIT 1
        """,
        {"customer_id": customer_id},
    ) or favorite_product
    preferred_hour = _scalar(
        db,
        """
        SELECT TO_CHAR(created_at, 'HH24:00')
        FROM orders
        WHERE customer_id = :customer_id
        GROUP BY TO_CHAR(created_at, 'HH24:00')
        ORDER BY COUNT(*) DESC
        LIMIT 1
        """,
        {"customer_id": customer_id},
    ) or ""
    neighborhood = _scalar(
        db,
        """
        SELECT neighborhood
        FROM addresses
        WHERE customer_id = :customer_id
        ORDER BY is_default DESC, created_at DESC
        LIMIT 1
        """,
        {"customer_id": customer_id},
    ) or ""
    coupon_id = automation.get("coupon_id") or last_order.get("coupon_id")
    coupon = _row_dict(
        db.execute(
            text("SELECT code, discount_value FROM coupons WHERE id = :coupon_id"),
            {"coupon_id": coupon_id},
        ).fetchone()
    ) if coupon_id else {}

    last_order_at = last_order.get("created_at") or full_customer.get("last_order_at")
    weekday = WEEKDAY_NAMES[last_order_at.weekday()] if isinstance(last_order_at, datetime) else ""
    store_url = os.environ.get("PUBLIC_STORE_URL") or os.environ.get("VITE_PUBLIC_STORE_URL") or "http://localhost:5173"

    return {
        "nome_cliente": str(full_customer.get("name") or ""),
        "primeiro_nome": _first_name(full_customer.get("name")),
        "produto_mais_comprado": str(favorite_product or ""),
        "ultima_pizza_comprada": str(last_product or ""),
        "data_ultimo_pedido": _iso_date(last_order_at),
        "dia_semana_ultimo_pedido": weekday,
        "cupom": str(coupon.get("code") or ""),
        "valor_cupom": str(coupon.get("discount_value") or ""),
        "link_loja": store_url.rstrip("/"),
        "link_carrinho": f"{store_url.rstrip('/')}/cart",
        "ticket_medio": f"{float(full_customer.get('avg_ticket') or 0):.2f}",
        "total_pedidos": str(full_customer.get("total_orders") or 0),
        "bairro": str(neighborhood or ""),
        "horario_preferido": str(preferred_hour or ""),
    }


def render_message(message: str, variables: dict[str, str]) -> str:
    def replace(match: re.Match[str]) -> str:
        key = match.group(1)
        return variables.get(key, match.group(0))

    return VARIABLE_RE.sub(replace, message or "")


def _parse_allowed_weekdays(raw: Any) -> set[int] | None:
    if not raw:
        return None
    names = {name: index for index, name in enumerate(WEEKDAY_NAMES)}
    values: set[int] = set()
    for part in str(raw).replace(";", ",").split(","):
        token = part.strip().lower()
        if not token:
            continue
        if token.isdigit():
            values.add(int(token) % 7)
        elif token in names:
            values.add(names[token])
    return values or None


def _parse_hour_minute(raw: Any) -> tuple[int, int] | None:
    if not raw:
        return None
    parts = str(raw).strip().split(":", 1)
    if len(parts) != 2:
        return None
    try:
        hour = max(0, min(23, int(parts[0])))
        minute = max(0, min(59, int(parts[1])))
    except ValueError:
        return None
    return hour, minute


def scheduled_at_for_automation(automation: dict[str, Any]) -> datetime:
    scheduled = _now() + timedelta(hours=_safe_int(automation.get("trigger_delay_hours"), 0))
    allowed_weekdays = _parse_allowed_weekdays(automation.get("allowed_weekdays"))
    start_time = _parse_hour_minute(automation.get("allowed_start_time"))
    end_time = _parse_hour_minute(automation.get("allowed_end_time"))

    for _ in range(8):
        if allowed_weekdays and scheduled.weekday() not in allowed_weekdays:
            scheduled = (scheduled + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
            continue

        if start_time:
            start_dt = scheduled.replace(hour=start_time[0], minute=start_time[1], second=0, microsecond=0)
            if scheduled < start_dt:
                scheduled = start_dt
        if end_time:
            end_dt = scheduled.replace(hour=end_time[0], minute=end_time[1], second=0, microsecond=0)
            if scheduled > end_dt:
                scheduled = (scheduled + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
                continue
        return scheduled

    return scheduled


def create_execution(
    db: Session,
    automation: dict[str, Any],
    customer: dict[str, Any],
    *,
    subject: str | None,
    message_body: str,
    scheduled_at: datetime | None = None,
) -> str | None:
    execution_id = str(uuid.uuid4())
    dedupe_key = f"{automation['id']}:{customer['id']}:{automation['channel']}:{_now().date().isoformat()}"
    existing = db.execute(
        text("SELECT id FROM automation_executions WHERE dedupe_key = :dedupe_key"),
        {"dedupe_key": dedupe_key},
    ).fetchone()
    if existing:
        return None
    db.execute(
        text(
            """
            INSERT INTO automation_executions (
                id, automation_id, customer_id, source_event_type, channel, status,
                scheduled_at, dedupe_key, subject, message_body, metadata_json, created_at, updated_at
            )
            VALUES (
                :id, :automation_id, :customer_id, :source_event_type, :channel, 'pending',
                :scheduled_at, :dedupe_key, :subject, :message_body, '{}', :now, :now
            )
            """
        ),
        {
            "id": execution_id,
            "automation_id": automation["id"],
            "customer_id": customer["id"],
            "source_event_type": automation["trigger"],
            "channel": automation["channel"],
            "scheduled_at": scheduled_at or _now(),
            "dedupe_key": dedupe_key,
            "subject": subject,
            "message_body": message_body,
            "now": _now(),
        },
    )
    log_execution_event(db, execution_id, automation["id"], customer["id"], "pending", "queued", "Execucao enfileirada.")
    return execution_id


def update_execution(
    db: Session,
    execution_id: str,
    status: str,
    *,
    error: str | None = None,
    provider_message_id: str | None = None,
) -> None:
    now = _now()
    db.execute(
        text(
            """
            UPDATE automation_executions
            SET status = :status,
                started_at = COALESCE(started_at, :now),
                sent_at = CASE WHEN :status = 'sent' THEN :now ELSE sent_at END,
                finished_at = :now,
                provider_message_id = :provider_message_id,
                error = :error,
                attempts = attempts + 1,
                updated_at = :now
            WHERE id = :execution_id
            """
        ),
        {
            "execution_id": execution_id,
            "status": status,
            "provider_message_id": provider_message_id,
            "error": error,
            "now": now,
        },
    )


def reschedule_execution(db: Session, execution_id: str, error: str | None, retry_minutes: int = 15) -> None:
    next_attempt = _now() + timedelta(minutes=retry_minutes)
    db.execute(
        text(
            """
            UPDATE automation_executions
            SET status = 'pending',
                attempts = attempts + 1,
                error = :error,
                next_attempt_at = :next_attempt,
                scheduled_at = :next_attempt,
                updated_at = :now
            WHERE id = :execution_id
            """
        ),
        {"execution_id": execution_id, "error": error, "next_attempt": next_attempt, "now": _now()},
    )


def log_execution_event(
    db: Session,
    execution_id: str | None,
    automation_id: str,
    customer_id: str | None,
    status: str,
    event_type: str,
    message: str | None = None,
    error: str | None = None,
) -> None:
    db.execute(
        text(
            """
            INSERT INTO automation_execution_logs (
                id, execution_id, automation_id, customer_id, status, event_type,
                message, error, metadata_json, created_at
            )
            VALUES (
                :id, :execution_id, :automation_id, :customer_id, :status, :event_type,
                :message, :error, '{}', :created_at
            )
            """
        ),
        {
            "id": str(uuid.uuid4()),
            "execution_id": execution_id,
            "automation_id": automation_id,
            "customer_id": customer_id,
            "status": status,
            "event_type": event_type,
            "message": message,
            "error": error,
            "created_at": _now(),
        },
    )


def log_legacy_automation(db: Session, automation_id: str, customer_id: str, channel: str, status: str, error: str | None) -> None:
    db.execute(
        text(
            """
            INSERT INTO automation_logs (id, automation_id, customer_id, channel, status, error, created_at)
            VALUES (:id, :automation_id, :customer_id, :channel, :status, :error, :created_at)
            """
        ),
        {
            "id": str(uuid.uuid4()),
            "automation_id": automation_id,
            "customer_id": customer_id,
            "channel": channel,
            "status": status,
            "error": error,
            "created_at": _now(),
        },
    )


def log_channel_message(
    db: Session,
    automation: dict[str, Any],
    customer: dict[str, Any],
    *,
    subject: str | None,
    body: str,
    status: str,
    provider_message_id: str | None,
    error: str | None,
) -> None:
    if automation["channel"] == "whatsapp":
        db.execute(
            text(
                """
                INSERT INTO whatsapp_messages (
                    id, template_id, customer_id, phone, body_sent, status, wamid, error, sent_at, created_at
                )
                VALUES (
                    :id, :template_id, :customer_id, :phone, :body, :status, :wamid, :error, :sent_at, :created_at
                )
                """
            ),
            {
                "id": str(uuid.uuid4()),
                "template_id": automation.get("template_id"),
                "customer_id": customer["id"],
                "phone": customer.get("phone"),
                "body": body,
                "status": status,
                "wamid": provider_message_id,
                "error": error,
                "sent_at": _now() if status == "sent" else None,
                "created_at": _now(),
            },
        )
    elif automation["channel"] == "email":
        db.execute(
            text(
                """
                INSERT INTO email_messages (
                    id, template_id, customer_id, to_email, subject_sent, status, error, sent_at, created_at
                )
                VALUES (
                    :id, :template_id, :customer_id, :to_email, :subject, :status, :error, :sent_at, :created_at
                )
                """
            ),
            {
                "id": str(uuid.uuid4()),
                "template_id": automation.get("template_id"),
                "customer_id": customer["id"],
                "to_email": customer.get("email"),
                "subject": subject,
                "status": status,
                "error": error,
                "sent_at": _now() if status == "sent" else None,
                "created_at": _now(),
            },
        )


def send_message(db: Session, automation: dict[str, Any], customer: dict[str, Any], subject: str | None, body: str) -> tuple[str, str | None, str | None]:
    if automation["channel"] == "whatsapp":
        from backend.routes.whatsapp_marketing import _send_whatsapp_api

        provider_message_id, status, error = _send_whatsapp_api(customer["phone"], body, db)
        return status, error, provider_message_id

    if automation["channel"] == "email":
        from backend.routes.email_marketing import _get_config, _send_email

        cfg = _get_config(db)
        success, error = _send_email(customer["email"], subject or "Mensagem da Pizzaria", body, cfg)
        return ("sent" if success else "failed"), error, None

    return "failed", f"Canal '{automation['channel']}' nao suportado.", None


def enqueue_automation(db: Session, automation: dict[str, Any]) -> dict[str, int]:
    customers = get_eligible_customers(db, automation)
    subject, raw_body = resolve_message(db, automation)
    queued_count = 0
    skipped_count = 0
    failed_count = 0

    for customer in customers:
        if daily_limit_reached(db, automation):
            skipped_count += 1
            break

        allowed, reason = customer_allows_channel(customer, automation["channel"])
        if not allowed:
            skipped_count += 1
            log_execution_event(db, None, automation["id"], customer["id"], "skipped", "skipped", error=reason)
            continue

        if already_sent(db, automation, customer["id"]):
            skipped_count += 1
            continue

        if not raw_body:
            failed_count += 1
            log_execution_event(
                db,
                None,
                automation["id"],
                customer["id"],
                "failed",
                "failed",
                error="Nenhum corpo de mensagem definido.",
            )
            continue

        variables = build_customer_variables(db, customer, automation)
        rendered_body = render_message(raw_body, variables)
        rendered_subject = render_message(subject or "", variables) if subject else None
        scheduled_at = scheduled_at_for_automation(automation)
        execution_id = create_execution(
            db,
            automation,
            customer,
            subject=rendered_subject,
            message_body=rendered_body,
            scheduled_at=scheduled_at,
        )
        if execution_id:
            queued_count += 1
        else:
            skipped_count += 1

    next_run_at = _now() + timedelta(hours=_safe_int(automation.get("cooldown_hours"), 24))
    db.execute(
        text(
            """
            UPDATE marketing_automations
            SET last_evaluated_at = :now,
                next_run_at = :next_run_at,
                updated_at = :now
            WHERE id = :automation_id
            """
        ),
        {"automation_id": automation["id"], "now": _now(), "next_run_at": next_run_at},
    )
    return {"queued": queued_count, "failed": failed_count, "skipped": skipped_count}


def enqueue_due_automations(db: Session, limit: int = 50) -> dict[str, int]:
    rows = db.execute(
        text(
            """
            SELECT id
            FROM marketing_automations
            WHERE active = TRUE
              AND (next_run_at IS NULL OR next_run_at <= :now)
            ORDER BY priority ASC, COALESCE(next_run_at, created_at) ASC
            LIMIT :limit
            """
        ),
        {"now": _now(), "limit": limit},
    ).fetchall()

    totals = {"automations": 0, "queued": 0, "failed": 0, "skipped": 0}
    for row in rows:
        automation = load_automation(db, row[0])
        result = enqueue_automation(db, automation)
        totals["automations"] += 1
        totals["queued"] += result["queued"]
        totals["failed"] += result["failed"]
        totals["skipped"] += result["skipped"]
    db.commit()
    return totals


def _load_pending_executions(db: Session, limit: int) -> list[dict[str, Any]]:
    rows = db.execute(
        text(
            """
            SELECT
                ae.id AS execution_id,
                ae.automation_id,
                ae.customer_id,
                ae.channel,
                ae.subject,
                ae.message_body,
                ae.attempts,
                ae.max_attempts,
                ma.template_id,
                c.name,
                c.phone,
                c.email,
                c.marketing_whatsapp_consent,
                c.marketing_email_consent
            FROM automation_executions ae
            JOIN marketing_automations ma ON ma.id = ae.automation_id
            LEFT JOIN customers c ON c.id = ae.customer_id
            WHERE ae.status = 'pending'
              AND ae.scheduled_at <= :now
            ORDER BY ae.scheduled_at ASC, ae.created_at ASC
            LIMIT :limit
            """
        ),
        {"now": _now(), "limit": limit},
    ).fetchall()
    return [_row_dict(row) for row in rows]


def process_pending_executions(db: Session, limit: int = 100) -> dict[str, int]:
    executions = _load_pending_executions(db, limit)
    totals = {"processed": 0, "sent": 0, "failed": 0, "retried": 0, "skipped": 0}

    for execution in executions:
        automation = load_automation(db, execution["automation_id"])
        customer = {
            "id": execution["customer_id"],
            "name": execution.get("name"),
            "phone": execution.get("phone"),
            "email": execution.get("email"),
            "marketing_whatsapp_consent": execution.get("marketing_whatsapp_consent"),
            "marketing_email_consent": execution.get("marketing_email_consent"),
        }
        totals["processed"] += 1

        allowed, reason = customer_allows_channel(customer, execution["channel"])
        if not allowed:
            update_execution(db, execution["execution_id"], "cancelled", error=reason)
            log_execution_event(
                db,
                execution["execution_id"],
                execution["automation_id"],
                execution["customer_id"],
                "cancelled",
                "cancelled",
                error=reason,
            )
            log_legacy_automation(db, execution["automation_id"], execution["customer_id"], execution["channel"], "skipped", reason)
            totals["skipped"] += 1
            continue

        try:
            status, error_msg, provider_message_id = send_message(
                db,
                automation,
                customer,
                execution.get("subject"),
                execution.get("message_body") or "",
            )
        except Exception as exc:
            status = "failed"
            error_msg = str(exc)
            provider_message_id = None

        if status != "sent" and int(execution.get("attempts") or 0) + 1 < int(execution.get("max_attempts") or 3):
            reschedule_execution(db, execution["execution_id"], error_msg)
            log_execution_event(
                db,
                execution["execution_id"],
                execution["automation_id"],
                execution["customer_id"],
                "pending",
                "retry_scheduled",
                error=error_msg,
            )
            totals["retried"] += 1
            continue

        update_execution(db, execution["execution_id"], status, error=error_msg, provider_message_id=provider_message_id)
        log_execution_event(
            db,
            execution["execution_id"],
            execution["automation_id"],
            execution["customer_id"],
            status,
            "sent" if status == "sent" else "failed",
            error=error_msg,
        )
        log_channel_message(
            db,
            automation,
            customer,
            subject=execution.get("subject"),
            body=execution.get("message_body") or "",
            status=status,
            provider_message_id=provider_message_id,
            error=error_msg,
        )
        log_legacy_automation(db, execution["automation_id"], execution["customer_id"], execution["channel"], status, error_msg)

        if status == "sent":
            totals["sent"] += 1
        else:
            totals["failed"] += 1

    db.commit()
    return totals


def run_due_automation_worker(db: Session, automation_limit: int = 50, execution_limit: int = 100) -> dict[str, dict[str, int]]:
    queued = enqueue_due_automations(db, limit=automation_limit)
    processed = process_pending_executions(db, limit=execution_limit)
    return {"queued": queued, "processed": processed}


def run_automation_now(db: Session, automation_id: str) -> dict[str, int]:
    automation = load_automation(db, automation_id)
    customers = get_eligible_customers(db, automation)
    subject, raw_body = resolve_message(db, automation)
    sent_count = 0
    failed_count = 0
    skipped_count = 0

    for customer in customers:
        status = "failed"
        error_msg: str | None = None
        execution_id: str | None = None
        rendered_body = raw_body

        if daily_limit_reached(db, automation):
            skipped_count += 1
            break

        allowed, reason = customer_allows_channel(customer, automation["channel"])
        if not allowed:
            status = "skipped"
            error_msg = reason
            skipped_count += 1
            log_legacy_automation(db, automation_id, customer["id"], automation["channel"], status, error_msg)
            log_execution_event(db, None, automation_id, customer["id"], status, "skipped", error=error_msg)
            continue

        if already_sent(db, automation, customer["id"]):
            skipped_count += 1
            continue

        if not raw_body:
            status = "failed"
            error_msg = "Nenhum corpo de mensagem definido."
            failed_count += 1
            log_legacy_automation(db, automation_id, customer["id"], automation["channel"], status, error_msg)
            log_execution_event(db, None, automation_id, customer["id"], status, "failed", error=error_msg)
            continue

        variables = build_customer_variables(db, customer, automation)
        rendered_body = render_message(raw_body, variables)
        rendered_subject = render_message(subject or "", variables) if subject else None
        execution_id = create_execution(db, automation, customer, subject=rendered_subject, message_body=rendered_body)
        if not execution_id:
            skipped_count += 1
            continue

        try:
            status, error_msg, provider_message_id = send_message(db, automation, customer, rendered_subject, rendered_body)
        except Exception as exc:
            status = "failed"
            error_msg = str(exc)
            provider_message_id = None

        update_execution(db, execution_id, status, error=error_msg, provider_message_id=provider_message_id)
        log_execution_event(
            db,
            execution_id,
            automation_id,
            customer["id"],
            status,
            "sent" if status == "sent" else "failed",
            error=error_msg,
        )
        log_channel_message(
            db,
            automation,
            customer,
            subject=rendered_subject,
            body=rendered_body,
            status=status,
            provider_message_id=provider_message_id,
            error=error_msg,
        )
        log_legacy_automation(db, automation_id, customer["id"], automation["channel"], status, error_msg)

        if status == "sent":
            sent_count += 1
        elif status == "skipped":
            skipped_count += 1
        else:
            failed_count += 1

    db.execute(
        text(
            """
            UPDATE marketing_automations
            SET runs_total = COALESCE(runs_total, 0) + 1,
                last_run_at = :now,
                last_evaluated_at = :now,
                updated_at = :now
            WHERE id = :automation_id
            """
        ),
        {"automation_id": automation_id, "now": _now()},
    )
    db.commit()
    return {"sent": sent_count, "failed": failed_count, "skipped": skipped_count}
