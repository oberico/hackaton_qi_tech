from typing import List

from src.engine import policy
from src.engine.risk_context import DeviceTrust, EvaluatedRule, RiskContext, RiskLevel
from src.engine.rules import fired, not_fired

AXIS = "who"

DEVICE_COMPROMISED_CODE = "WHO_DEVICE_COMPROMISED"
DEVICE_COMPROMISED_DESCRIPTION = "Device used by several distinct account holders in total or within 24 hours."
DEVICE_COMPROMISED_TRANSLATION = "Dispositivo usado por vários titulares distintos no total ou nas últimas 24 horas."

DEVICE_UNKNOWN_CODE = "WHO_DEVICE_UNKNOWN"
DEVICE_UNKNOWN_DESCRIPTION = "Device without approved history used by a payer who already has other known devices."
DEVICE_UNKNOWN_TRANSLATION = "Dispositivo sem histórico aprovado usado por um pagador que já tem outros dispositivos conhecidos."


def device_compromised(context: RiskContext) -> EvaluatedRule:
    observed = {
        "distinct_documents_total": context.device.distinct_documents_total,
        "distinct_documents_24h": context.device.distinct_documents_24h,
    }
    threshold = {
        "distinct_documents_total": policy.DEVICE_COMPROMISED_DOCUMENTS_TOTAL,
        "distinct_documents_24h": policy.DEVICE_COMPROMISED_DOCUMENTS_24H,
    }
    if any(observed[key] >= threshold[key] for key in threshold):
        return fired(
            DEVICE_COMPROMISED_CODE, AXIS, RiskLevel.CRITICAL, observed, threshold,
            DEVICE_COMPROMISED_DESCRIPTION, DEVICE_COMPROMISED_TRANSLATION,
        )
    return not_fired(
        DEVICE_COMPROMISED_CODE, AXIS, DEVICE_COMPROMISED_DESCRIPTION, DEVICE_COMPROMISED_TRANSLATION, observed, threshold,
    )


def device_unknown(context: RiskContext) -> EvaluatedRule:
    observed = {"device_trust": context.payer.device_trust.value, "known_devices_count": context.payer.known_devices_count}
    threshold = {"known_devices_count": policy.DEVICE_UNKNOWN_MIN_KNOWN_DEVICES}
    if context.payer.device_trust == DeviceTrust.UNKNOWN and observed["known_devices_count"] >= threshold["known_devices_count"]:
        return fired(
            DEVICE_UNKNOWN_CODE, AXIS, RiskLevel.SUSPICIOUS, observed, threshold, DEVICE_UNKNOWN_DESCRIPTION, DEVICE_UNKNOWN_TRANSLATION
        )
    return not_fired(DEVICE_UNKNOWN_CODE, AXIS, DEVICE_UNKNOWN_DESCRIPTION, DEVICE_UNKNOWN_TRANSLATION, observed, threshold)


RULES = (device_compromised, device_unknown)


def analyze(context: RiskContext) -> List[EvaluatedRule]:
    return [rule(context) for rule in RULES]
