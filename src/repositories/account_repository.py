from datetime import datetime
from typing import Optional, Tuple

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from database import Context
from models import Account, AccountHolder, PixParticipant


class AccountRepository:
    def __init__(self, context: Context) -> None:
        self.session = context.db_session

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

    def find_with_holder(self, ispb: str, branch: str, account_number: str) -> Optional[Tuple[Account, AccountHolder]]:
        row = self.session.execute(
            select(Account, AccountHolder)
            .join(PixParticipant, Account.participant_id == PixParticipant.id)
            .join(AccountHolder, Account.account_holder_id == AccountHolder.id)
            .where(
                PixParticipant.ispb == ispb,
                Account.branch == branch,
                Account.account_number == account_number,
            )
        ).first()
        if row is None:
            return None
        return row[0], row[1]
