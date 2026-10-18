from typing import Dict

from sqlalchemy import select
from sqlalchemy.orm import Session

from models import PixAnalysisAxis, RiskLevel, RuleAxis


class PixAnalysisAxisRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create_all(self, pix_analysis_id: int, levels: Dict[str, str]) -> None:
        self.session.add_all(
            PixAnalysisAxis(
                pix_analysis_id=pix_analysis_id,
                rule_axis_id=select(RuleAxis.id).where(RuleAxis.enumerator == axis).scalar_subquery(),
                risk_level_id=select(RiskLevel.id).where(RiskLevel.enumerator == level).scalar_subquery(),
            )
            for axis, level in levels.items()
        )
        self.session.flush()

    def levels_by_analysis(self, pix_analysis_id: int) -> Dict[str, str]:
        rows = self.session.execute(
            select(RuleAxis.enumerator, RiskLevel.enumerator)
            .join(PixAnalysisAxis, PixAnalysisAxis.rule_axis_id == RuleAxis.id)
            .join(RiskLevel, RiskLevel.id == PixAnalysisAxis.risk_level_id)
            .where(PixAnalysisAxis.pix_analysis_id == pix_analysis_id)
        ).all()
        return {axis: level for axis, level in rows}
