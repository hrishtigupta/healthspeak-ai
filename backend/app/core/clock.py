"""Time helpers: store UTC, think in the hospital's local time."""

from datetime import UTC, date, datetime
from functools import lru_cache
from zoneinfo import ZoneInfo

from app.core.config import get_settings


@lru_cache
def hospital_tz() -> ZoneInfo:
    return ZoneInfo(get_settings().hospital_timezone)


def now_utc() -> datetime:
    return datetime.now(UTC)


def local_today() -> date:
    return datetime.now(hospital_tz()).date()


def local_day_bounds_utc(day: date) -> tuple[datetime, datetime]:
    """UTC start/end of a hospital-local calendar day."""
    tz = hospital_tz()
    start = datetime(day.year, day.month, day.day, tzinfo=tz)
    end = datetime.fromordinal(day.toordinal() + 1).replace(tzinfo=tz)
    return start.astimezone(UTC), end.astimezone(UTC)
