from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base


class AccountHolder(Base):
    __tablename__ = "account_holder"
    __table_args__ = (UniqueConstraint("document_number", name="uq_account_holder_document_number"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    document_number: Mapped[str] = mapped_column(String(18), nullable=False)
    person_type_id: Mapped[int] = mapped_column(Integer, ForeignKey("person_type.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
