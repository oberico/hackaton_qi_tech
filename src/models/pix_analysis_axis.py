from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base


class PixAnalysisAxis(Base):
    __tablename__ = "pix_analysis_axis"
    __table_args__ = (UniqueConstraint("pix_analysis_id", "rule_axis_id", name="uq_pix_analysis_axis"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    pix_analysis_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("pix_analysis.id"), nullable=False)
    rule_axis_id: Mapped[int] = mapped_column(Integer, ForeignKey("rule_axis.id"), nullable=False)
    risk_level_id: Mapped[int] = mapped_column(Integer, ForeignKey("risk_level.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
