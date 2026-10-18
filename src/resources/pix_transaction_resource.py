from fastapi import Body, status
from fastapi.responses import JSONResponse

from controllers import PixTransactionController
from utils.schema_handler import SchemaHandler


class PixTransactionResource:
    @SchemaHandler.validate("post_pix_transaction.json")
    def on_post_transaction(self, payload: dict = Body(...)) -> JSONResponse:
        controller = PixTransactionController()
        body, created = controller.create(payload)
        return JSONResponse(content=body, status_code=status.HTTP_201_CREATED if created else status.HTTP_200_OK)
