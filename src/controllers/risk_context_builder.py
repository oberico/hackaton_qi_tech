import ipaddress
from datetime import datetime
from typing import Optional

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


def build_risk_context(payload: dict, source_account, destination_account, destination_participant) -> RiskContext:
    return RiskContext(
        transaction=transaction_facts(payload, source_account, destination_account, destination_participant),
        payer=neutral_payer_history(),
        beneficiary=BeneficiaryRelationship(approved_count=0, first_approved_at=None),
        device=DeviceHistory(distinct_documents_total=0, distinct_documents_24h=0),
        destination=DestinationHistory(distinct_payers_24h=0, rejections_from_distinct_payers_24h=0),
        ip=IpHistory(distinct_payers_1h=0),
    )
