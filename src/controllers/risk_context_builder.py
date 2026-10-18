import dataclasses
import ipaddress
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Tuple

from repositories import RiskHistoryRepository
from src.engine import policy
from src.engine.risk_context import (
    BeneficiaryRelationship,
    DestinationHistory,
    DeviceHistory,
    DeviceTrust,
    Flow,
    Geolocation,
    IpHistory,
    PayerHistory,
    PersonType,
    RiskContext,
    TransactionFacts,
)

SECONDS_PER_DAY = 86400
DEVICE_TRUSTED_AFTER = timedelta(hours=policy.DEVICE_TRUSTED_AFTER_HOURS)
DEVICE_RECENT_WINDOW = timedelta(hours=24)
IP_WINDOW = timedelta(hours=1)

FLOWS = {
    (PersonType.INDIVIDUAL, PersonType.INDIVIDUAL): Flow.PF_PF,
    (PersonType.INDIVIDUAL, PersonType.COMPANY): Flow.PF_PJ,
    (PersonType.COMPANY, PersonType.INDIVIDUAL): Flow.PJ_PF,
    (PersonType.COMPANY, PersonType.COMPANY): Flow.PJ_PJ,
}


def person_type_of(document_number: str) -> PersonType:
    return PersonType.COMPANY if "/" in document_number else PersonType.INDIVIDUAL


def utc_offset_minutes_of(moment: datetime) -> int:
    return int(moment.utcoffset().total_seconds() // 60)


def age_in_days(opening_date: datetime, transaction_date: datetime) -> float:
    return (transaction_date - opening_date).total_seconds() / SECONDS_PER_DAY


PRIVATE_NETWORKS = tuple(
    ipaddress.ip_network(network)
    for network in (
        "10.0.0.0/8",
        "172.16.0.0/12",
        "192.168.0.0/16",
        "127.0.0.0/8",
        "169.254.0.0/16",
        "::1/128",
        "fc00::/7",
        "fe80::/10",
    )
)


def is_private_ip(ip_address: str) -> bool:
    try:
        address = ipaddress.ip_address(ip_address)
    except ValueError:
        return False
    return any(address.version == network.version and address in network for network in PRIVATE_NETWORKS)


def geolocation_of(source: dict) -> Optional[Geolocation]:
    geolocation = source.get("geolocation")
    if not geolocation:
        return None
    return Geolocation(latitude=geolocation["latitude"], longitude=geolocation["longitude"])


def transaction_facts(payload: dict, source_account, destination_account, destination_participant) -> TransactionFacts:
    transaction_date = datetime.fromisoformat(payload["transaction_date"])
    source = payload["source"]
    source_person_type = person_type_of(payload["source_account"]["owner"]["document_number"])
    destination_person_type = person_type_of(payload["destination_account"]["owner"]["document_number"])
    return TransactionFacts(
        amount=payload["amount"],
        transaction_date=transaction_date,
        utc_offset_minutes=utc_offset_minutes_of(transaction_date),
        source_person_type=source_person_type,
        destination_person_type=destination_person_type,
        flow=FLOWS[(source_person_type, destination_person_type)],
        same_owner=source_account.account_holder_id == destination_account.account_holder_id,
        destination_participant_listed=destination_participant.listed,
        source_account_age_days=age_in_days(source_account.opening_date, transaction_date),
        destination_account_age_days=age_in_days(destination_account.opening_date, transaction_date),
        device_id=source["device_id"],
        channel=source["channel"],
        ip_address=source["ip"],
        ip_is_private=is_private_ip(source["ip"]),
        geolocation=geolocation_of(source),
    )


def neutral_payer_history() -> PayerHistory:
    return PayerHistory(
        approved_count=0,
        relationship_days=0,
        approved_amounts_90d=[],
        transactions_last_10min=0,
        night_amount_to_individuals=0,
        unknown_device_amount_today=0,
        small_amount_to_destination_last_15min=False,
        early_morning_share=0.0,
        last_rejection_at=None,
        last_rejected_amount=None,
        known_devices_count=0,
        device_trust=DeviceTrust.UNKNOWN,
        known_channels=[],
        usually_sends_geolocation=False,
        known_geolocations=[],
    )


def local_moment(facts: TransactionFacts) -> datetime:
    return facts.transaction_date.astimezone(timezone(timedelta(minutes=facts.utc_offset_minutes)))


def night_period_start(facts: TransactionFacts) -> Optional[datetime]:
    local = local_moment(facts)
    night_start = local.replace(hour=policy.NIGHT_START_HOUR, minute=0, second=0, microsecond=0)
    if local.hour >= policy.NIGHT_START_HOUR:
        return night_start
    if local.hour < policy.NIGHT_END_HOUR:
        return night_start - timedelta(days=1)
    return None


def night_amount_to_individuals(history: RiskHistoryRepository, facts: TransactionFacts, source_account) -> int:
    since = night_period_start(facts)
    if since is None:
        return 0
    return history.sum_night_amount_to_individuals(
        source_account.id, source_account.account_holder_id, since, facts.transaction_date
    )


def local_day_start(facts: TransactionFacts) -> datetime:
    return local_moment(facts).replace(hour=0, minute=0, second=0, microsecond=0)


def history_start(facts: TransactionFacts) -> datetime:
    return facts.transaction_date - timedelta(days=policy.HISTORY_WINDOW_DAYS)


def device_trust_of(first_approved_at: Optional[datetime], moment: datetime) -> DeviceTrust:
    if first_approved_at is None:
        return DeviceTrust.UNKNOWN
    if moment - first_approved_at > DEVICE_TRUSTED_AFTER:
        return DeviceTrust.TRUSTED
    return DeviceTrust.OBSERVING


def latest_rejected_amount(amounts_latest_first: Optional[List[int]]) -> Optional[int]:
    return amounts_latest_first[0] if amounts_latest_first else None


def payer_and_beneficiary_history(
    history: RiskHistoryRepository, facts: TransactionFacts, source_account, destination_account
) -> Tuple[PayerHistory, BeneficiaryRelationship]:
    moment = facts.transaction_date
    summary = history.payer_summary(
        source_account_id=source_account.id,
        destination_account_id=destination_account.id,
        device_id=facts.device_id,
        since=history_start(facts),
        velocity_since=moment - timedelta(minutes=policy.VELOCITY_WINDOW_MINUTES),
        day_since=local_day_start(facts),
        test_since=moment - timedelta(minutes=policy.TEST_PIX_WINDOW_MINUTES),
        test_max_amount=policy.TEST_PIX_MAX_AMOUNT_MINOR,
        test_multiplier=policy.TEST_PIX_FOLLOWUP_MULTIPLIER,
        amount=facts.amount,
        until=moment,
    )
    payer = dataclasses.replace(
        neutral_payer_history(),
        approved_count=summary.approved_count,
        relationship_days=age_in_days(summary.first_approved_at, moment) if summary.first_approved_at else 0,
        approved_amounts_90d=list(summary.approved_amounts or []),
        transactions_last_10min=summary.attempts + 1,
        night_amount_to_individuals=night_amount_to_individuals(history, facts, source_account),
        unknown_device_amount_today=summary.device_amount_today,
        small_amount_to_destination_last_15min=summary.test_pix_count > 0,
        last_rejection_at=summary.last_rejection_at,
        last_rejected_amount=latest_rejected_amount(summary.rejected_amounts_latest_first),
        known_devices_count=summary.known_devices_count,
        device_trust=device_trust_of(summary.device_first_approved_at, moment),
    )
    beneficiary = BeneficiaryRelationship(
        approved_count=summary.beneficiary_approved_count, first_approved_at=summary.beneficiary_first_approved_at
    )
    return payer, beneficiary


def device_history(history: RiskHistoryRepository, facts: TransactionFacts) -> DeviceHistory:
    total, recent = history.count_device_holders(
        facts.device_id, history_start(facts), facts.transaction_date - DEVICE_RECENT_WINDOW, facts.transaction_date
    )
    return DeviceHistory(distinct_documents_total=total, distinct_documents_24h=recent)


def destination_history(
    history: RiskHistoryRepository, facts: TransactionFacts, source_account, destination_account
) -> DestinationHistory:
    moment = facts.transaction_date
    other_payers, rejections_from_other_payers = history.count_other_payers_to_destination(
        destination_account.id, source_account.id, moment - timedelta(hours=policy.FAN_IN_WINDOW_HOURS), moment
    )
    return DestinationHistory(
        distinct_payers_24h=other_payers + 1, rejections_from_distinct_payers_24h=rejections_from_other_payers
    )


def ip_history(history: RiskHistoryRepository, facts: TransactionFacts, source_account) -> IpHistory:
    moment = facts.transaction_date
    other_payers = history.count_other_payers_from_ip(facts.ip_address, source_account.id, moment - IP_WINDOW, moment)
    return IpHistory(distinct_payers_1h=other_payers + 1)


def build_risk_context(
    payload: dict, source_account, destination_account, destination_participant, history: RiskHistoryRepository
) -> RiskContext:
    facts = transaction_facts(payload, source_account, destination_account, destination_participant)
    payer, beneficiary = payer_and_beneficiary_history(history, facts, source_account, destination_account)
    return RiskContext(
        transaction=facts,
        payer=payer,
        beneficiary=beneficiary,
        device=device_history(history, facts),
        destination=destination_history(history, facts, source_account, destination_account),
        ip=ip_history(history, facts, source_account),
    )
