from typing import List

from src.engine import policy
from src.engine.clock import is_within_hours, local_datetime
from src.engine.risk_context import DeviceTrust, EvaluatedRule, RiskContext
from src.engine.rules import fired, not_fired

AXIS = "floor"

UNREGISTERED_DEVICE_CODE = "FLOOR_UNREGISTERED_DEVICE"
UNREGISTERED_DEVICE_DESCRIPTION = "Pix from a device with no history above the regulatory per-transaction or daily limit."
UNREGISTERED_DEVICE_TRANSLATION = "Pix de dispositivo sem histórico acima do limite regulatório por transação ou por dia."

NIGHT_LIMIT_CODE = "FLOOR_NIGHT_LIMIT"
NIGHT_LIMIT_DESCRIPTION = "Night-time amount between individuals above the regulatory limit."
NIGHT_LIMIT_TRANSLATION = "Soma noturna entre pessoas físicas acima do limite regulatório."


def unregistered_device(context: RiskContext) -> EvaluatedRule:
    flow = context.transaction.flow
    transaction_limit = policy.UNKNOWN_DEVICE_TX_LIMIT_MINOR[flow]
    daily_limit = policy.UNKNOWN_DEVICE_DAILY_LIMIT_MINOR[flow]
    if transaction_limit is None or context.payer.device_trust != DeviceTrust.UNKNOWN:
        return not_fired(UNREGISTERED_DEVICE_CODE, AXIS, UNREGISTERED_DEVICE_DESCRIPTION, UNREGISTERED_DEVICE_TRANSLATION)
    amount = context.transaction.amount
    daily_amount = context.payer.unknown_device_amount_today + amount
    observed = {"amount": amount, "daily_amount": daily_amount}
    threshold = {"amount": transaction_limit, "daily_amount": daily_limit}
    if amount > transaction_limit or daily_amount > daily_limit:
        return fired(UNREGISTERED_DEVICE_CODE, AXIS, None, observed, threshold, UNREGISTERED_DEVICE_DESCRIPTION, UNREGISTERED_DEVICE_TRANSLATION)
    return not_fired(UNREGISTERED_DEVICE_CODE, AXIS, UNREGISTERED_DEVICE_DESCRIPTION, UNREGISTERED_DEVICE_TRANSLATION, observed, threshold)


def night_limit(context: RiskContext) -> EvaluatedRule:
    limit = policy.NIGHT_LIMIT_MINOR[context.transaction.flow]
    in_night = is_within_hours(local_datetime(context).hour, policy.NIGHT_START_HOUR, policy.NIGHT_END_HOUR)
    if limit is None or context.transaction.same_owner or not in_night:
        return not_fired(NIGHT_LIMIT_CODE, AXIS, NIGHT_LIMIT_DESCRIPTION, NIGHT_LIMIT_TRANSLATION)
    night_amount = context.payer.night_amount_to_individuals + context.transaction.amount
    observed = {"night_amount": night_amount}
    threshold = {"night_amount": limit}
    if night_amount > limit:
        return fired(NIGHT_LIMIT_CODE, AXIS, None, observed, threshold, NIGHT_LIMIT_DESCRIPTION, NIGHT_LIMIT_TRANSLATION)
    return not_fired(NIGHT_LIMIT_CODE, AXIS, NIGHT_LIMIT_DESCRIPTION, NIGHT_LIMIT_TRANSLATION, observed, threshold)


FLOORS = (unregistered_device, night_limit)


def evaluate_floors(context: RiskContext) -> List[EvaluatedRule]:
    return [floor(context) for floor in FLOORS]
