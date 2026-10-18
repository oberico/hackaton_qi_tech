from typing import List

from src.engine import night, policy
from src.engine.risk_context import EvaluatedRule, RiskContext, RiskLevel
from src.engine.rules import fired, not_fired

AXIS = "how"

NIGHT_LIMIT_CODE = "HOW_NIGHT_LIMIT_EXCEEDED"
NIGHT_LIMIT_DESCRIPTION = "Night-time amount between individuals above R$ 1,000."
NIGHT_LIMIT_TRANSLATION = "Soma noturna entre pessoas físicas acima de R$ 1.000."

VELOCITY_CODE = "HOW_VELOCITY_EXCEEDED"
VELOCITY_DESCRIPTION = "Payer attempts in the last 10 minutes at or above the limit for the flow."
VELOCITY_TRANSLATION = "Tentativas do pagador nos últimos 10 minutos iguais ou acima do limite do fluxo."


def night_limit_exceeded(context: RiskContext) -> EvaluatedRule:
    night_amount = night.night_amount(context)
    if night_amount is None:
        return not_fired(NIGHT_LIMIT_CODE, AXIS, NIGHT_LIMIT_DESCRIPTION, NIGHT_LIMIT_TRANSLATION)
    observed = {"night_amount": night_amount}
    threshold = {"night_amount": night.night_limit(context)}
    if night_amount > threshold["night_amount"]:
        return fired(NIGHT_LIMIT_CODE, AXIS, RiskLevel.SUSPICIOUS, observed, threshold, NIGHT_LIMIT_DESCRIPTION, NIGHT_LIMIT_TRANSLATION)
    return not_fired(NIGHT_LIMIT_CODE, AXIS, NIGHT_LIMIT_DESCRIPTION, NIGHT_LIMIT_TRANSLATION, observed, threshold)


def velocity_exceeded(context: RiskContext) -> EvaluatedRule:
    observed = {"attempts": context.payer.transactions_last_10min}
    threshold = policy.VELOCITY_10MIN[context.transaction.flow]
    if observed["attempts"] >= threshold["critical"]:
        level = RiskLevel.CRITICAL
    elif observed["attempts"] >= threshold["suspicious"]:
        level = RiskLevel.SUSPICIOUS
    else:
        return not_fired(VELOCITY_CODE, AXIS, VELOCITY_DESCRIPTION, VELOCITY_TRANSLATION, observed, threshold)
    return fired(VELOCITY_CODE, AXIS, level, observed, threshold, VELOCITY_DESCRIPTION, VELOCITY_TRANSLATION)


RULES = (night_limit_exceeded, velocity_exceeded)


def analyze(context: RiskContext) -> List[EvaluatedRule]:
    return [rule(context) for rule in RULES]
