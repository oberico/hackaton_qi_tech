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
