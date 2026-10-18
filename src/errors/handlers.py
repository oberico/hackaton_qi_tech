from fastapi.responses import JSONResponse

from errors.base_error import QIException


def qi_exception_to_response(exception: QIException, headers: dict = None) -> JSONResponse:
    body = {
        "title": exception.title,
        "description": exception.description,
        "translation": exception.translation,
        "code": exception.code,
    }
    return JSONResponse(status_code=exception.http_status, content=body, headers=headers)
