from typing import Dict, List, Tuple

from src.engine import policy
from src.engine.risk_context import RiskContext, RiskLevel


def detect_signals(context: RiskContext) -> List[str]:
    return []


def downgrade(levels: Dict[str, RiskLevel], signals: List[str]) -> Tuple[Dict[str, RiskLevel], List[str]]:
    if not signals:
        return levels, []
    for axis in policy.TRUST_DOWNGRADE_AXIS_ORDER:
        if levels[axis] == RiskLevel.SUSPICIOUS:
            return {**levels, axis: RiskLevel.OK}, [signals[0]]
    return levels, []
