from datetime import datetime, timedelta, timezone

from src.engine.risk_context import RiskContext


def local_datetime(context: RiskContext) -> datetime:
    zone = timezone(timedelta(minutes=context.transaction.utc_offset_minutes))
    return context.transaction.transaction_date.astimezone(zone)


def is_within_hours(hour: int, start_hour: int, end_hour: int) -> bool:
    if start_hour <= end_hour:
        return start_hour <= hour < end_hour
    return hour >= start_hour or hour < end_hour
