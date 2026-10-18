from fractions import Fraction
from typing import List

from src.engine import policy
from src.engine.risk_context import PersonType, RiskContext


def interpolated_percentile(values: List[int], percentile: float) -> Fraction:
    ordered = sorted(values)
    rank = Fraction(str(percentile)) * (len(ordered) - 1)
    lower = int(rank)
    upper = min(lower + 1, len(ordered) - 1)
    return ordered[lower] + (rank - lower) * (ordered[upper] - ordered[lower])


def reference_ceiling(context: RiskContext) -> int:
    if context.transaction.source_person_type == PersonType.COMPANY:
        return policy.REFERENCE_CEILING_MINOR["company"]
    if context.transaction.source_account_age_days < policy.REFERENCE_CEILING_NEW_ACCOUNT_DAYS:
        return policy.REFERENCE_CEILING_MINOR["individual_new_account"]
    return policy.REFERENCE_CEILING_MINOR["individual"]


def customer_ceiling(context: RiskContext) -> int:
    reference = reference_ceiling(context)
    amounts = context.payer.approved_amounts_90d
    if not amounts:
        return reference
    history = Fraction(str(policy.HISTORY_MARGIN)) * interpolated_percentile(amounts, policy.HISTORY_PERCENTILE)
    approved = len(amounts)
    blended = (approved * history + policy.SHRINKAGE_K * reference) / (approved + policy.SHRINKAGE_K)
    return blended.numerator // blended.denominator
