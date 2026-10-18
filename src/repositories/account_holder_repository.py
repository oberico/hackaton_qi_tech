from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from database import Context
from models import AccountHolder, PersonType


class AccountHolderRepository:
    def __init__(self, context: Context) -> None:
        self.session = context.db_session

    def get_or_create(self, document_number: str, person_type: str) -> AccountHolder:
        person_type_id = select(PersonType.id).where(PersonType.enumerator == person_type).scalar_subquery()
        self.session.execute(
            insert(AccountHolder)
            .values(document_number=document_number, person_type_id=person_type_id)
            .on_conflict_do_nothing(constraint="uq_account_holder_document_number")
        )
        return self.session.execute(
            select(AccountHolder).where(AccountHolder.document_number == document_number)
        ).scalar_one()
