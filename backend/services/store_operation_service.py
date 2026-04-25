from __future__ import annotations

import json
import uuid
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session, joinedload

from backend.core.exceptions import DomainError
from backend.models.admin import AdminUser
from backend.models.store_operation import (
    StoreOperationException,
    StoreOperationInterval,
    StoreOperationLog,
    StoreOperationSettings,
    StoreWeeklySchedule,
)
from backend.schemas.store_operation import (
    StoreOperationExceptionIn,
    StoreOperationSettingsIn,
    StoreWeeklyScheduleIn,
)

TENANT_ID = "default"


class StoreClosed(DomainError):
    http_status = 423

    def __init__(self, message: str):
        super().__init__(message, code="StoreClosed")


class StoreOperationService:
    def __init__(self, db: Session, tenant_id: str = TENANT_ID):
        self._db = db
        self._tenant_id = tenant_id

    def get_config(self) -> dict:
        settings = self._settings()
        schedules = self._schedules()
        exceptions = (
            self._db.query(StoreOperationException)
            .filter(StoreOperationException.tenant_id == self._tenant_id)
            .order_by(StoreOperationException.date.desc())
            .all()
        )
        return {"settings": settings, "weekly_schedules": schedules, "exceptions": exceptions}

    def get_status(self, now: datetime | None = None) -> dict:
        settings = self._settings()
        current = self._localized_now(settings, now)
        is_open, mode, message = self._is_open_at(current, settings)
        next_opening = None if is_open else self._next_opening_after(current, settings)
        return {
            "is_open": is_open,
            "mode": settings.manual_mode,
            "status_label": "Aberto agora" if is_open else "Fechado agora",
            "message": message,
            "current_weekday": current.weekday(),
            "today_hours": self._hours_label(current.date()),
            "next_opening_at": next_opening,
            "next_opening_label": self._opening_label(next_opening) if next_opening else None,
            "allow_scheduled_orders": settings.allow_scheduled_orders,
        }

    def validate_order_allowed(
        self,
        *,
        is_scheduled: bool = False,
        scheduled_for: datetime | None = None,
    ) -> None:
        status = self.get_status()
        if status["is_open"] and not is_scheduled:
            return

        settings = self._settings()
        if is_scheduled:
            if not settings.allow_scheduled_orders:
                raise StoreClosed(self._closed_message(status))
            if not scheduled_for:
                raise StoreClosed("Informe um horario futuro disponivel para agendar o pedido.")
            current = self._localized_now(settings)
            schedule_dt = scheduled_for if scheduled_for.tzinfo else scheduled_for.replace(tzinfo=ZoneInfo(settings.timezone))
            schedule_dt = schedule_dt.astimezone(ZoneInfo(settings.timezone))
            if schedule_dt <= current:
                raise StoreClosed("O horario agendado precisa ser futuro.")
            is_open, _, _ = self._is_open_at(schedule_dt, settings, ignore_manual=True)
            if not is_open:
                next_opening = self._next_opening_after(current, settings)
                label = self._opening_label(next_opening) if next_opening else "proximo horario disponivel"
                raise StoreClosed(f"Horario indisponivel para agendamento. Pedidos disponiveis a partir de {label}.")
            return

        if settings.allow_scheduled_orders:
            raise StoreClosed(self._closed_message(status) + " Voce pode agendar para um horario futuro disponivel.")
        raise StoreClosed(self._closed_message(status))

    def update_settings(self, payload: StoreOperationSettingsIn, admin: AdminUser) -> StoreOperationSettings:
        settings = self._settings()
        old = self._serialize_settings(settings)
        for key, value in payload.model_dump().items():
            setattr(settings, key, value)
        self._log(admin, "update", "settings", settings.id, old, payload.model_dump())
        self._db.commit()
        self._db.refresh(settings)
        return settings

    def replace_weekly_schedules(self, payload: list[StoreWeeklyScheduleIn], admin: AdminUser) -> list[StoreWeeklySchedule]:
        old = [self._serialize_schedule(schedule) for schedule in self._schedules()]
        self._db.query(StoreOperationInterval).filter(StoreOperationInterval.tenant_id == self._tenant_id).delete(synchronize_session=False)
        self._db.query(StoreWeeklySchedule).filter(StoreWeeklySchedule.tenant_id == self._tenant_id).delete(synchronize_session=False)
        for item in payload:
            schedule = StoreWeeklySchedule(
                id=f"store-day-{uuid.uuid4().hex[:10]}",
                tenant_id=self._tenant_id,
                weekday=item.weekday,
                active=item.active,
            )
            self._db.add(schedule)
            self._db.flush()
            for interval in item.intervals:
                self._db.add(StoreOperationInterval(
                    id=f"store-int-{uuid.uuid4().hex[:10]}",
                    schedule_id=schedule.id,
                    tenant_id=self._tenant_id,
                    open_time=interval.open_time,
                    close_time=interval.close_time,
                ))
        self._log(admin, "replace", "weekly_schedules", None, old, [item.model_dump(mode="json") for item in payload])
        self._db.commit()
        return self._schedules()

    def create_exception(self, payload: StoreOperationExceptionIn, admin: AdminUser) -> StoreOperationException:
        self._validate_exception(payload)
        item = StoreOperationException(
            id=f"store-exc-{uuid.uuid4().hex[:10]}",
            tenant_id=self._tenant_id,
            **payload.model_dump(),
        )
        self._db.add(item)
        self._log(admin, "create", "exception", item.id, None, payload.model_dump(mode="json"))
        self._db.commit()
        self._db.refresh(item)
        return item

    def update_exception(self, exception_id: str, payload: StoreOperationExceptionIn, admin: AdminUser) -> StoreOperationException:
        self._validate_exception(payload)
        item = self._exception(exception_id)
        old = self._serialize_exception(item)
        for key, value in payload.model_dump().items():
            setattr(item, key, value)
        self._log(admin, "update", "exception", item.id, old, payload.model_dump(mode="json"))
        self._db.commit()
        self._db.refresh(item)
        return item

    def delete_exception(self, exception_id: str, admin: AdminUser) -> None:
        item = self._exception(exception_id)
        old = self._serialize_exception(item)
        self._db.delete(item)
        self._log(admin, "delete", "exception", exception_id, old, None)
        self._db.commit()

    def list_logs(self, limit: int = 100) -> list[StoreOperationLog]:
        return (
            self._db.query(StoreOperationLog)
            .filter(StoreOperationLog.tenant_id == self._tenant_id)
            .order_by(StoreOperationLog.created_at.desc())
            .limit(limit)
            .all()
        )

    def _settings(self) -> StoreOperationSettings:
        settings = (
            self._db.query(StoreOperationSettings)
            .filter(StoreOperationSettings.tenant_id == self._tenant_id)
            .first()
        )
        if settings:
            return settings
        settings = StoreOperationSettings(id="default", tenant_id=self._tenant_id)
        self._db.add(settings)
        self._db.flush()
        for weekday in range(7):
            schedule = StoreWeeklySchedule(
                id=f"store-day-{uuid.uuid4().hex[:10]}",
                tenant_id=self._tenant_id,
                weekday=weekday,
                active=True,
            )
            self._db.add(schedule)
            self._db.flush()
            self._db.add(StoreOperationInterval(
                id=f"store-int-{uuid.uuid4().hex[:10]}",
                tenant_id=self._tenant_id,
                schedule_id=schedule.id,
                open_time=time(18, 0),
                close_time=time(23, 30),
            ))
        self._db.commit()
        return settings

    def _schedules(self) -> list[StoreWeeklySchedule]:
        self._settings()
        return (
            self._db.query(StoreWeeklySchedule)
            .options(joinedload(StoreWeeklySchedule.intervals))
            .filter(StoreWeeklySchedule.tenant_id == self._tenant_id)
            .order_by(StoreWeeklySchedule.weekday)
            .all()
        )

    def _exception(self, exception_id: str) -> StoreOperationException:
        item = (
            self._db.query(StoreOperationException)
            .filter(StoreOperationException.id == exception_id, StoreOperationException.tenant_id == self._tenant_id)
            .first()
        )
        if not item:
            raise DomainError("Excecao de funcionamento nao encontrada.", code="StoreOperationExceptionNotFound")
        return item

    def _localized_now(self, settings: StoreOperationSettings, now: datetime | None = None) -> datetime:
        zone = ZoneInfo(settings.timezone or "America/Sao_Paulo")
        if now is None:
            return datetime.now(zone)
        if now.tzinfo is None:
            return now.replace(tzinfo=zone)
        return now.astimezone(zone)

    def _is_open_at(
        self,
        current: datetime,
        settings: StoreOperationSettings,
        *,
        ignore_manual: bool = False,
    ) -> tuple[bool, str, str]:
        if not ignore_manual:
            if settings.manual_mode == "manual_open":
                return True, "manual_open", "Loja aberta manualmente."
            if settings.manual_mode == "manual_closed":
                return False, "manual_closed", settings.closed_message

        day_exception = self._exception_for_date(current.date())
        if day_exception:
            if day_exception.exception_type == "closed":
                return False, "exception_closed", settings.closed_message
            if day_exception.open_time and day_exception.close_time and self._time_in_interval(current.time(), day_exception.open_time, day_exception.close_time):
                return True, "exception_special_hours", "Loja aberta em horario especial."
            return False, "exception_special_hours", settings.closed_message

        if self._date_has_open_interval(current):
            return True, "auto", "Loja aberta conforme horario de funcionamento."
        return False, "auto", settings.closed_message

    def _date_has_open_interval(self, current: datetime) -> bool:
        schedules = {schedule.weekday: schedule for schedule in self._schedules()}
        today = schedules.get(current.weekday())
        if today and today.active and any(self._time_in_interval(current.time(), item.open_time, item.close_time) for item in today.intervals):
            return True

        yesterday = schedules.get((current.weekday() - 1) % 7)
        if not yesterday or not yesterday.active:
            return False
        return any(item.open_time > item.close_time and current.time() <= item.close_time for item in yesterday.intervals)

    def _next_opening_after(self, current: datetime, settings: StoreOperationSettings) -> datetime | None:
        if settings.manual_mode == "manual_closed":
            return None
        zone = ZoneInfo(settings.timezone or "America/Sao_Paulo")
        start = current.astimezone(zone)
        for offset in range(0, 15):
            candidate_date = start.date() + timedelta(days=offset)
            openings = self._openings_for_date(candidate_date)
            for opening in openings:
                opening_dt = datetime.combine(candidate_date, opening, tzinfo=zone)
                if opening_dt > start:
                    return opening_dt
        return None

    def _openings_for_date(self, target_date: date) -> list[time]:
        day_exception = self._exception_for_date(target_date)
        if day_exception:
            if day_exception.exception_type == "closed":
                return []
            return [day_exception.open_time] if day_exception.open_time else []
        schedules = {schedule.weekday: schedule for schedule in self._schedules()}
        schedule = schedules.get(target_date.weekday())
        if not schedule or not schedule.active:
            return []
        return sorted(item.open_time for item in schedule.intervals)

    def _hours_label(self, target_date: date) -> str:
        day_exception = self._exception_for_date(target_date)
        if day_exception:
            if day_exception.exception_type == "closed":
                return "Fechado"
            if day_exception.open_time and day_exception.close_time:
                return f"{self._fmt_time(day_exception.open_time)} as {self._fmt_time(day_exception.close_time)}"
        schedules = {schedule.weekday: schedule for schedule in self._schedules()}
        schedule = schedules.get(target_date.weekday())
        if not schedule or not schedule.active or not schedule.intervals:
            return "Fechado"
        return " / ".join(f"{self._fmt_time(item.open_time)} as {self._fmt_time(item.close_time)}" for item in schedule.intervals)

    def _exception_for_date(self, target_date: date) -> StoreOperationException | None:
        return (
            self._db.query(StoreOperationException)
            .filter(StoreOperationException.tenant_id == self._tenant_id, StoreOperationException.date == target_date)
            .first()
        )

    def _time_in_interval(self, current: time, open_time: time, close_time: time) -> bool:
        if open_time <= close_time:
            return open_time <= current <= close_time
        return current >= open_time or current <= close_time

    def _opening_label(self, opening: datetime | None) -> str | None:
        if not opening:
            return None
        now = datetime.now(opening.tzinfo)
        prefix = "hoje" if opening.date() == now.date() else "amanha" if opening.date() == (now.date() + timedelta(days=1)) else opening.strftime("%d/%m")
        return f"{prefix} as {opening.strftime('%H:%M')}"

    def _closed_message(self, status: dict) -> str:
        if status.get("next_opening_label"):
            return f"Loja fechada no momento. Pedidos disponiveis a partir de {status['next_opening_label']}."
        return status.get("message") or "Loja fechada no momento."

    def _validate_exception(self, payload: StoreOperationExceptionIn) -> None:
        if payload.exception_type == "special_hours" and (not payload.open_time or not payload.close_time):
            raise DomainError("Informe abertura e fechamento para horario especial.", code="InvalidStoreOperationException")

    def _log(self, admin: AdminUser, action: str, entity: str, entity_id: str | None, old_value, new_value) -> None:
        self._db.add(StoreOperationLog(
            id=f"store-log-{uuid.uuid4().hex[:10]}",
            tenant_id=self._tenant_id,
            admin_id=admin.id,
            admin_email=admin.email,
            action=action,
            entity=entity,
            entity_id=entity_id,
            old_value=json.dumps(old_value, default=str, ensure_ascii=False) if old_value is not None else None,
            new_value=json.dumps(new_value, default=str, ensure_ascii=False) if new_value is not None else None,
        ))

    def _serialize_settings(self, item: StoreOperationSettings) -> dict:
        return {
            "manual_mode": item.manual_mode,
            "closed_message": item.closed_message,
            "allow_scheduled_orders": item.allow_scheduled_orders,
            "timezone": item.timezone,
        }

    def _serialize_schedule(self, item: StoreWeeklySchedule) -> dict:
        return {
            "weekday": item.weekday,
            "active": item.active,
            "intervals": [
                {"open_time": interval.open_time.isoformat(), "close_time": interval.close_time.isoformat()}
                for interval in item.intervals
            ],
        }

    def _serialize_exception(self, item: StoreOperationException) -> dict:
        return {
            "date": item.date.isoformat(),
            "exception_type": item.exception_type,
            "open_time": item.open_time.isoformat() if item.open_time else None,
            "close_time": item.close_time.isoformat() if item.close_time else None,
            "reason": item.reason,
        }

    def _fmt_time(self, value: time) -> str:
        return value.strftime("%H:%M")
