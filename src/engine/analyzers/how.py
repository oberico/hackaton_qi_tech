from datetime import timedelta
from typing import List

from src.engine import ceiling, night, policy
from src.engine.clock import is_within_hours, local_datetime
from src.engine.risk_context import EvaluatedRule, RiskContext, RiskLevel
from src.engine.rules import fired, not_fired

AXIS = "how"

NIGHT_LIMIT_CODE = "HOW_NIGHT_LIMIT_EXCEEDED"
NIGHT_LIMIT_DESCRIPTION = "Night-time amount between individuals above R$ 1,000."
NIGHT_LIMIT_TRANSLATION = "Soma noturna entre pessoas físicas acima de R$ 1.000."

VELOCITY_CODE = "HOW_VELOCITY_EXCEEDED"
VELOCITY_DESCRIPTION = "Payer attempts in the last 10 minutes at or above the limit for the flow."
VELOCITY_TRANSLATION = "Tentativas do pagador nos últimos 10 minutos iguais ou acima do limite do fluxo."

CEILING_CODE = "HOW_ABOVE_CUSTOMER_CEILING"
CEILING_DESCRIPTION = "Amount above the payer ceiling, blended from the payer approved history and the reference ceiling."
CEILING_TRANSLATION = "Valor acima do teto do pagador, combinando o histórico aprovado do pagador e o teto de referência."

EARLY_MORNING_CODE = "HOW_EARLY_MORNING_AMOUNT"
EARLY_MORNING_DESCRIPTION = "Amount between R$ 200 and R$ 1,000 sent in the early morning (00:00 to 05:59 local time)."
EARLY_MORNING_TRANSLATION = "Valor entre R$ 200 e R$ 1.000 enviado de madrugada (00:00 às 05:59, horário local)."

RETRY_CODE = "HOW_RETRY_AFTER_REJECTION"
RETRY_DESCRIPTION = "New attempt shortly after a rejection of the same payer, with a smaller amount than the rejected one."
RETRY_TRANSLATION = "Nova tentativa logo após uma rejeição do mesmo pagador, com valor menor que o rejeitado."

TEST_PIX_CODE = "HOW_TEST_PIX"
TEST_PIX_DESCRIPTION = "Large Pix to a destination that received a very small Pix minutes before, with no earlier approved relationship."
TEST_PIX_TRANSLATION = "Pix alto para um destino que recebeu um Pix muito pequeno minutos antes, sem relação aprovada anterior."


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


def above_customer_ceiling(context: RiskContext) -> EvaluatedRule:
    observed = {"amount": context.transaction.amount}
    threshold = {"ceiling": ceiling.customer_ceiling(context)}
    if observed["amount"] > threshold["ceiling"]:
        return fired(
            CEILING_CODE, AXIS, RiskLevel.SUSPICIOUS, observed, threshold, CEILING_DESCRIPTION, CEILING_TRANSLATION
        )
    return not_fired(CEILING_CODE, AXIS, CEILING_DESCRIPTION, CEILING_TRANSLATION, observed, threshold)


def early_morning_amount(context: RiskContext) -> EvaluatedRule:
    hour = local_datetime(context).hour
    observed = {"amount": context.transaction.amount, "local_hour": hour}
    threshold = {"min_amount": policy.EARLY_MORNING_MIN_AMOUNT_MINOR, "max_amount": policy.EARLY_MORNING_MAX_AMOUNT_MINOR}
    in_early_morning = is_within_hours(hour, policy.EARLY_MORNING_START_HOUR, policy.EARLY_MORNING_END_HOUR)
    if in_early_morning and threshold["min_amount"] < observed["amount"] <= threshold["max_amount"]:
        return fired(
            EARLY_MORNING_CODE, AXIS, RiskLevel.SUSPICIOUS, observed, threshold, EARLY_MORNING_DESCRIPTION, EARLY_MORNING_TRANSLATION
        )
    return not_fired(EARLY_MORNING_CODE, AXIS, EARLY_MORNING_DESCRIPTION, EARLY_MORNING_TRANSLATION, observed, threshold)


def retry_after_rejection(context: RiskContext) -> EvaluatedRule:
    rejection_at = context.payer.last_rejection_at
    rejected_amount = context.payer.last_rejected_amount
    if rejection_at is None or rejected_amount is None:
        return not_fired(RETRY_CODE, AXIS, RETRY_DESCRIPTION, RETRY_TRANSLATION)
    elapsed = context.transaction.transaction_date - rejection_at
    observed = {
        "minutes_since_rejection": int(elapsed.total_seconds() // 60),
        "amount": context.transaction.amount,
        "last_rejected_amount": rejected_amount,
    }
    threshold = {"window_minutes": policy.RETRY_AFTER_REJECTION_WINDOW_MINUTES}
    within_window = timedelta(0) <= elapsed < timedelta(minutes=threshold["window_minutes"])
    if within_window and observed["amount"] < rejected_amount:
        return fired(RETRY_CODE, AXIS, RiskLevel.SUSPICIOUS, observed, threshold, RETRY_DESCRIPTION, RETRY_TRANSLATION)
    return not_fired(RETRY_CODE, AXIS, RETRY_DESCRIPTION, RETRY_TRANSLATION, observed, threshold)


def beneficiary_known_before_the_test_window(context: RiskContext) -> bool:
    first_approved_at = context.beneficiary.first_approved_at
    window_start = context.transaction.transaction_date - timedelta(minutes=policy.TEST_PIX_WINDOW_MINUTES)
    return first_approved_at is not None and first_approved_at < window_start


def pix_test_followup(context: RiskContext) -> EvaluatedRule:
    observed = {
        "amount": context.transaction.amount,
        "small_amount_to_destination_last_15min": context.payer.small_amount_to_destination_last_15min,
    }
    threshold = {
        "test_max_amount": policy.TEST_PIX_MAX_AMOUNT_MINOR,
        "followup_min_amount": policy.TEST_PIX_FOLLOWUP_MIN_AMOUNT_MINOR,
        "followup_multiplier": policy.TEST_PIX_FOLLOWUP_MULTIPLIER,
        "window_minutes": policy.TEST_PIX_WINDOW_MINUTES,
    }
    probing = (
        observed["small_amount_to_destination_last_15min"]
        and observed["amount"] >= threshold["followup_min_amount"]
        and not beneficiary_known_before_the_test_window(context)
    )
    if probing:
        return fired(TEST_PIX_CODE, AXIS, RiskLevel.SUSPICIOUS, observed, threshold, TEST_PIX_DESCRIPTION, TEST_PIX_TRANSLATION)
    return not_fired(TEST_PIX_CODE, AXIS, TEST_PIX_DESCRIPTION, TEST_PIX_TRANSLATION, observed, threshold)


RULES = (
    night_limit_exceeded, velocity_exceeded, above_customer_ceiling, early_morning_amount, retry_after_rejection, pix_test_followup,
)


def analyze(context: RiskContext) -> List[EvaluatedRule]:
    return [rule(context) for rule in RULES]
