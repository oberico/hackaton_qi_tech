from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from database import Context
from models import PixParticipant


class PixParticipantRepository:
    def __init__(self, context: Context) -> None:
        self.session = context.db_session

    def get_or_create(self, ispb: str) -> PixParticipant:
        self.session.execute(
            insert(PixParticipant)
            .values(ispb=ispb, name=ispb, listed=False)
            .on_conflict_do_nothing(constraint="uq_pix_participant_ispb")
        )
        return self.session.execute(select(PixParticipant).where(PixParticipant.ispb == ispb)).scalar_one()
