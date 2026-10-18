from errors.base_error import QIException


class PixTransactionNotFound(QIException):
    code = "RNV001039"

    def __init__(self) -> None:
        title = "Pix Transaction Not Found"
        http_status = 404
        description = "No Pix transaction was found with the given id."
        translation = "Nenhum Pix foi encontrado com o id informado."
        super().__init__(title, self.code, http_status, description, translation)
