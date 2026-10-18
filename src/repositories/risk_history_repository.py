from datetime import datetime
from typing import Tuple

from sqlalchemy import BigInteger, Row, and_, cast, func, select
from sqlalchemy.dialects.postgresql import aggregate_order_by

from database import Context
from models import Account, AccountHolder, AnalysisStatus, PersonType, PixAnalysis, PixTransaction

APPROVED = "approved"
REJECTED = "rejected"
AMOUNT_LIMIT_STATUSES = (APPROVED, "two_factor_required")
INDIVIDUAL = "individual"


def total_amount(*conditions):
    return cast(func.coalesce(func.sum(PixTransaction.amount_minor).filter(*conditions), 0), BigInteger)


def within(since: datetime, until: datetime):
    return and_(PixTransaction.transaction_date >= since, PixTransaction.transaction_date < until)


class RiskHistoryRepository:
    def __init__(self, context: Context) -> None:
        self.session = context.db_session

    def payer_summary(
        self,
        source_account_id: int,
        destination_account_id: int,
        device_id: str,
        since: datetime,
        velocity_since: datetime,
        day_since: datetime,
        test_since: datetime,
        test_max_amount: int,
        test_multiplier: int,
        amount: int,
        until: datetime,
    ) -> Row:
        approved = AnalysisStatus.enumerator == APPROVED
        rejected = AnalysisStatus.enumerator == REJECTED
        same_device = PixTransaction.device_id == device_id
        same_beneficiary = PixTransaction.destination_account_id == destination_account_id
        test_pix = and_(
            same_beneficiary,
            PixTransaction.transaction_date >= test_since,
            PixTransaction.amount_minor <= test_max_amount,
            PixTransaction.amount_minor * test_multiplier <= amount,
        )
        return self.session.execute(
            select(
                func.count().filter(PixTransaction.transaction_date >= velocity_since).label("attempts"),
                func.count().filter(test_pix).label("test_pix_count"),
                total_amount(
                    same_device, PixTransaction.transaction_date >= day_since, AnalysisStatus.enumerator.in_(AMOUNT_LIMIT_STATUSES)
                ).label("device_amount_today"),
                func.count().filter(approved).label("approved_count"),
                func.min(PixTransaction.transaction_date).filter(approved).label("first_approved_at"),
                func.min(PixTransaction.transaction_date).filter(approved, same_device).label("device_first_approved_at"),
                func.count(func.distinct(PixTransaction.device_id)).filter(approved).label("known_devices_count"),
                func.array_agg(aggregate_order_by(PixTransaction.amount_minor, PixTransaction.transaction_date)).filter(approved).label("approved_amounts"),
                func.max(PixTransaction.transaction_date).filter(rejected).label("last_rejection_at"),
                func.array_agg(aggregate_order_by(PixTransaction.amount_minor, PixTransaction.transaction_date.desc()))
                .filter(rejected)
                .label("rejected_amounts_latest_first"),
                func.count().filter(approved, same_beneficiary).label("beneficiary_approved_count"),
                func.min(PixTransaction.transaction_date).filter(approved, same_beneficiary).label("beneficiary_first_approved_at"),
            )
            .select_from(PixTransaction)
            .outerjoin(PixAnalysis, PixAnalysis.pix_transaction_id == PixTransaction.id)
            .outerjoin(AnalysisStatus, AnalysisStatus.id == PixAnalysis.status_id)
            .where(PixTransaction.source_account_id == source_account_id, within(since, until))
        ).one()

    def sum_night_amount_to_individuals(
        self, source_account_id: int, source_holder_id: int, since: datetime, until: datetime
    ) -> int:
        return self.session.execute(
            select(total_amount())
            .join(PixAnalysis, PixAnalysis.pix_transaction_id == PixTransaction.id)
            .join(AnalysisStatus, AnalysisStatus.id == PixAnalysis.status_id)
            .join(Account, Account.id == PixTransaction.destination_account_id)
            .join(AccountHolder, AccountHolder.id == Account.account_holder_id)
            .join(PersonType, PersonType.id == AccountHolder.person_type_id)
            .where(
                PixTransaction.source_account_id == source_account_id,
                within(since, until),
                AnalysisStatus.enumerator.in_(AMOUNT_LIMIT_STATUSES),
                PersonType.enumerator == INDIVIDUAL,
                AccountHolder.id != source_holder_id,
            )
        ).scalar_one()

    def count_device_holders(self, device_id: str, since: datetime, recent_since: datetime, until: datetime) -> Tuple[int, int]:
        holders = func.count(func.distinct(Account.account_holder_id))
        return tuple(
            self.session.execute(
                select(holders, holders.filter(PixTransaction.transaction_date >= recent_since))
                .select_from(PixTransaction)
                .join(Account, Account.id == PixTransaction.source_account_id)
                .where(PixTransaction.device_id == device_id, within(since, until))
            ).one()
        )

    def count_other_payers_to_destination(
        self, destination_account_id: int, source_account_id: int, since: datetime, until: datetime
    ) -> Tuple[int, int]:
        other_payers = func.count(func.distinct(PixTransaction.source_account_id))
        return tuple(
            self.session.execute(
                select(other_payers, other_payers.filter(AnalysisStatus.enumerator == REJECTED))
                .select_from(PixTransaction)
                .outerjoin(PixAnalysis, PixAnalysis.pix_transaction_id == PixTransaction.id)
                .outerjoin(AnalysisStatus, AnalysisStatus.id == PixAnalysis.status_id)
                .where(
                    PixTransaction.destination_account_id == destination_account_id,
                    PixTransaction.source_account_id != source_account_id,
                    within(since, until),
                )
            ).one()
        )

    def count_other_payers_from_ip(self, ip_address: str, source_account_id: int, since: datetime, until: datetime) -> int:
        return self.session.execute(
            select(func.count(func.distinct(PixTransaction.source_account_id))).where(
                PixTransaction.ip_address == ip_address,
                PixTransaction.source_account_id != source_account_id,
                within(since, until),
            )
        ).scalar_one()
