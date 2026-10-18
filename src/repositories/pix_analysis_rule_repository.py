from typing import List

from sqlalchemy import select

from database import Context
from models import PixAnalysisRule, RiskLevel, RuleAxis, RuleOutcome


class PixAnalysisRuleRepository:
    def __init__(self, context: Context) -> None:
        self.session = context.db_session

    def create_all(self, pix_analysis_id: int, evaluated_rules: List) -> None:
        self.session.add_all(
            PixAnalysisRule(
                pix_analysis_id=pix_analysis_id,
                rule_code=rule.code,
                rule_axis_id=select(RuleAxis.id).where(RuleAxis.enumerator == rule.axis).scalar_subquery(),
                rule_outcome_id=select(RuleOutcome.id).where(RuleOutcome.enumerator == rule.outcome.value).scalar_subquery(),
                risk_level_id=self._risk_level_id(rule.level),
                observed=rule.observed,
                threshold=rule.threshold,
                reason=rule.description,
            )
            for rule in evaluated_rules
        )
        self.session.flush()

    @staticmethod
    def _risk_level_id(level):
        if level is None:
            return None
        return select(RiskLevel.id).where(RiskLevel.enumerator == level.value).scalar_subquery()
