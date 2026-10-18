from datetime import datetime
from typing import Optional

from sqlalchemy import Row, func, select
from sqlalchemy.dialects.postgresql import insert

from database import Context
from models import AccountCounterparty


class AccountCounterpartyRepository:
    def __init__(self, context: Context) -> None:
        self.session = context.db_session

    def record_approval(self, source_account_id: int, destination_account_id: int, amount_minor: int, approved_at: datetime) -> None:
        statement = insert(AccountCounterparty).values(
            source_account_id=source_account_id,
            destination_account_id=destination_account_id,
            approved_count=1,
            approved_amount_minor=amount_minor,
            first_approved_at=approved_at,
            last_approved_at=approved_at,
        )
        self.session.execute(
            statement.on_conflict_do_update(
                constraint="uq_account_counterparty",
                set_={
                    "approved_count": AccountCounterparty.approved_count + 1,
                    "approved_amount_minor": AccountCounterparty.approved_amount_minor + statement.excluded.approved_amount_minor,
                    "first_approved_at": func.least(AccountCounterparty.first_approved_at, statement.excluded.first_approved_at),
                    "last_approved_at": func.greatest(AccountCounterparty.last_approved_at, statement.excluded.last_approved_at),
                },
            )
        )

    def find_relationship(self, source_account_id: int, destination_account_id: int, until: datetime) -> Optional[Row]:
        return self.session.execute(
            select(AccountCounterparty.approved_count, AccountCounterparty.first_approved_at).where(
                AccountCounterparty.source_account_id == source_account_id,
                AccountCounterparty.destination_account_id == destination_account_id,
                AccountCounterparty.first_approved_at < until,
            )
        ).one_or_none()
