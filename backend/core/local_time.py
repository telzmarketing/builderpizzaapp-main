from __future__ import annotations

from datetime import date, datetime, time, timezone
from zoneinfo import ZoneInfo

STORE_TIMEZONE = ZoneInfo("America/Sao_Paulo")


def local_now() -> datetime:
    return datetime.now(timezone.utc).astimezone(STORE_TIMEZONE)


def local_today() -> date:
    return local_now().date()


def local_day_bounds(target_date: date) -> tuple[datetime, datetime]:
    start_local = datetime.combine(target_date, time.min, tzinfo=STORE_TIMEZONE)
    end_local = datetime.combine(target_date, time.max, tzinfo=STORE_TIMEZONE)
    return start_local.astimezone(timezone.utc), end_local.astimezone(timezone.utc)


def local_period_bounds(start_date: date, end_date: date) -> tuple[datetime, datetime]:
    start_dt, _ = local_day_bounds(start_date)
    _, end_dt = local_day_bounds(end_date)
    return start_dt, end_dt


def to_store_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(STORE_TIMEZONE)
