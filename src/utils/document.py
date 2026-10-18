from errors import InvalidCnpj, InvalidCpf
from utils.cnpj import is_valid_cnpj
from utils.cpf import is_valid_cpf


def is_cnpj(document: str) -> bool:
    return "/" in document


def is_cpf(document: str) -> bool:
    return not is_cnpj(document)


def is_valid_document(document: str) -> bool:
    return is_valid_cnpj(document) if is_cnpj(document) else is_valid_cpf(document)


def validate_document(document: str) -> None:
    if is_cnpj(document):
        if not is_valid_cnpj(document):
            raise InvalidCnpj()
    elif not is_valid_cpf(document):
        raise InvalidCpf()
