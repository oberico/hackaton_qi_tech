from typing import List

from src.engine import policy
from src.engine.risk_context import EvaluatedRule, RiskContext, RiskLevel
from src.engine.rules import fired, not_fired

AXIS = "where"

DESTINATION_NEW_ACCOUNT_CODE = "WHERE_DESTINATION_NEW_ACCOUNT"
DESTINATION_NEW_ACCOUNT_DESCRIPTION = "Destination account opened less than 30 days ago."
DESTINATION_NEW_ACCOUNT_TRANSLATION = "Conta de destino aberta há menos de 30 dias."

DESTINATION_FAN_IN_CODE = "WHERE_DESTINATION_FAN_IN"
DESTINATION_FAN_IN_DESCRIPTION = "Destination account opened less than 30 days ago received from many distinct payers in the last 24 hours."
DESTINATION_FAN_IN_TRANSLATION = "Conta de destino aberta há menos de 30 dias recebeu de muitos pagadores distintos nas últimas 24 horas."

UNKNOWN_PARTICIPANT_CODE = "WHERE_UNKNOWN_PARTICIPANT"
UNKNOWN_PARTICIPANT_DESCRIPTION = "Destination participant (ISPB) is not on the BCB STR participant list."
UNKNOWN_PARTICIPANT_TRANSLATION = "Participante de destino (ISPB) fora da lista de participantes do STR do BCB."


def destination_new_account(context: RiskContext) -> EvaluatedRule:
    observed = {"destination_account_age_days": context.transaction.destination_account_age_days}
    threshold = {"destination_account_age_days": policy.DESTINATION_NEW_ACCOUNT_DAYS}
    if context.transaction.destination_account_age_days < policy.DESTINATION_NEW_ACCOUNT_DAYS:
        return fired(
            DESTINATION_NEW_ACCOUNT_CODE,
            AXIS,
            RiskLevel.SUSPICIOUS,
            observed,
            threshold,
            DESTINATION_NEW_ACCOUNT_DESCRIPTION,
            DESTINATION_NEW_ACCOUNT_TRANSLATION,
        )
    return not_fired(DESTINATION_NEW_ACCOUNT_CODE, AXIS, DESTINATION_NEW_ACCOUNT_DESCRIPTION, DESTINATION_NEW_ACCOUNT_TRANSLATION, observed, threshold)


def destination_fan_in(context: RiskContext) -> EvaluatedRule:
    payers_threshold = policy.FAN_IN_CRITICAL_PAYERS_24H[context.transaction.flow]
    observed = {
        "distinct_payers_24h": context.destination.distinct_payers_24h,
        "destination_account_age_days": context.transaction.destination_account_age_days,
    }
    threshold = {"distinct_payers_24h": payers_threshold, "destination_account_age_days": policy.DESTINATION_NEW_ACCOUNT_DAYS}
    is_new_destination = context.transaction.destination_account_age_days < policy.DESTINATION_NEW_ACCOUNT_DAYS
    if is_new_destination and context.destination.distinct_payers_24h >= payers_threshold:
        return fired(
            DESTINATION_FAN_IN_CODE, AXIS, RiskLevel.CRITICAL, observed, threshold, DESTINATION_FAN_IN_DESCRIPTION, DESTINATION_FAN_IN_TRANSLATION
        )
    return not_fired(DESTINATION_FAN_IN_CODE, AXIS, DESTINATION_FAN_IN_DESCRIPTION, DESTINATION_FAN_IN_TRANSLATION, observed, threshold)


def unknown_participant(context: RiskContext) -> EvaluatedRule:
    observed = {"destination_participant_listed": context.transaction.destination_participant_listed}
    threshold = {"destination_participant_listed": True}
    if not context.transaction.destination_participant_listed:
        return fired(
            UNKNOWN_PARTICIPANT_CODE,
            AXIS,
            RiskLevel.SUSPICIOUS,
            observed,
            threshold,
            UNKNOWN_PARTICIPANT_DESCRIPTION,
            UNKNOWN_PARTICIPANT_TRANSLATION,
        )
    return not_fired(UNKNOWN_PARTICIPANT_CODE, AXIS, UNKNOWN_PARTICIPANT_DESCRIPTION, UNKNOWN_PARTICIPANT_TRANSLATION, observed, threshold)


RULES = (destination_new_account, unknown_participant, destination_fan_in)


def analyze(context: RiskContext) -> List[EvaluatedRule]:
    return [rule(context) for rule in RULES]
