from os import environ

from tests.utils.requisition import BaseConnectorResponse, ClientRequisition

INTERNAL_TOKEN = environ.get("INTERNAL_TOKEN", "internal-token-dev")
INTERNAL_HEADERS = {"INTERNAL-TOKEN": INTERNAL_TOKEN}
PIX_TRANSACTION_ENDPOINT = "/pix/transaction"
JSON_CONTENT_TYPE = {"Content-Type": "application/json"}


class RequestGenerator:
    @staticmethod
    def POST_pix_transaction(pix_transaction_payload) -> tuple:
        response = ClientRequisition.send("POST", PIX_TRANSACTION_ENDPOINT, payload=pix_transaction_payload, headers=INTERNAL_HEADERS)
        return response.response_status, response.response_json

    @staticmethod
    def POST_pix_transaction_raw_body(raw_body: str) -> tuple:
        headers = {**INTERNAL_HEADERS, **JSON_CONTENT_TYPE}
        response = ClientRequisition.send("POST", PIX_TRANSACTION_ENDPOINT, data=raw_body, headers=headers)
        return response.response_status, response.response_json

    @staticmethod
    def POST_pix_transaction_with_token(pix_transaction_payload: dict, internal_token: str = None) -> tuple:
        headers = {} if internal_token is None else {"INTERNAL-TOKEN": internal_token}
        response = ClientRequisition.send("POST", PIX_TRANSACTION_ENDPOINT, payload=pix_transaction_payload, headers=headers)
        return response.response_status, response.response_json

    @staticmethod
    def GET_pix_transaction(transaction_id: str) -> tuple:
        response = ClientRequisition.send("GET", f"{PIX_TRANSACTION_ENDPOINT}/{transaction_id}", headers=INTERNAL_HEADERS)
        return response.response_status, response.response_json

    @staticmethod
    def GET_home() -> tuple:
        response = ClientRequisition.send("GET", "/")
        return response.response_status, response.response_json

    @staticmethod
    def GET_health_check() -> tuple:
        response = ClientRequisition.send("GET", "/health_check")
        return response.response_status, response.response_json

    @staticmethod
    def send_without_token(method: str, endpoint: str) -> BaseConnectorResponse:
        return ClientRequisition.send(method, endpoint)
