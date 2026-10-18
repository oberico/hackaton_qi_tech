from fastapi import Body, status
from fastapi.responses import JSONResponse

from controllers import PixTransactionController
from database import get_context


class PixTransactionResource:
    def on_post_transaction(self, payload: dict = Body(...)) -> JSONResponse:
        controller = PixTransactionController(get_context().session)
        return JSONResponse(content=controller.create(payload), status_code=status.HTTP_201_CREATED)
