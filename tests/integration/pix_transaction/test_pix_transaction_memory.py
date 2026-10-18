from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

from tests.utils import DatabaseInspector, ObjectGenerator, PayloadGenerator, RandomGenerator, RequestGenerator

BRASILIA = timezone(timedelta(hours=-3))
SMALL_AMOUNT = 5000
PARALLEL_PIX = 10
ABOVE_UNREGISTERED_DEVICE_LIMIT = 50000


def days_ago_at(days: int, hour: int, minute: int = 0) -> datetime:
    day = datetime.now(BRASILIA) - timedelta(days=days)
    return day.replace(hour=hour, minute=minute, second=0, microsecond=0)


def pair() -> dict:
    return {
        "payer_document": RandomGenerator.cpf(),
        "source_account_number": RandomGenerator.account_number(),
        "device_id": RandomGenerator.device_id(),
        "beneficiary_document": RandomGenerator.cpf(),
        "destination_account_number": RandomGenerator.account_number(),
    }


def other_beneficiary() -> dict:
    return {"beneficiary_document": RandomGenerator.cpf(), "destination_account_number": RandomGenerator.account_number()}


def young_destination(fields: dict) -> dict:
    return {**fields, "destination_opening_date": days_ago_at(15, 9).isoformat()}


def post(payload: dict, expected_status: int = 201) -> dict:
    status, response = RequestGenerator.POST_pix_transaction(payload)
    assert status == expected_status, response
    return response


class TestPixTransactionMemory:
    def test_approved_pix_records_the_device_and_the_counterparty(self):
        transaction_date = days_ago_at(2, 14)
        payload = PayloadGenerator.create_pix_transaction_payload(**pair(), amount=SMALL_AMOUNT, transaction_date=transaction_date)

        response = post(payload)

        assert response["status"] == "approved"
        device = DatabaseInspector.account_device(payload)
        assert device["approved_count"] == 1
        assert device["first_approved_at"] == device["last_approved_at"] == transaction_date
        counterparty = DatabaseInspector.account_counterparty(payload)
        assert counterparty["approved_count"] == 1
        assert counterparty["approved_amount_minor"] == SMALL_AMOUNT
        assert counterparty["first_approved_at"] == counterparty["last_approved_at"] == transaction_date

    def test_two_factor_pix_records_nothing_in_memory(self):
        payload = PayloadGenerator.create_pix_transaction_payload(**young_destination(pair()), transaction_date=days_ago_at(2, 14))

        response = post(payload)

        assert response["status"] == "two_factor_required"
        assert DatabaseInspector.account_device(payload) is None
        assert DatabaseInspector.account_counterparty(payload) is None

    def test_rejected_pix_records_nothing_in_memory(self):
        fields = young_destination(pair())
        burst_start = days_ago_at(2, 14)
        for index in range(2):
            ObjectGenerator.create_pix_transaction(
                payer_document=fields["payer_document"],
                source_account_number=fields["source_account_number"],
                device_id=fields["device_id"],
                transaction_date=burst_start + timedelta(minutes=index),
            )
        payload = PayloadGenerator.create_pix_transaction_payload(**fields, transaction_date=burst_start + timedelta(minutes=2))

        response = post(payload)

        assert response["status"] == "rejected"
        assert DatabaseInspector.account_device(payload)["approved_count"] == 2
        assert DatabaseInspector.account_counterparty(payload) is None

    def test_parallel_approved_pix_for_the_same_pair_are_all_counted(self):
        fields = pair()
        dates = [days_ago_at(day, 14) for day in range(1, PARALLEL_PIX + 1)]
        payloads = [
            PayloadGenerator.create_pix_transaction_payload(**fields, amount=SMALL_AMOUNT, transaction_date=transaction_date)
            for transaction_date in dates
        ]

        with ThreadPoolExecutor(max_workers=PARALLEL_PIX) as executor:
            responses = list(executor.map(post, payloads))

        assert {response["status"] for response in responses} == {"approved"}
        device = DatabaseInspector.account_device(payloads[0])
        assert device["approved_count"] == PARALLEL_PIX
        assert (device["first_approved_at"], device["last_approved_at"]) == (min(dates), max(dates))
        counterparty = DatabaseInspector.account_counterparty(payloads[0])
        assert counterparty["approved_count"] == PARALLEL_PIX
        assert counterparty["approved_amount_minor"] == SMALL_AMOUNT * PARALLEL_PIX
        assert (counterparty["first_approved_at"], counterparty["last_approved_at"]) == (min(dates), max(dates))

    def test_identical_retry_does_not_count_the_approved_pix_twice(self):
        payload = PayloadGenerator.create_pix_transaction_payload(**pair(), amount=SMALL_AMOUNT, transaction_date=days_ago_at(2, 14))
        post(payload)

        post(payload, expected_status=200)

        assert DatabaseInspector.account_device(payload)["approved_count"] == 1
        assert DatabaseInspector.account_counterparty(payload)["approved_count"] == 1

    def test_device_first_approved_more_than_90_days_ago_is_still_trusted(self):
        fields = pair()
        ObjectGenerator.create_pix_transaction(**fields, amount=SMALL_AMOUNT, transaction_date=days_ago_at(100, 14))
        payload = PayloadGenerator.create_pix_transaction_payload(
            **{**fields, **other_beneficiary()}, amount=ABOVE_UNREGISTERED_DEVICE_LIMIT, transaction_date=days_ago_at(1, 14)
        )

        response = post(payload)

        assert response["status"] == "approved"
        assert response["metadata"]["floors"] == []

    def test_beneficiary_paid_twice_more_than_90_days_ago_is_still_recurrent(self):
        fields = pair()
        for days in (120, 100):
            ObjectGenerator.create_pix_transaction(**fields, amount=SMALL_AMOUNT, transaction_date=days_ago_at(days, 14))
        burst_start = days_ago_at(1, 14)
        for index in range(2):
            ObjectGenerator.create_pix_transaction(
                **{**fields, **other_beneficiary()}, amount=SMALL_AMOUNT, transaction_date=burst_start + timedelta(minutes=index)
            )
        payload = PayloadGenerator.create_pix_transaction_payload(
            **fields, amount=SMALL_AMOUNT, transaction_date=burst_start + timedelta(minutes=2)
        )

        response = post(payload)

        assert response["status"] == "approved"
        assert response["metadata"]["decision_basis"] == "trust_downgrade"
        assert response["metadata"]["trust"] == ["TRUST_RECURRENT_BENEFICIARY"]
