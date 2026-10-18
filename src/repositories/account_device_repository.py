from datetime import datetime

from sqlalchemy import Row, func, select
from sqlalchemy.dialects.postgresql import insert

from database import Context
from models import AccountDevice


class AccountDeviceRepository:
    def __init__(self, context: Context) -> None:
        self.session = context.db_session

    def record_approval(self, account_id: int, device_id: str, approved_at: datetime) -> None:
        statement = insert(AccountDevice).values(
            account_id=account_id,
            device_id=device_id,
            approved_count=1,
            first_approved_at=approved_at,
            last_approved_at=approved_at,
        )
        self.session.execute(
            statement.on_conflict_do_update(
                constraint="uq_account_device",
                set_={
                    "approved_count": AccountDevice.approved_count + 1,
                    "first_approved_at": func.least(AccountDevice.first_approved_at, statement.excluded.first_approved_at),
                    "last_approved_at": func.greatest(AccountDevice.last_approved_at, statement.excluded.last_approved_at),
                },
            )
        )

    def known_devices(self, account_id: int, device_id: str, until: datetime) -> Row:
        return self.session.execute(
            select(
                func.min(AccountDevice.first_approved_at).filter(AccountDevice.device_id == device_id).label("device_first_approved_at"),
                func.count().label("known_devices_count"),
            ).where(AccountDevice.account_id == account_id, AccountDevice.first_approved_at < until)
        ).one()
