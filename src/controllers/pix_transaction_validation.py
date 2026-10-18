import ipaddress
from datetime import datetime, timedelta, timezone

from constants import OWN_PARTICIPANT
from errors import (
    AccountConflict,
    AccountOpenedAfterTransaction,
    InvalidIpAddress,
    SourceAndDestinationAccountsAreTheSame,
    TransactionDateInFuture,
)
from utils.document import validate_document

FUTURE_TOLERANCE_MINUTES = 5


def validate_document_numbers(payload: dict) -> None:
    for account_key in ("source_account", "destination_account"):
        validate_document(payload[account_key]["owner"]["document_number"])


def validate_opening_dates(payload: dict) -> None:
    tx_date = datetime.fromisoformat(payload["transaction_date"])
    for account_key in ("source_account", "destination_account"):
        opening_date = datetime.fromisoformat(payload[account_key]["opening_date"])
        if opening_date > tx_date:
            raise AccountOpenedAfterTransaction()


def validate_transaction_date_not_in_future(payload: dict) -> None:
    tx_date = datetime.fromisoformat(payload["transaction_date"])
    now = datetime.now(timezone.utc)
    if tx_date > now + timedelta(minutes=FUTURE_TOLERANCE_MINUTES):
        raise TransactionDateInFuture()


def validate_different_accounts(payload: dict) -> None:
    dest = payload["destination_account"]
    if dest["participant"] == OWN_PARTICIPANT:
        src = payload["source_account"]
        if src["branch"] == dest["branch"] and src["account_number"] == dest["account_number"]:
            raise SourceAndDestinationAccountsAreTheSame()


def validate_ip_address(payload: dict) -> None:
    ip_str = payload["source"]["ip"]
    try:
        ipaddress.ip_address(ip_str)
    except ValueError:
        raise InvalidIpAddress()


def validate_account_conflicts(payload: dict, account_repository) -> None:
    if account_repository is None:
        return
    for ispb, account_data in (
        (OWN_PARTICIPANT, payload["source_account"]),
        (payload["destination_account"]["participant"], payload["destination_account"]),
    ):
        match = account_repository.find_with_holder(
            ispb=ispb,
            branch=account_data["branch"],
            account_number=account_data["account_number"],
        )
        if match is not None:
            account, holder = match
            if holder.document_number != account_data["owner"]["document_number"]:
                raise AccountConflict()
            if account.opening_date != datetime.fromisoformat(account_data["opening_date"]):
                raise AccountConflict()


def validate_payload_semantics(payload: dict, account_repository=None) -> None:
    validate_document_numbers(payload)
    validate_opening_dates(payload)
    validate_transaction_date_not_in_future(payload)
    validate_different_accounts(payload)
    validate_ip_address(payload)
    validate_account_conflicts(payload, account_repository)
