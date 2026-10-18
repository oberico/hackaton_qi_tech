from tests.utils.request_generator import RequestGenerator

PIX_TRANSACTION_PATH = "/pix/transaction"


class PixRequests:
    def __init__(self, api: RequestGenerator, internal_headers: dict):
        self.api = api
        self.internal_headers = internal_headers

    def post_transaction(self, payload: dict) -> tuple:
        return self.api.post(PIX_TRANSACTION_PATH, body=payload, headers=self.internal_headers)
