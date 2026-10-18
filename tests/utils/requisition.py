from os import environ

from requests import Response, request
from requests.exceptions import ConnectionError as RequestsConnectionError

DEFAULT_API_URL = "http://localhost:8001"
DEFAULT_TIMEOUT_SECONDS = 10
API_OFFLINE = "Could not reach the API at {base_url}. Start it with: docker compose up -d"


class BaseConnectorResponse:
    def __init__(self, response: Response, endpoint: str, method: str, headers: dict, payload) -> None:
        self.endpoint = endpoint
        self.method = method
        self.payload = payload
        self.headers = headers
        self.response = response
        self.response_status = response.status_code
        self.response_headers = response.headers
        self.response_json = BaseConnectorResponse.parse_json(response)

    @staticmethod
    def parse_json(response: Response):
        try:
            return response.json()
        except ValueError:
            return None


class ClientRequisition:
    @staticmethod
    def base_url() -> str:
        return environ.get("API_URL", DEFAULT_API_URL).rstrip("/")

    @staticmethod
    def send(method: str, endpoint: str, payload=None, headers: dict = None, data: str = None) -> BaseConnectorResponse:
        headers = dict(headers or {})
        base_url = ClientRequisition.base_url()
        try:
            response = request(
                method.upper(), f"{base_url}{endpoint}", json=payload, data=data, headers=headers, timeout=DEFAULT_TIMEOUT_SECONDS
            )
        except RequestsConnectionError:
            raise RuntimeError(API_OFFLINE.format(base_url=base_url)) from None
        return BaseConnectorResponse(response=response, endpoint=endpoint, method=method, headers=headers, payload=payload)
