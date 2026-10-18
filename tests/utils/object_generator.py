from datetime import datetime, timedelta, timezone
from typing import List

from tests.utils.payload_generator import PayloadGenerator
from tests.utils.random_generator import RandomGenerator
from tests.utils.request_generator import RequestGenerator

CREATED_STATUSES = (200, 201)
ONE_DAY = timedelta(days=1)


class ObjectGenerator:
    @staticmethod
    def create_pix_transaction(**payload_fields) -> dict:
        payload = PayloadGenerator.create_pix_transaction_payload(**payload_fields)
        status, response = RequestGenerator.POST_pix_transaction(payload)
        assert status in CREATED_STATUSES, f"could not create the pix {payload['id']}: {status} {response}"
        return response

    @staticmethod
    def create_payer_history(payer_document: str, count: int, interval: timedelta = ONE_DAY, **payload_fields) -> List[dict]:
        first_transaction_date = datetime.now(timezone.utc) - interval * (count + 1)
        payload_fields.setdefault("source_account_number", RandomGenerator.account_number())
        return [
            ObjectGenerator.create_pix_transaction(
                payer_document=payer_document, transaction_date=first_transaction_date + interval * index, **payload_fields
            )
            for index in range(count)
        ]
