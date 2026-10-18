from typing import List

from src.engine import policy
from src.engine.clock import is_within_hours, local_datetime
from src.engine.risk_context import EvaluatedRule, RiskContext, RiskLevel
from src.engine.rules import fired, not_fired

AXIS = "how"

NIGHT_LIMIT_CODE = "HOW_NIGHT_LIMIT_EXCEEDED"
NIGHT_LIMIT_DESCRIPTION = "Night-time amount between individuals above R$ 1,000."
NIGHT_LIMIT_TRANSLATION = "Soma noturna entre pessoas físicas acima de R$ 1.000."


def night_limit_exceeded(context: RiskContext) -> EvaluatedRule:
    limit = policy.NIGHT_LIMIT_MINOR[context.transaction.flow]
    in_night = is_within_hours(local_datetime(context).hour, policy.NIGHT_START_HOUR, policy.NIGHT_END_HOUR)
    if limit is None or context.transaction.same_owner or not in_night:
        return not_fired(NIGHT_LIMIT_CODE, AXIS, NIGHT_LIMIT_DESCRIPTION, NIGHT_LIMIT_TRANSLATION)
    night_amount = context.payer.night_amount_to_individuals + context.transaction.amount
    observed = {"night_amount": night_amount}
    threshold = {"night_amount": limit}
    if night_amount > limit:
        return fired(NIGHT_LIMIT_CODE, AXIS, RiskLevel.SUSPICIOUS, observed, threshold, NIGHT_LIMIT_DESCRIPTION, NIGHT_LIMIT_TRANSLATION)
    return not_fired(NIGHT_LIMIT_CODE, AXIS, NIGHT_LIMIT_DESCRIPTION, NIGHT_LIMIT_TRANSLATION, observed, threshold)


RULES = (night_limit_exceeded,)


def analyze(context: RiskContext) -> List[EvaluatedRule]:
    return [rule(context) for rule in RULES]
