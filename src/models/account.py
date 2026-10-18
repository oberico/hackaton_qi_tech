from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base


class Account(Base):
    __tablename__ = "account"
    __table_args__ = (
        UniqueConstraint("participant_id", "branch", "account_number", name="uq_account_participant_branch_number"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    participant_id: Mapped[int] = mapped_column(Integer, ForeignKey("pix_participant.id"), nullable=False)
    branch: Mapped[str] = mapped_column(String(4), nullable=False)
    account_number: Mapped[str] = mapped_column(String(20), nullable=False)
    account_holder_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("account_holder.id"), nullable=False)
    opening_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
