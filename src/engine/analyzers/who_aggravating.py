from src.engine import policy
from src.engine.risk_context import EvaluatedRule, RiskContext, RiskLevel
from src.engine.rules import fired, not_fired

AXIS = "who"
CODE = "WHO_AGGRAVATING_SIGNALS"
DESCRIPTION = "Two or more aggravating signals on who axis (IP with many payers, private IP, new channel)."
TRANSLATION = "Dois ou mais sinais agravantes no eixo who (IP com muitos pagadores, IP privado, canal novo)."


def evaluate_aggravating_signals(context: RiskContext) -> EvaluatedRule:
    ip_many_payers = context.ip.distinct_payers_1h >= policy.WHO_AGGRAVATING_IP_DISTINCT_PAYERS_1H
    ip_is_private = bool(context.transaction.ip_is_private)
    has_payer_history = context.payer.approved_count > 0
    new_channel = bool(has_payer_history and context.transaction.channel not in context.payer.known_channels)

    signals = [ip_many_payers, ip_is_private, new_channel]
    signals_count = sum(signals)

    observed = {
        "signals_count": signals_count,
        "distinct_payers_1h": context.ip.distinct_payers_1h,
        "ip_is_private": ip_is_private,
        "new_channel": new_channel,
    }
    threshold = {
        "min_signals": policy.WHO_AGGRAVATING_MIN_SIGNALS,
        "ip_distinct_payers_1h": policy.WHO_AGGRAVATING_IP_DISTINCT_PAYERS_1H,
    }

    if signals_count >= policy.WHO_AGGRAVATING_MIN_SIGNALS:
        return fired(
            CODE, AXIS, RiskLevel.SUSPICIOUS, observed, threshold, DESCRIPTION, TRANSLATION
        )
    return not_fired(
        CODE, AXIS, DESCRIPTION, TRANSLATION, observed, threshold
    )
