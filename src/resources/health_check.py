from fastapi import status
from fastapi.responses import JSONResponse

from constants import SERVICE_NAME


class HealthCheckResource:
    def on_get_home(self) -> JSONResponse:
        return JSONResponse(content={"service": SERVICE_NAME}, status_code=status.HTTP_200_OK)

    def on_get_health_check(self) -> JSONResponse:
        return JSONResponse(content={"status": "ok"}, status_code=status.HTTP_200_OK)
