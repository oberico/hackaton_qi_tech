from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import CHAR, BigInteger, DateTime, ForeignKey, Numeric, SmallInteger, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import INET, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base


class PixTransaction(Base):
    __tablename__ = "pix_transaction"
    __table_args__ = (UniqueConstraint("transaction_id", name="uq_pix_transaction_transaction_id"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    transaction_id: Mapped[str] = mapped_column(String(64), nullable=False)
    payload_hash: Mapped[str] = mapped_column(CHAR(64), nullable=False)
    amount_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    transaction_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    utc_offset_minutes: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    source_account_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("account.id"), nullable=False)
    destination_account_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("account.id"), nullable=False)
    device_id: Mapped[str] = mapped_column(String(128), nullable=False)
    channel: Mapped[str] = mapped_column(String(30), nullable=False)
    ip_address: Mapped[str] = mapped_column(INET, nullable=False)
    latitude: Mapped[Optional[Decimal]] = mapped_column(Numeric(9, 6))
    longitude: Mapped[Optional[Decimal]] = mapped_column(Numeric(9, 6))
    raw_payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
