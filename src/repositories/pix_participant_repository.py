from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from models import PixParticipant


class PixParticipantRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def find_by_ispb(self, ispb: str) -> Optional[PixParticipant]:
        return self.session.execute(select(PixParticipant).where(PixParticipant.ispb == ispb)).scalar_one_or_none()
