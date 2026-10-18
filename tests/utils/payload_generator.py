import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from tests.utils.random_generator import RandomGenerator

CHALLENGE_EXAMPLE_PATH = Path(__file__).parent.parent / "fixtures" / "challenge_example_payload.json"
BRASILIA = timezone(timedelta(hours=-3))
LISTED_PARTICIPANT = "60701190"
OLD_ACCOUNT_OPENING_DATE = "2025-03-02T10:00:00-03:00"


def iso_in_brasilia(moment: datetime) -> str:
    return moment.astimezone(BRASILIA).replace(microsecond=0).isoformat()


class PayloadGenerator:
    @staticmethod
    def create_challenge_example_payload(transaction_id: str = None) -> dict:
        payload = json.loads(CHALLENGE_EXAMPLE_PATH.read_text(encoding="utf-8"))
        payload["id"] = transaction_id or RandomGenerator.transaction_id()
        return payload

    @staticmethod
    def create_pix_transaction_payload(
        transaction_id: str = None,
        amount: int = 5000,
        transaction_date: datetime = None,
        payer_document: str = None,
        source_account_number: str = None,
        source_opening_date: str = OLD_ACCOUNT_OPENING_DATE,
        beneficiary_document: str = None,
        participant: str = LISTED_PARTICIPANT,
        destination_account_number: str = None,
        destination_opening_date: str = OLD_ACCOUNT_OPENING_DATE,
        device_id: str = None,
    ) -> dict:
        moment = transaction_date or datetime.now(timezone.utc) - timedelta(days=1)
        return {
            "id": transaction_id or RandomGenerator.transaction_id(),
            "amount": amount,
            "transaction_date": iso_in_brasilia(moment),
            "source_account": {
                "branch": "0001",
                "account_number": source_account_number or RandomGenerator.account_number(),
                "opening_date": source_opening_date,
                "owner": {"document_number": payer_document or RandomGenerator.cpf()},
            },
            "destination_account": {
                "participant": participant,
                "branch": "3675",
                "account_number": destination_account_number or RandomGenerator.account_number(),
                "opening_date": destination_opening_date,
                "owner": {"document_number": beneficiary_document or RandomGenerator.cpf()},
            },
            "source": {
                "device_id": device_id or RandomGenerator.device_id(),
                "channel": "app",
                "ip": "198.51.100.23",
                "geolocation": {"latitude": -23.56, "longitude": -46.65},
            },
        }
