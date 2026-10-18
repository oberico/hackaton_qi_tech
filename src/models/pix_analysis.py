from datetime import datetime
from uuid import UUID as PyUUID

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, SmallInteger, String, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base


class PixAnalysis(Base):
    __tablename__ = "pix_analysis"
    __table_args__ = (
        UniqueConstraint("analysis_key", name="uq_pix_analysis_analysis_key"),
        UniqueConstraint("pix_transaction_id", name="uq_pix_analysis_pix_transaction"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    analysis_key: Mapped[PyUUID] = mapped_column(UUID(as_uuid=True), nullable=False, server_default=text("gen_random_uuid()"))
    pix_transaction_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("pix_transaction.id"), nullable=False)
    status_id: Mapped[int] = mapped_column(Integer, ForeignKey("analysis_status.id"), nullable=False)
    decision_basis_id: Mapped[int] = mapped_column(Integer, ForeignKey("decision_basis.id"), nullable=False)
    policy_version: Mapped[str] = mapped_column(String(30), nullable=False)
    payer_maturity_phase: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    features: Mapped[dict] = mapped_column(JSONB, nullable=False)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
