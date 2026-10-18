from datetime import datetime, timedelta, timezone

from tests.utils import ObjectGenerator, PayloadGenerator, RandomGenerator, RequestGenerator

BRASILIA = timezone(timedelta(hours=-3))


def days_ago_at(days: int, hour: int, minute: int = 0) -> datetime:
    day = datetime.now(BRASILIA) - timedelta(days=days)
    return day.replace(hour=hour, minute=minute, second=0, microsecond=0)


def reasons_by_code(response: dict) -> dict:
    return {reason["code"]: reason for reason in response["metadata"]["reasons"]}


def new_destination() -> dict:
    return {
        "beneficiary_document": RandomGenerator.cpf(),
        "destination_account_number": RandomGenerator.account_number(),
        "destination_opening_date": days_ago_at(15, 9).isoformat(),
    }


def reject_first_pix(payer_document: str, account_number: str, moment: datetime, amount: int) -> None:
    destination = new_destination()
    for hours_before in (2, 1):
        ObjectGenerator.create_pix_transaction(amount=5000, transaction_date=moment - timedelta(hours=hours_before), **destination)
    response = post(
        payer_document=payer_document, source_account_number=account_number, amount=amount, transaction_date=moment, **destination
    )
    assert response["status"] == "rejected"


def post(**payload_fields) -> dict:
    payload = PayloadGenerator.create_pix_transaction_payload(**payload_fields)
    status, response = RequestGenerator.POST_pix_transaction(payload)
    assert status == 201, response
    return response


class TestPixTransactionDepthRules:
    def test_amount_above_the_ceiling_learned_from_the_payer_history_requires_two_factor(self):
        payer_document, account_number, device_id = RandomGenerator.cpf(), RandomGenerator.account_number(), RandomGenerator.device_id()
        ObjectGenerator.create_payer_history(
            payer_document, 5, amount=10000, source_account_number=account_number, device_id=device_id
        )

        response = post(
            payer_document=payer_document,
            source_account_number=account_number,
            device_id=device_id,
            amount=200000,
            transaction_date=days_ago_at(1, 14),
        )

        assert response["status"] == "two_factor_required"
        assert response["metadata"]["decision_basis"] == "single_suspicious_axis"
        ceiling = reasons_by_code(response)["HOW_ABOVE_CUSTOMER_CEILING"]
        assert ceiling["level"] == "suspicious"
        assert ceiling["observed"] == {"amount": 200000}
        assert ceiling["threshold"] == {"ceiling": 157500}

    def test_first_pix_below_the_reference_ceiling_does_not_trigger_the_customer_ceiling(self):
        response = post(amount=150000, transaction_date=days_ago_at(1, 14))

        assert response["metadata"]["payer_maturity_phase"] == 0
        assert "HOW_ABOVE_CUSTOMER_CEILING" not in reasons_by_code(response)

    def test_amount_between_two_hundred_and_one_thousand_reais_at_three_am_requires_two_factor(self):
        payer_document, account_number, device_id = RandomGenerator.cpf(), RandomGenerator.account_number(), RandomGenerator.device_id()
        ObjectGenerator.create_payer_history(
            payer_document, 3, amount=5000, source_account_number=account_number, device_id=device_id
        )

        response = post(
            payer_document=payer_document,
            source_account_number=account_number,
            device_id=device_id,
            amount=50000,
            transaction_date=days_ago_at(1, 3),
        )

        assert response["status"] == "two_factor_required"
        assert response["metadata"]["decision_basis"] == "single_suspicious_axis"
        early_morning = reasons_by_code(response)["HOW_EARLY_MORNING_AMOUNT"]
        assert early_morning["level"] == "suspicious"
        assert early_morning["observed"] == {"amount": 50000, "local_hour": 3}

    def test_same_amount_in_the_afternoon_is_approved(self):
        payer_document, account_number, device_id = RandomGenerator.cpf(), RandomGenerator.account_number(), RandomGenerator.device_id()
        ObjectGenerator.create_payer_history(
            payer_document, 3, amount=5000, source_account_number=account_number, device_id=device_id
        )

        response = post(
            payer_document=payer_document,
            source_account_number=account_number,
            device_id=device_id,
            amount=50000,
            transaction_date=days_ago_at(1, 15),
        )

        assert response["status"] == "approved"
        assert "HOW_EARLY_MORNING_AMOUNT" not in reasons_by_code(response)

    def test_new_device_for_a_payer_with_other_known_devices_requires_two_factor_without_the_floor(self):
        payer_document, account_number = RandomGenerator.cpf(), RandomGenerator.account_number()
        ObjectGenerator.create_payer_history(
            payer_document, 3, amount=5000, source_account_number=account_number, device_id=RandomGenerator.device_id()
        )

        response = post(
            payer_document=payer_document,
            source_account_number=account_number,
            device_id=RandomGenerator.device_id(),
            amount=5000,
            transaction_date=days_ago_at(1, 15),
        )

        assert response["status"] == "two_factor_required"
        assert response["metadata"]["decision_basis"] == "single_suspicious_axis"
        assert response["metadata"]["axes"]["who"] == "suspicious"
        device_unknown = reasons_by_code(response)["WHO_DEVICE_UNKNOWN"]
        assert device_unknown["level"] == "suspicious"
        assert device_unknown["observed"] == {"device_trust": "unknown", "known_devices_count": 1}
        assert response["metadata"]["floors"] == []

    def test_first_pix_of_a_payer_from_a_new_device_is_not_a_device_signal(self):
        response = post(amount=5000, transaction_date=days_ago_at(1, 15))

        assert response["status"] == "approved"
        assert "WHO_DEVICE_UNKNOWN" not in reasons_by_code(response)

    def test_smaller_retry_within_ten_minutes_of_a_rejection_is_a_probe_and_requires_two_factor(self):
        payer_document, account_number = RandomGenerator.cpf(), RandomGenerator.account_number()
        rejected_at = days_ago_at(2, 14)
        reject_first_pix(payer_document, account_number, rejected_at, 100000)

        response = post(
            payer_document=payer_document,
            source_account_number=account_number,
            amount=50000,
            transaction_date=rejected_at + timedelta(minutes=3),
        )

        assert response["status"] == "two_factor_required"
        assert response["metadata"]["decision_basis"] == "single_suspicious_axis"
        retry = reasons_by_code(response)["HOW_RETRY_AFTER_REJECTION"]
        assert retry["level"] == "suspicious"
        assert retry["observed"] == {"minutes_since_rejection": 3, "amount": 50000, "last_rejected_amount": 100000}
        assert retry["threshold"] == {"window_minutes": 10}

    def test_retry_after_ten_minutes_or_with_an_equal_amount_is_not_a_probe(self):
        payer_document, account_number = RandomGenerator.cpf(), RandomGenerator.account_number()
        rejected_at = days_ago_at(2, 14)
        reject_first_pix(payer_document, account_number, rejected_at, 100000)

        late = post(
            payer_document=payer_document,
            source_account_number=account_number,
            amount=50000,
            transaction_date=rejected_at + timedelta(minutes=10),
        )
        same_amount = post(
            payer_document=payer_document,
            source_account_number=account_number,
            amount=100000,
            transaction_date=rejected_at + timedelta(minutes=11),
        )

        assert "HOW_RETRY_AFTER_REJECTION" not in reasons_by_code(late)
        assert "HOW_RETRY_AFTER_REJECTION" not in reasons_by_code(same_amount)

    def test_large_pix_after_a_ten_real_test_pix_to_a_new_destination_requires_two_factor(self):
        payer_document, account_number, device_id = RandomGenerator.cpf(), RandomGenerator.account_number(), RandomGenerator.device_id()
        destination = {"beneficiary_document": RandomGenerator.cpf(), "destination_account_number": RandomGenerator.account_number()}
        moment = days_ago_at(1, 14)
        payer = {"payer_document": payer_document, "source_account_number": account_number, "device_id": device_id}
        test_response = post(amount=1000, transaction_date=moment - timedelta(minutes=5), **payer, **destination)

        response = post(amount=20000, transaction_date=moment, **payer, **destination)

        assert test_response["status"] == "approved"
        assert response["status"] == "two_factor_required"
        assert response["metadata"]["decision_basis"] == "single_suspicious_axis"
        test_pix = reasons_by_code(response)["HOW_TEST_PIX"]
        assert test_pix["level"] == "suspicious"
        assert test_pix["observed"] == {"amount": 20000, "small_amount_to_destination_last_15min": True}

    def test_large_pix_after_a_small_pix_above_ten_reais_or_to_a_known_destination_is_not_a_test_pix(self):
        payer_document, account_number, device_id = RandomGenerator.cpf(), RandomGenerator.account_number(), RandomGenerator.device_id()
        payer = {"payer_document": payer_document, "source_account_number": account_number, "device_id": device_id}
        moment = days_ago_at(1, 14)
        above_ten = {"beneficiary_document": RandomGenerator.cpf(), "destination_account_number": RandomGenerator.account_number()}
        known = {"beneficiary_document": RandomGenerator.cpf(), "destination_account_number": RandomGenerator.account_number()}
        ObjectGenerator.create_pix_transaction(amount=5000, transaction_date=moment - timedelta(days=2), **payer, **known)
        ObjectGenerator.create_pix_transaction(amount=1001, transaction_date=moment - timedelta(minutes=5), **payer, **above_ten)
        ObjectGenerator.create_pix_transaction(amount=1000, transaction_date=moment - timedelta(minutes=4), **payer, **known)

        after_above_ten = post(amount=30000, transaction_date=moment, **payer, **above_ten)
        after_known = post(amount=30000, transaction_date=moment + timedelta(minutes=20), **payer, **known)

        assert "HOW_TEST_PIX" not in reasons_by_code(after_above_ten)
        assert "HOW_TEST_PIX" not in reasons_by_code(after_known)
