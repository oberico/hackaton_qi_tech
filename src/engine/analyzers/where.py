from typing import List

from src.engine.risk_context import EvaluatedRule, RiskContext

RULES = ()


def analyze(context: RiskContext) -> List[EvaluatedRule]:
    return [rule(context) for rule in RULES]
