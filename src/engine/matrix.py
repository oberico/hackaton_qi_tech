from typing import Tuple

from src.engine.risk_context import Decision, DecisionBasis, RiskLevel


def decide(who: RiskLevel, how: RiskLevel, where: RiskLevel) -> Tuple[Decision, DecisionBasis]:
    levels = (who, how, where)
    if RiskLevel.CRITICAL in levels:
        return Decision.REJECTED, DecisionBasis.CRITICAL_AXIS
    suspicious_axes = levels.count(RiskLevel.SUSPICIOUS)
    if suspicious_axes >= 2:
        return Decision.REJECTED, DecisionBasis.TWO_SUSPICIOUS_AXES
    if suspicious_axes == 1:
        return Decision.TWO_FACTOR_REQUIRED, DecisionBasis.SINGLE_SUSPICIOUS_AXIS
    return Decision.APPROVED, DecisionBasis.CLEAN
