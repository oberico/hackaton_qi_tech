from typing import Optional

from src.engine import policy
from src.engine.clock import is_within_hours, local_datetime
from src.engine.risk_context import RiskContext


def night_limit(context: RiskContext) -> Optional[int]:
    return policy.NIGHT_LIMIT_MINOR[context.transaction.flow]


def night_amount(context: RiskContext) -> Optional[int]:
    in_night = is_within_hours(local_datetime(context).hour, policy.NIGHT_START_HOUR, policy.NIGHT_END_HOUR)
    if night_limit(context) is None or context.transaction.same_owner or not in_night:
        return None
    return context.payer.night_amount_to_individuals + context.transaction.amount
