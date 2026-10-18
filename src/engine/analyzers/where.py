from typing import List

from src.engine.risk_context import EvaluatedRule, RiskContext, RiskLevel
from src.engine.rules import fired, not_fired

AXIS = "where"

UNKNOWN_PARTICIPANT_CODE = "WHERE_UNKNOWN_PARTICIPANT"
UNKNOWN_PARTICIPANT_DESCRIPTION = "Destination participant (ISPB) is not on the BCB STR participant list."
UNKNOWN_PARTICIPANT_TRANSLATION = "Participante de destino (ISPB) fora da lista de participantes do STR do BCB."


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


RULES = (unknown_participant,)


def analyze(context: RiskContext) -> List[EvaluatedRule]:
    return [rule(context) for rule in RULES]
