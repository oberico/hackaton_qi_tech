from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base


class AccountCounterparty(Base):
    __tablename__ = "account_counterparty"
    __table_args__ = (UniqueConstraint("source_account_id", "destination_account_id", name="uq_account_counterparty"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    source_account_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("account.id"), nullable=False)
    destination_account_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("account.id"), nullable=False)
    approved_count: Mapped[int] = mapped_column(Integer, nullable=False)
    approved_amount_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    first_approved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_approved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
