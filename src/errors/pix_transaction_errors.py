from errors.base_error import QIException


class PixIdReusedWithDifferentPayload(QIException):
    code = "RNV001024"

    def __init__(self) -> None:
        title = "Pix Id Reused With Different Payload"
        http_status = 422
        description = "A Pix with this id was already received with a different payload; the id cannot be reused."
        translation = "Já existe um Pix recebido com este id e conteúdo diferente; o id não pode ser reutilizado."
        super().__init__(title, self.code, http_status, description, translation)


class PixTransactionNotFound(QIException):
    code = "RNV001039"

    def __init__(self) -> None:
        title = "Pix Transaction Not Found"
        http_status = 404
        description = "No Pix transaction was found with the given id."
        translation = "Nenhum Pix foi encontrado com o id informado."
        super().__init__(title, self.code, http_status, description, translation)


class InvalidCpf(QIException):
    code = "RNV001002"

    def __init__(self) -> None:
        title = "Invalid CPF"
        http_status = 422
        description = "The document number has invalid CPF check digits."
        translation = "O CPF informado possui dígitos verificadores inválidos."
        super().__init__(title, self.code, http_status, description, translation)


class InvalidCnpj(QIException):
    code = "RNV001020"

    def __init__(self) -> None:
        title = "Invalid CNPJ"
        http_status = 422
        description = "The document number has invalid CNPJ check digits."
        translation = "O CNPJ informado possui dígitos verificadores inválidos."
        super().__init__(title, self.code, http_status, description, translation)
