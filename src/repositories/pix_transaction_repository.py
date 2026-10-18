from sqlalchemy.orm import Session

from models import PixTransaction


class PixTransactionRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create(self, **fields) -> PixTransaction:
        pix_transaction = PixTransaction(**fields)
        self.session.add(pix_transaction)
        self.session.flush()
        return pix_transaction
