from datetime import datetime, timedelta, timezone

from errors import (
    AccountOpenedAfterTransaction,
    InvalidCnpj,
    InvalidCpf,
    TransactionDateInFuture,
)
from utils.cnpj import is_valid_cnpj
from utils.cpf import is_valid_cpf

FUTURE_TOLERANCE_MINUTES = 5


def validate_document_numbers(payload: dict) -> None:
    for account_key in ("source_account", "destination_account"):
        doc = payload[account_key]["owner"]["document_number"]
        if "/" in doc:
            if not is_valid_cnpj(doc):
                raise InvalidCnpj()
        elif not is_valid_cpf(doc):
            raise InvalidCpf()


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


def validate_payload_semantics(payload: dict) -> None:
    validate_document_numbers(payload)
    validate_opening_dates(payload)
    validate_transaction_date_not_in_future(payload)
