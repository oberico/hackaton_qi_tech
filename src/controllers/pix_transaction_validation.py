from errors import InvalidCnpj, InvalidCpf
from utils.cnpj import is_valid_cnpj
from utils.cpf import is_valid_cpf


def validate_document_numbers(payload: dict) -> None:
    for account_key in ("source_account", "destination_account"):
        doc = payload[account_key]["owner"]["document_number"]
        if "/" in doc:
            if not is_valid_cnpj(doc):
                raise InvalidCnpj()
        elif not is_valid_cpf(doc):
            raise InvalidCpf()


def validate_payload_semantics(payload: dict) -> None:
    validate_document_numbers(payload)
