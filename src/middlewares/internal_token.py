import hmac

from fastapi import FastAPI, Request

from constants import INTERNAL_ROUTE_PREFIXES, INTERNAL_TOKEN
from errors.custom_errors import ForbiddenNotInternal
from errors.handlers import qi_exception_to_response

INTERNAL_TOKEN_HEADER = "INTERNAL-TOKEN"


def is_valid_internal_token(received_token: str) -> bool:
    if not INTERNAL_TOKEN or not received_token:
        return False
    return hmac.compare_digest(received_token.encode("utf-8"), INTERNAL_TOKEN.encode("utf-8"))


def register_internal_token_middleware(application: FastAPI) -> None:
    @application.middleware("http")
    async def check_internal_token(request: Request, call_next):
        if not request.url.path.startswith(INTERNAL_ROUTE_PREFIXES):
            return await call_next(request)

        if not is_valid_internal_token(request.headers.get(INTERNAL_TOKEN_HEADER)):
            return qi_exception_to_response(ForbiddenNotInternal())

        return await call_next(request)
