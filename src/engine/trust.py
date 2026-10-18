from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

from src.engine import policy
from src.engine.risk_context import DeviceTrust, EvaluatedRule, RiskContext, RiskLevel, RuleOutcome
from src.engine.rules import fired, not_fired

AXIS = "trust"
HOURS_DECIMALS = 2
AGE_DECIMALS = 2
SECONDS_PER_HOUR = 3600

RECURRENT_BENEFICIARY_CODE = "TRUST_RECURRENT_BENEFICIARY"
RECURRENT_BENEFICIARY_DESCRIPTION = "Recurrent beneficiary: {count} or more approved Pix to this destination, the first more than {hours} hours ago."
RECURRENT_BENEFICIARY_TRANSLATION = "Destinatário recorrente: {count} ou mais Pix aprovados para este destino, o primeiro há mais de {hours} horas."

MATURE_SELF_PIX_CODE = "TRUST_MATURE_SELF_PIX"
MATURE_SELF_PIX_DESCRIPTION = "Pix between accounts of the same owner, destination opened {days} or more days ago, from a trusted device."
MATURE_SELF_PIX_TRANSLATION = "Pix entre contas do mesmo titular, destino aberto há {days} dias ou mais, de dispositivo confiável."


def hours_between(earlier: Optional[datetime], later: datetime) -> Optional[float]:
    if earlier is None:
        return None
    return round((later - earlier).total_seconds() / SECONDS_PER_HOUR, HOURS_DECIMALS)


def recurrent_beneficiary(context: RiskContext) -> EvaluatedRule:
    beneficiary = context.beneficiary
    moment = context.transaction.transaction_date
    observed = {
        "approved_count": beneficiary.approved_count,
        "first_approved_hours_ago": hours_between(beneficiary.first_approved_at, moment),
    }
    threshold = {
        "approved_count": policy.RECURRENT_BENEFICIARY_MIN_APPROVED,
        "first_approved_hours_ago": policy.RECURRENT_BENEFICIARY_MIN_AGE_HOURS,
    }
    description = RECURRENT_BENEFICIARY_DESCRIPTION.format(
        count=policy.RECURRENT_BENEFICIARY_MIN_APPROVED, hours=policy.RECURRENT_BENEFICIARY_MIN_AGE_HOURS
    )
    translation = RECURRENT_BENEFICIARY_TRANSLATION.format(
        count=policy.RECURRENT_BENEFICIARY_MIN_APPROVED, hours=policy.RECURRENT_BENEFICIARY_MIN_AGE_HOURS
    )
    is_recurrent = (
        beneficiary.approved_count >= policy.RECURRENT_BENEFICIARY_MIN_APPROVED
        and beneficiary.first_approved_at is not None
        and moment - beneficiary.first_approved_at > timedelta(hours=policy.RECURRENT_BENEFICIARY_MIN_AGE_HOURS)
    )
    if is_recurrent:
        return fired(RECURRENT_BENEFICIARY_CODE, AXIS, None, observed, threshold, description, translation)
    return not_fired(RECURRENT_BENEFICIARY_CODE, AXIS, description, translation, observed, threshold)


def mature_self_pix(context: RiskContext) -> EvaluatedRule:
    transaction = context.transaction
    observed = {
        "same_owner": transaction.same_owner,
        "destination_account_age_days": round(transaction.destination_account_age_days, AGE_DECIMALS),
        "device_trust": context.payer.device_trust.value,
    }
    threshold = {
        "same_owner": True,
        "destination_account_age_days": policy.MATURE_SELF_PIX_MIN_DESTINATION_AGE_DAYS,
        "device_trust": DeviceTrust.TRUSTED.value,
    }
    description = MATURE_SELF_PIX_DESCRIPTION.format(days=policy.MATURE_SELF_PIX_MIN_DESTINATION_AGE_DAYS)
    translation = MATURE_SELF_PIX_TRANSLATION.format(days=policy.MATURE_SELF_PIX_MIN_DESTINATION_AGE_DAYS)
    is_mature_self_pix = (
        transaction.same_owner
        and transaction.destination_account_age_days >= policy.MATURE_SELF_PIX_MIN_DESTINATION_AGE_DAYS
        and context.payer.device_trust == DeviceTrust.TRUSTED
    )
    if is_mature_self_pix:
        return fired(MATURE_SELF_PIX_CODE, AXIS, None, observed, threshold, description, translation)
    return not_fired(MATURE_SELF_PIX_CODE, AXIS, description, translation, observed, threshold)


SIGNALS = (recurrent_beneficiary, mature_self_pix)


def evaluate_signals(context: RiskContext) -> List[EvaluatedRule]:
    return [signal(context) for signal in SIGNALS]


def detect_signals(context: RiskContext) -> List[str]:
    return [rule.code for rule in evaluate_signals(context) if rule.outcome == RuleOutcome.FIRED]


def downgrade(levels: Dict[str, RiskLevel], signals: List[str]) -> Tuple[Dict[str, RiskLevel], List[str]]:
    if not signals:
        return levels, []
    for axis in policy.TRUST_DOWNGRADE_AXIS_ORDER:
        if levels[axis] == RiskLevel.SUSPICIOUS:
            return {**levels, axis: RiskLevel.OK}, [signals[0]]
    return levels, []
