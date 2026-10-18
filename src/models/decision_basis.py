from datetime import datetime

from sqlalchemy import DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base


class DecisionBasis(Base):
    __tablename__ = "decision_basis"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    enumerator: Mapped[str] = mapped_column(String(30), nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
