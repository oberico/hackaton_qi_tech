from errors import InvalidCpf
from utils.cpf import is_valid_cpf


def validate_document_numbers(payload: dict) -> None:
    for account_key in ("source_account", "destination_account"):
        doc = payload[account_key]["owner"]["document_number"]
        if "/" not in doc and not is_valid_cpf(doc):
            raise InvalidCpf()


def validate_payload_semantics(payload: dict) -> None:
    validate_document_numbers(payload)
