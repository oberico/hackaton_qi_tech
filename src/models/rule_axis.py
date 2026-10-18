from datetime import datetime

from sqlalchemy import DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base


class RuleAxis(Base):
    __tablename__ = "rule_axis"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    enumerator: Mapped[str] = mapped_column(String(20), nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
