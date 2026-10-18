from typing import Optional

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from database import Context
from models import PixTransaction

TRANSACTION_ID_CONSTRAINT = "uq_pix_transaction_transaction_id"


class PixTransactionRepository:
    def __init__(self, context: Context) -> None:
        self.session = context.db_session

    def create(self, **fields) -> Optional[PixTransaction]:
        pix_transaction = PixTransaction(**fields)
        self.session.add(pix_transaction)
        try:
            self.session.flush()
        except IntegrityError as error:
            self.session.rollback()
            if TRANSACTION_ID_CONSTRAINT not in str(error.orig):
                raise
            return None
        return pix_transaction

    def find_by_transaction_id(self, transaction_id: str) -> Optional[PixTransaction]:
        return self.session.execute(
            select(PixTransaction).where(PixTransaction.transaction_id == transaction_id)
        ).scalar_one_or_none()
