from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base


class AccountDevice(Base):
    __tablename__ = "account_device"
    __table_args__ = (UniqueConstraint("account_id", "device_id", name="uq_account_device"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    account_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("account.id"), nullable=False)
    device_id: Mapped[str] = mapped_column(String(128), nullable=False)
    approved_count: Mapped[int] = mapped_column(Integer, nullable=False)
    first_approved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_approved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
