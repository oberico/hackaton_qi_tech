from typing import List

from src.engine import night
from src.engine.risk_context import EvaluatedRule, RiskContext, RiskLevel
from src.engine.rules import fired, not_fired

AXIS = "how"

NIGHT_LIMIT_CODE = "HOW_NIGHT_LIMIT_EXCEEDED"
NIGHT_LIMIT_DESCRIPTION = "Night-time amount between individuals above R$ 1,000."
NIGHT_LIMIT_TRANSLATION = "Soma noturna entre pessoas físicas acima de R$ 1.000."


def night_limit_exceeded(context: RiskContext) -> EvaluatedRule:
    night_amount = night.night_amount(context)
    if night_amount is None:
        return not_fired(NIGHT_LIMIT_CODE, AXIS, NIGHT_LIMIT_DESCRIPTION, NIGHT_LIMIT_TRANSLATION)
    observed = {"night_amount": night_amount}
    threshold = {"night_amount": night.night_limit(context)}
    if night_amount > threshold["night_amount"]:
        return fired(NIGHT_LIMIT_CODE, AXIS, RiskLevel.SUSPICIOUS, observed, threshold, NIGHT_LIMIT_DESCRIPTION, NIGHT_LIMIT_TRANSLATION)
    return not_fired(NIGHT_LIMIT_CODE, AXIS, NIGHT_LIMIT_DESCRIPTION, NIGHT_LIMIT_TRANSLATION, observed, threshold)


RULES = (night_limit_exceeded,)


def analyze(context: RiskContext) -> List[EvaluatedRule]:
    return [rule(context) for rule in RULES]
