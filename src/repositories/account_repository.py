from datetime import datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from models import Account


class AccountRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_or_create(
        self, participant_id: int, branch: str, account_number: str, account_holder_id: int, opening_date: datetime
    ) -> Account:
        self.session.execute(
            insert(Account)
            .values(
                participant_id=participant_id,
                branch=branch,
                account_number=account_number,
                account_holder_id=account_holder_id,
                opening_date=opening_date,
            )
            .on_conflict_do_nothing(constraint="uq_account_participant_branch_number")
        )
        return self.session.execute(
            select(Account).where(
                Account.participant_id == participant_id,
                Account.branch == branch,
                Account.account_number == account_number,
            )
        ).scalar_one()
