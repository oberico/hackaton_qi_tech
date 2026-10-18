from datetime import datetime

from sqlalchemy import CHAR, Boolean, DateTime, Integer, String, UniqueConstraint, func, true
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base


class PixParticipant(Base):
    __tablename__ = "pix_participant"
    __table_args__ = (UniqueConstraint("ispb", name="uq_pix_participant_ispb"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ispb: Mapped[str] = mapped_column(CHAR(8), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    listed: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=true())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
