from fastapi import Body, status
from fastapi.responses import JSONResponse

from controllers import PixTransactionController
from utils.schema_handler import SchemaHandler


class PixTransactionResource:
    @SchemaHandler.validate("post_pix_transaction.json")
    def on_post_transaction(self, payload: dict = Body(...)) -> JSONResponse:
        controller = PixTransactionController()
        return JSONResponse(content=controller.create(payload), status_code=status.HTTP_201_CREATED)

    def on_get_transaction(self, transaction_id: str) -> JSONResponse:
        controller = PixTransactionController()
        return JSONResponse(content=controller.get(transaction_id), status_code=status.HTTP_200_OK)
