"""Mobile BI projections over canonical, tenant-owned operational records."""
from __future__ import annotations

import calendar
import json
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import and_, case, exists, func, or_, select, text
from sqlalchemy.orm import Session

from backend.core.exceptions import DomainError
from backend.core.local_time import STORE_TIMEZONE, local_now, local_period_bounds
from backend.models.order import Order, OrderItem
from backend.models.payment import Payment
from backend.models.product import Product
from backend.schemas.bi import BIMobileAnalyticsOut, BIMobileAnalysisOut, BIMobileQuery
from backend.services.business_intelligence_service import BusinessIntelligenceService
from backend.services.storefront_presence import active_storefront_visitors


class InvalidBIQuery(DomainError):
    http_status = 422


def previous_month(value: date) -> date:
    year, month = (value.year - 1, 12) if value.month == 1 else (value.year, value.month - 1)
    return date(year, month, min(value.day, calendar.monthrange(year, month)[1]))


def variation(current: float, previous: float) -> dict:
    return {"difference": round(current - previous, 2),
            "percent": round((current - previous) / previous * 100, 2) if previous else None}


class BIMobileService:
    def __init__(self, db: Session, tenant_id: str):
        self.db = db
        self.tenant_id = tenant_id
        self.legacy = BusinessIntelligenceService(db, tenant_id)

    def bounds(self, query: BIMobileQuery, now: datetime) -> dict:
        anchor = query.date or now.date()
        if anchor > now.date():
            raise InvalidBIQuery("Selecione uma data até hoje.")
        days = {"today": 1, "7d": 7, "30d": 30, "90d": 90}
        start = anchor.replace(day=1) if query.period == "month" else anchor - timedelta(days=days[query.period] - 1)
        start_dt, end_dt = local_period_bounds(start, anchor)
        partial = bool(query.partial and anchor == now.date())
        if partial:
            end_dt = now.astimezone(timezone.utc)
        previous_start = previous_end = None
        if query.compare == "previous_month":
            # Keep the same number of days; clamp the ending day explicitly.
            previous_end = previous_month(anchor)
            previous_start = previous_end - timedelta(days=(anchor - start).days)
            if query.period == "month":
                previous_start = previous_end.replace(day=1)
        elif query.compare == "previous_period":
            previous_end = start - timedelta(days=1)
            previous_start = previous_end - timedelta(days=(anchor - start).days)
        prev_start_dt = prev_end_dt = None
        if previous_start:
            prev_start_dt, prev_end_dt = local_period_bounds(previous_start, previous_end)
            if partial:
                prev_end_dt = datetime.combine(previous_end, now.timetz(), tzinfo=STORE_TIMEZONE).astimezone(timezone.utc)
        return {"start": start, "end": anchor, "start_dt": start_dt, "end_dt": end_dt,
                "previous_start": previous_start, "previous_end": previous_end,
                "previous_start_dt": prev_start_dt, "previous_end_dt": prev_end_dt, "partial": partial}

    def _paid(self):
        return and_(~Order.status.in_(self.legacy.CANCELLED_STATUSES), exists(select(Payment.id).where(
            Payment.order_id == Order.id, Payment.tenant_id == self.tenant_id,
            Payment.status.in_(self.legacy.PAID_PAYMENT_STATUSES)).correlate(Order)))

    def _pizza_quantity(self):
        # Each physical item counts once regardless of flavor divisions. Legacy
        # products lacking type are only counted with an explicit pizza category.
        return select(func.coalesce(func.sum(OrderItem.quantity), 0)).select_from(OrderItem).join(
            Product, and_(Product.id == OrderItem.product_id, Product.tenant_id == self.tenant_id)
        ).where(OrderItem.order_id == Order.id, OrderItem.tenant_id == self.tenant_id,
                or_(Product.product_type == "pizza", and_(Product.product_type.is_(None),
                    func.lower(func.trim(Product.category)).in_((
                        "pizza", "pizzas", "pizza individual", "pizzas individuais",
                        "pizzas tradicionais", "pizzas especiais", "pizzas doces", "pizzas salgadas",
                    ))))) .correlate(Order).scalar_subquery()

    def _bucket(self, hourly: bool):
        if self.db.get_bind().dialect.name == "postgresql":
            return func.to_char(func.timezone("America/Sao_Paulo", Order.created_at), "YYYY-MM-DD HH24" if hourly else "YYYY-MM-DD")
        return func.strftime("%Y-%m-%d %H" if hourly else "%Y-%m-%d", Order.created_at, "-3 hours")

    def _rows(self, start_dt: datetime, end_dt: datetime, hourly: bool = False) -> list[dict]:
        bucket, paid = self._bucket(hourly), self._paid()
        rows = self.db.query(bucket.label("date"), func.count(Order.id).label("created"),
            func.sum(case((paid, 1), else_=0)).label("orders"),
            func.coalesce(func.sum(case((paid, Order.total), else_=0)), 0).label("revenue"),
            func.coalesce(func.sum(case((paid, self._pizza_quantity()), else_=0)), 0).label("pizzas"),
        ).filter(Order.tenant_id == self.tenant_id, Order.created_at >= start_dt, Order.created_at <= end_dt
        ).group_by(bucket).order_by(bucket).all()
        return [{"date": str(row.date), "created": int(row.created), "orders": int(row.orders or 0),
                 "revenue": round(float(row.revenue), 2), "pizzas": int(row.pizzas or 0)} for row in rows]

    def _totals(self, start_dt: datetime, end_dt: datetime, rows: list[dict], days: int) -> dict:
        paid = self._paid()
        cancelled = Order.status.in_(self.legacy.CANCELLED_STATUSES)
        q = self.db.query(Order).filter(Order.tenant_id == self.tenant_id,
            Order.created_at >= start_dt, Order.created_at <= end_dt)
        financial = q.with_entities(
            func.coalesce(func.sum(case((cancelled, Order.total), else_=0)), 0),
            func.coalesce(func.sum(case((paid, Order.subtotal + func.coalesce(Order.shipping_fee, 0)), else_=0)), 0),
            func.coalesce(func.sum(case((paid, Order.discount), else_=0)), 0),
            func.coalesce(func.sum(case((~cancelled, Order.total), else_=0)), 0),
        ).one()
        statuses = {getattr(status, "value", status): int(count) for status, count in q.with_entities(
            Order.status, func.count(Order.id)).group_by(Order.status).all()}
        buckets = {key: sum(statuses.get(status, 0) for status in values)
                   for key, values in self.legacy.MOBILE_STATUS_BUCKETS.items()}
        orders = sum(row["orders"] for row in rows)
        revenue = round(sum(row["revenue"] for row in rows), 2)
        best = max(rows, key=lambda row: row["revenue"], default=None)
        return {"orders": sum(statuses.values()), "valid_orders": orders, "revenue": revenue,
            "pizzas": sum(row["pizzas"] for row in rows), "average_ticket": round(revenue / orders, 2) if orders else 0,
            "cancelled_orders": buckets["cancelado"], "cancelled_value": round(float(financial[0]), 2),
            "completed_orders": buckets["entregue"],
            "active_orders": sum(statuses.get(s.value, 0) for s in self.legacy.MOBILE_EFFECTIVE_ORDER_STATUSES if s.value != "delivered"),
            "gross_sales": round(float(financial[1]), 2), "discounts": round(float(financial[2]), 2),
            "forecast_revenue": round(float(financial[3]), 2),
            "daily_revenue": round(revenue / days, 2), "daily_orders": round(orders / days, 2),
            "best_day": best["date"] if best and best["revenue"] > 0 else None, "status_counts": buckets}

    def _attendance(self, start_dt: datetime, end_dt: datetime, now: datetime) -> dict:
        from backend.routes.marketing import _public_tracking_sql as public_page_sql
        params = {"tenant_id": self.tenant_id, "start_dt": start_dt, "end_dt": end_dt}
        accesses = self.db.execute(text(f"""SELECT COUNT(*) FROM visitor_sessions
            WHERE tenant_id = :tenant_id AND started_at BETWEEN :start_dt AND :end_dt
            AND {public_page_sql('landing_page')}"""), params).scalar() or 0
        minutes = self.db.execute(text("SELECT online_visitor_minutes FROM marketing_settings WHERE tenant_id = :tenant_id"), params).scalar() or 5
        active, _ = active_storefront_visitors(self.db, self.tenant_id, now, int(minutes), public_page_sql("ve.page"))
        customers = 0
        if active:
            # Only profile links of visitors with current storefront heartbeats
            # count as online; an admin/customer analytics event is insufficient.
            from sqlalchemy import bindparam
            customers = self.db.execute(text("SELECT COUNT(DISTINCT customer_id) FROM visitor_profiles WHERE tenant_id = :tenant_id AND id IN :ids AND customer_id IS NOT NULL").bindparams(bindparam("ids", expanding=True)),
                {"tenant_id": self.tenant_id, "ids": list(active)}).scalar() or 0
        from backend.models.agente_whatsapp import AgenteWhatsAppAISettings, AgenteWhatsAppSession
        from backend.services.agente_whatsapp_service import AgenteWhatsAppService
        from backend.core.wave6_tenant_context import WAVE6_SESSION_TENANT_KEY
        context = self.db.info.get(WAVE6_SESSION_TENANT_KEY)
        whatsapp = None
        if context is not None and context.tenant_id == self.tenant_id:
            whatsapp = AgenteWhatsAppService(self.db, context).operational_metrics()
            # Configuration and recent conversations do not prove live presence.
            whatsapp["chatbots_online"] = None
            whatsapp["human_attendants_online"] = None
        sessions_in_period = self.db.query(func.count(AgenteWhatsAppSession.id)).filter(
            AgenteWhatsAppSession.tenant_id == self.tenant_id, AgenteWhatsAppSession.created_at >= start_dt,
            AgenteWhatsAppSession.created_at <= end_dt).scalar() or 0
        settings = self.db.query(AgenteWhatsAppAISettings).filter(AgenteWhatsAppAISettings.tenant_id == self.tenant_id).first()
        unique_visitors = self.db.execute(text(f"""SELECT COUNT(*) FROM (
            SELECT visitor_id FROM visitor_events WHERE tenant_id = :tenant_id
            AND created_at BETWEEN :start_dt AND :end_dt AND {public_page_sql('page')}
            UNION SELECT visitor_id FROM visitor_sessions WHERE tenant_id = :tenant_id
            AND started_at BETWEEN :start_dt AND :end_dt AND {public_page_sql('landing_page')}
            ) visitors"""), params).scalar() or 0
        from backend.models.chatbot import ChatbotConversation, ChatbotMessage, ConversationStatus
        chatbot_rows = self.db.query(ChatbotConversation.status, func.count(ChatbotConversation.id)).filter(
            ChatbotConversation.tenant_id == self.tenant_id, ChatbotConversation.iniciada_em >= start_dt,
            ChatbotConversation.iniciada_em <= end_dt).group_by(ChatbotConversation.status).all()
        chatbot_conversations = {getattr(status, "value", status): int(count) for status, count in chatbot_rows}
        chatbot_online = self.db.query(func.count(ChatbotConversation.id)).filter(
            ChatbotConversation.tenant_id == self.tenant_id,
            ChatbotConversation.status == ConversationStatus.aberta,
            exists(select(ChatbotMessage.id).where(
                ChatbotMessage.tenant_id == self.tenant_id,
                ChatbotMessage.conversation_id == ChatbotConversation.id,
                ChatbotMessage.timestamp >= now - timedelta(minutes=5),
                ChatbotMessage.timestamp <= now,
            )),
        ).scalar() or 0
        duration = (func.extract("epoch", ChatbotConversation.encerrada_em - ChatbotConversation.iniciada_em)
            if self.db.get_bind().dialect.name == "postgresql" else
            (func.julianday(ChatbotConversation.encerrada_em) - func.julianday(ChatbotConversation.iniciada_em)) * 86400)
        avg_duration = self.db.query(func.avg(duration)).filter(
            ChatbotConversation.tenant_id == self.tenant_id,
            ChatbotConversation.status == ConversationStatus.encerrada,
            ChatbotConversation.encerrada_em >= start_dt, ChatbotConversation.encerrada_em <= end_dt,
            ChatbotConversation.encerrada_em >= ChatbotConversation.iniciada_em).scalar()
        return {"unique_visitors": int(unique_visitors), "accesses": int(accesses),
            "visitors_online": len(active), "customers_online": int(customers), "whatsapp": whatsapp,
            "chatbot": int(chatbot_online), "human_operators": None,
            "chatbot_conversations": chatbot_conversations,
            "total_attendances": int(sessions_in_period) + sum(chatbot_conversations.values()),
            "avg_attendance_seconds": round(float(avg_duration), 2) if avg_duration is not None else None,
            "avg_attendance_source": "chatbot_closed_in_period",
            "ai_status": ("enabled" if settings.enabled else "disabled") if settings else "unavailable",
            "availability_note": "Presença da loja usa heartbeat atual. Chatbot online conta conversas abertas com mensagens nos últimos cinco minutos. Total do período conta conversas iniciadas na loja e WhatsApp, sem deduplicar pessoas entre canais. Duração média considera apenas chatbot da loja encerrado no período (início/fim persistidos). Métricas operacionais WhatsApp são atuais. Disponibilidade de operadores humanos não possui presença comprovada."}

    def _monthly(self, query: BIMobileQuery, now: datetime) -> list[dict]:
        anchor = query.date or now.date()
        if query.monthly in ("year", "previous_year"):
            year = anchor.year - (query.monthly == "previous_year")
            start, end = date(year, 1, 1), min(date(year, 12, 31), now.date())
        else:
            start, end = anchor.replace(day=1), anchor
            for _ in range((6 if query.monthly == "6m" else 12) - 1):
                start = previous_month(start)
        extra = previous_month(start)
        rows = self._rows(*local_period_bounds(extra, end))
        grouped = {}
        for row in rows:
            month = row["date"][:7]
            item = grouped.setdefault(month, {"revenue": 0.0, "orders": 0, "pizzas": 0})
            for key in ("revenue", "orders", "pizzas"):
                item[key] += row[key]
        result, cursor = [], start
        while cursor <= end:
            key = cursor.strftime("%Y-%m")
            values = grouped.get(key, {"revenue": 0, "orders": 0, "pizzas": 0})
            previous = grouped.get(previous_month(cursor).strftime("%Y-%m"))
            result.append({"month": key, **values, "revenue": round(values["revenue"], 2),
                "average_ticket": round(values["revenue"] / values["orders"], 2) if values["orders"] else 0,
                "growth_percent": variation(values["revenue"], previous["revenue"])["percent"] if previous else None,
                "partial": cursor.year == end.year and cursor.month == end.month and end.day < calendar.monthrange(end.year, end.month)[1]})
            cursor = (cursor.replace(day=28) + timedelta(days=4)).replace(day=1)
        return result

    def analytics(self, query: BIMobileQuery) -> dict:
        now = local_now()
        b = self.bounds(query, now)
        hourly = query.period == "today"
        rows = self._rows(b["start_dt"], b["end_dt"])
        totals = self._totals(b["start_dt"], b["end_dt"], rows, (b["end"] - b["start"]).days + 1)
        prev_rows = self._rows(b["previous_start_dt"], b["previous_end_dt"]) if b["previous_start"] else []
        prev_totals = self._totals(b["previous_start_dt"], b["previous_end_dt"], prev_rows,
            (b["previous_end"] - b["previous_start"]).days + 1) if b["previous_start"] else None
        current_series = self._rows(b["start_dt"], b["end_dt"], True) if hourly else rows
        previous_series = self._rows(b["previous_start_dt"], b["previous_end_dt"], True) if hourly and b["previous_start"] else prev_rows
        current_map = {r["date"]: r for r in current_series}
        previous_map = {r["date"]: r for r in previous_series}
        sales = []
        count = 24 if hourly else (b["end"] - b["start"]).days + 1
        for index in range(count):
            current_date = b["start"] if hourly else b["start"] + timedelta(days=index)
            previous_date = (b["previous_start"] if hourly else b["previous_start"] + timedelta(days=index)) if b["previous_start"] else None
            if previous_date and previous_date > b["previous_end"]:
                previous_date = None
            suffix = f" {index:02d}" if hourly else ""
            key = current_date.isoformat() + suffix
            previous_key = previous_date.isoformat() + suffix if previous_date else None
            current = current_map.get(key, {"revenue": 0, "orders": 0, "pizzas": 0})
            previous = previous_map.get(previous_key, {"revenue": 0, "orders": 0, "pizzas": 0}) if previous_key else None
            sales.append({"label": f"{index:02d}:00" if hourly else current_date.strftime("%d/%m"), "date": key,
                "previous_date": previous_key, **{k: current[k] for k in ("revenue", "orders", "pizzas")},
                **{f"previous_{k}": previous[k] if previous else None for k in ("revenue", "orders", "pizzas")},
                "comparison": {k: variation(current[k], previous[k]) for k in ("revenue", "orders", "pizzas")} if previous else {}})
        if query.grouping == "week" and not hourly:
            weekly = []
            for offset in range(0, len(sales), 7):
                points = sales[offset:offset + 7]
                point = {"date": points[0]["date"], "previous_date": points[0]["previous_date"],
                    "label": f"{points[0]['label']}–{points[-1]['label']}"}
                for key in ("revenue", "orders", "pizzas"):
                    point[key] = round(sum(item[key] for item in points), 2)
                    previous_values = [item[f"previous_{key}"] for item in points if item[f"previous_{key}"] is not None]
                    point[f"previous_{key}"] = round(sum(previous_values), 2) if previous_values else None
                point["comparison"] = {key: variation(point[key], point[f"previous_{key}"])
                    for key in ("revenue", "orders", "pizzas") if point[f"previous_{key}"] is not None}
                weekly.append(point)
            sales = weekly
        paid = self._paid()
        base = self.db.query(Order).filter(Order.tenant_id == self.tenant_id, Order.created_at >= b["start_dt"], Order.created_at <= b["end_dt"], paid)
        channels = [{"channel": channel or "unknown", "orders": int(count), "revenue": round(float(value), 2)}
            for channel, count, value in base.with_entities(Order.sales_channel, func.count(Order.id), func.sum(Order.total)).group_by(Order.sales_channel).all()]
        # A canonical payment is selected once per order, even in a corrupt
        # legacy database with duplicated payment rows.
        payment_id = select(func.min(Payment.id)).where(Payment.order_id == Order.id,
            Payment.tenant_id == self.tenant_id, Payment.status.in_(self.legacy.PAID_PAYMENT_STATUSES)).correlate(Order).scalar_subquery()
        payments = [{"method": getattr(method, "value", method), "orders": int(count), "revenue": round(float(value), 2)}
            for method, count, value in base.join(Payment, Payment.id == payment_id).with_entities(Payment.method, func.count(Order.id), func.sum(Order.total)).group_by(Payment.method).all()]
        first = self.db.query(func.min(Order.created_at)).filter(Order.tenant_id == self.tenant_id).scalar()
        payload = {"period": {"date_from": b["start"].isoformat(), "date_to": b["end"].isoformat(),
            "previous_date_from": b["previous_start"].isoformat() if b["previous_start"] else None,
            "previous_date_to": b["previous_end"].isoformat() if b["previous_end"] else None,
            "partial": b["partial"], "cutoff": now.isoformat() if b["partial"] else None,
            "timezone": "America/Sao_Paulo", "day_basis": "calendar", "granularity": "hour" if hourly else query.grouping,
            "comparison_rule": (
                "Fim no mesmo dia do mês anterior, limitado ao último dia existente; janelas móveis mantêm a duração."
                if query.compare == "previous_month" else
                "Período imediatamente anterior, com a mesma quantidade de dias."
                if query.compare == "previous_period" else "Sem comparação histórica selecionada."
            )},
            "totals": totals, "previous_totals": prev_totals,
            "comparison": {key: variation(totals[field], prev_totals[field]) for key, field in
                (("revenue", "revenue"), ("orders", "valid_orders"), ("pizzas", "pizzas"), ("average_ticket", "average_ticket"))} if prev_totals else {},
            "sales": sales, "monthly": self._monthly(query, now) if query.view in ("all", "general") else [],
            "attendance": self._attendance(b["start_dt"], b["end_dt"], now) if query.view in ("all", "attendance") else {}, "payments": payments, "channels": channels,
            "history": {"first_order_at": first.isoformat() if first else None, "status": "available" if first else "no_records",
                "note": "Histórico dos registros existentes; completude de importações externas não verificada."},
            "generated_at": now.isoformat(), "definitions": [
                "Receita confirmada: total dos pedidos com pagamento confirmado, excluindo cancelados e estornados; não é saldo bancário ou repasse.",
                "Pedidos nas séries e comparações são pedidos com pagamento confirmado; pedidos criados incluem todos os status.",
                "Pizzas: quantidades dos itens classificados pizza (ou categoria pizza em produtos legados sem tipo); sabores não multiplicam unidades.",
                "Combos consideram os produtos registrados no pedido. Produtos ausentes na composição histórica não são estimados.",
                "Taxas, subsídios e repasses externos indisponíveis não são estimados. Dias civis preservam o histórico existente.",
                "Ausência de registros não comprova completude de importação. Variação percentual sem base anterior é indisponível."]}
        return BIMobileAnalyticsOut.model_validate(payload).model_dump()

    def analyze(self, query: BIMobileQuery) -> dict:
        data = self.analytics(query)
        t = data["totals"]
        facts = [f"Receita confirmada de R$ {t['revenue']:.2f} em {t['valid_orders']} pedidos pagos.",
            f"{t['pizzas']} pizzas identificadas; ticket médio de R$ {t['average_ticket']:.2f}.",
            f"Média diária de R$ {t['daily_revenue']:.2f} e {t['daily_orders']:.2f} pedidos pagos."]
        if t["best_day"]:
            facts.append(f"Maior faturamento diário no período: {t['best_day']}.")
        b = self.bounds(query, local_now())
        daily_rows = self._rows(b["start_dt"], b["end_dt"])
        by_date = {row["date"]: row for row in daily_rows}
        dates = [b["start"] + timedelta(days=offset) for offset in range((b["end"] - b["start"]).days + 1)]
        if t["valid_orders"]:
            quietest = min(dates, key=lambda day: by_date.get(day.isoformat(), {}).get("revenue", 0))
            quiet_revenue = by_date.get(quietest.isoformat(), {}).get("revenue", 0)
            facts.append(f"Menor faturamento diário nos registros do período: {quietest.isoformat()}, R$ {quiet_revenue:.2f}.")
        hour_totals = {}
        for row in self._rows(b["start_dt"], b["end_dt"], hourly=True):
            hour = row["date"][-2:]
            hour_totals[hour] = hour_totals.get(hour, 0) + row["orders"]
        if hour_totals and max(hour_totals.values()):
            hour = max(hour_totals, key=hour_totals.get)
            facts.append(f"Horário com maior volume no período: {hour}:00–{hour}:59, com {hour_totals[hour]} pedidos pagos.")
        change = data["comparison"].get("revenue", {}).get("percent")
        trends = [f"Variação da receita frente à janela identificada: {change:.2f}%."] if change is not None else []
        for metric, label in (("orders", "pedidos pagos"), ("average_ticket", "ticket médio")):
            delta = data["comparison"].get(metric, {}).get("percent")
            if delta is not None:
                trends.append(f"Variação de {label} frente à janela identificada: {delta:.2f}%.")
        attention = ["Valores representam pedidos confirmados; recebimento bancário e repasses não foram conciliados."]
        if not t["valid_orders"]:
            attention.append("Nenhum pedido pago encontrado na janela; confirme a disponibilidade do histórico e das integrações.")
        if data["period"]["partial"]:
            attention.append("Período parcial: comparação limitada ao mesmo horário local.")
        eligible = {}
        if t["cancelled_orders"]:
            eligible["review_cancellations"] = "Revisar os motivos dos cancelamentos antes de definir ações comerciais."
        if change is not None and change < 0:
            eligible["review_channels"] = "Investigar canais e horários com menor movimento antes de testar campanhas."
        if t["valid_orders"]:
            eligible["plan_peak"] = "Conferir capacidade operacional nos horários de maior movimento."
            if len(dates) > 1:
                eligible["review_quiet_days"] = "Avaliar os dias de menor faturamento e testar ações comerciais com acompanhamento dos resultados."
        ticket_delta = data["comparison"].get("average_ticket", {}).get("percent")
        if ticket_delta is not None and ticket_delta < 0:
            eligible["protect_ticket"] = "Revisar descontos e composição dos pedidos para entender a redução do ticket médio."
        recommendations, engine, ai_note = self._prioritize_recommendations(data, eligible)
        return BIMobileAnalysisOut(generated_at=data["generated_at"], period=data["period"],
            engine=engine, ai_note=ai_note,
            summary=f"{t['valid_orders']} pedidos pagos e receita confirmada de R$ {t['revenue']:.2f} no período selecionado.",
            facts=facts, trends=trends, attention=attention, recommendations=recommendations).model_dump()

    def _prioritize_recommendations(self, data: dict, eligible: dict[str, str]) -> tuple[list[str], str, str]:
        """AI may order known actions; it can never supply displayed facts or prose."""
        fallback = (list(eligible.values()), "calculated", "IA indisponível ou inativa; recomendações baseadas em regras calculadas.")
        if not eligible:
            return fallback
        from backend.models.chatbot import ChatbotSettings
        from backend.services.ai.base import AIMessage
        from backend.services.ai.factory import get_ai_provider
        settings = self.db.query(ChatbotSettings).filter(ChatbotSettings.tenant_id == self.tenant_id).first()
        if settings is None or not settings.ativo or not settings.ia_ativo:
            return fallback
        try:
            provider = get_ai_provider(settings)
            if not provider.is_configured():
                return fallback
            # Only aggregate numbers and static action labels leave this service.
            payload = {"period": data["period"], "totals": data["totals"],
                       "comparison": data["comparison"], "eligible_actions": eligible}
            response = provider.generate(
                system_prompt="Priorize as ações gerenciais fornecidas pelos indicadores agregados. Responda somente JSON com recommendation_ids: lista de todos os IDs recebidos, sem repetir, na ordem de prioridade. Não crie IDs, textos, valores ou conclusões.",
                messages=[AIMessage(role="user", content=json.dumps(payload, ensure_ascii=False))],
                temperatura=0, max_tokens=256,
            )
            if response.error_reason:
                return fallback
            ordered = json.loads(response.content).get("recommendation_ids")
            if (not isinstance(ordered, list) or not all(isinstance(key, str) for key in ordered)
                    or len(ordered) != len(eligible) or set(ordered) != set(eligible)):
                return fallback
            return ([eligible[key] for key in ordered], "ai_assisted",
                    "IA priorizou recomendações previamente validadas. Todos os fatos e números foram calculados pelo sistema.")
        except Exception:
            # Provider errors and untrusted output cannot contaminate BI results.
            return fallback
