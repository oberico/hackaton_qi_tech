import requests

DEFAULT_TIMEOUT_SECONDS = 10


class RequestGenerator:
    def __init__(self, base_url: str, timeout: int = DEFAULT_TIMEOUT_SECONDS):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def get(self, path: str, headers: dict = None, params: dict = None) -> tuple:
        return self._send("GET", path, headers=headers, params=params)

    def post(self, path: str, body: dict = None, headers: dict = None) -> tuple:
        return self._send("POST", path, body=body, headers=headers)

    def put(self, path: str, body: dict = None, headers: dict = None) -> tuple:
        return self._send("PUT", path, body=body, headers=headers)

    def delete(self, path: str, headers: dict = None) -> tuple:
        return self._send("DELETE", path, headers=headers)

    def request_with_headers(self, method: str, path: str, body: dict = None, headers: dict = None) -> tuple:
        response = self._request(method, path, body=body, headers=headers)
        return response.status_code, self._parse(response), response.headers

    def _send(self, method: str, path: str, body: dict = None, headers: dict = None, params: dict = None) -> tuple:
        response = self._request(method, path, body=body, headers=headers, params=params)
        return response.status_code, self._parse(response)

    def _request(self, method: str, path: str, body: dict = None, headers: dict = None, params: dict = None):
        return requests.request(
            method,
            f"{self.base_url}{path}",
            json=body,
            headers=headers,
            params=params,
            timeout=self.timeout,
        )

    @staticmethod
    def _parse(response) -> dict:
        try:
            return response.json()
        except ValueError:
            return None
