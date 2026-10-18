from typing import List

from src.engine import policy
from src.engine.risk_context import EvaluatedRule, RiskContext, RiskLevel
from src.engine.rules import fired, not_fired

AXIS = "where"
AGE_DECIMALS = 2

DESTINATION_NEW_ACCOUNT_CODE = "WHERE_DESTINATION_NEW_ACCOUNT"
DESTINATION_NEW_ACCOUNT_DESCRIPTION = "Destination account opened less than {days} days ago."
DESTINATION_NEW_ACCOUNT_TRANSLATION = "Conta de destino aberta há menos de {days} dias."

UNKNOWN_PARTICIPANT_CODE = "WHERE_UNKNOWN_PARTICIPANT"
UNKNOWN_PARTICIPANT_DESCRIPTION = "Destination participant (ISPB) is not on the BCB STR participant list."
UNKNOWN_PARTICIPANT_TRANSLATION = "Participante de destino (ISPB) fora da lista de participantes do STR do BCB."


def destination_new_account(context: RiskContext) -> EvaluatedRule:
    age_days = context.transaction.destination_account_age_days
    observed = {"destination_account_age_days": round(age_days, AGE_DECIMALS)}
    threshold = {"destination_account_age_days": policy.DESTINATION_NEW_ACCOUNT_DAYS}
    description = DESTINATION_NEW_ACCOUNT_DESCRIPTION.format(days=policy.DESTINATION_NEW_ACCOUNT_DAYS)
    translation = DESTINATION_NEW_ACCOUNT_TRANSLATION.format(days=policy.DESTINATION_NEW_ACCOUNT_DAYS)
    if age_days < policy.DESTINATION_NEW_ACCOUNT_DAYS:
        return fired(DESTINATION_NEW_ACCOUNT_CODE, AXIS, RiskLevel.SUSPICIOUS, observed, threshold, description, translation)
    return not_fired(DESTINATION_NEW_ACCOUNT_CODE, AXIS, description, translation, observed, threshold)


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


RULES = (destination_new_account, unknown_participant)


def analyze(context: RiskContext) -> List[EvaluatedRule]:
    return [rule(context) for rule in RULES]
