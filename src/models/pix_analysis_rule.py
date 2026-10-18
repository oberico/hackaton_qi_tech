from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base


class PixAnalysisRule(Base):
    __tablename__ = "pix_analysis_rule"
    __table_args__ = (UniqueConstraint("pix_analysis_id", "rule_code", name="uq_pix_analysis_rule"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    pix_analysis_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("pix_analysis.id"), nullable=False)
    rule_code: Mapped[str] = mapped_column(String(60), nullable=False)
    rule_axis_id: Mapped[int] = mapped_column(Integer, ForeignKey("rule_axis.id"), nullable=False)
    rule_outcome_id: Mapped[int] = mapped_column(Integer, ForeignKey("rule_outcome.id"), nullable=False)
    risk_level_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("risk_level.id"), nullable=True)
    observed: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    threshold: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    reason: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
