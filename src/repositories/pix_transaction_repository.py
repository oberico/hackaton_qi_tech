from typing import Optional

from sqlalchemy import select

from database import Context
from models import PixTransaction


class PixTransactionRepository:
    def __init__(self, context: Context) -> None:
        self.session = context.db_session

    def create(self, **fields) -> PixTransaction:
        pix_transaction = PixTransaction(**fields)
        self.session.add(pix_transaction)
        self.session.flush()
        return pix_transaction

    def find_by_transaction_id(self, transaction_id: str) -> Optional[PixTransaction]:
        return self.session.execute(
            select(PixTransaction).where(PixTransaction.transaction_id == transaction_id)
        ).scalar_one_or_none()
