from datetime import datetime, timedelta, timezone

from tests.utils import ObjectGenerator, PayloadGenerator, RandomGenerator, RequestGenerator

BRASILIA = timezone(timedelta(hours=-3))
SMALL_AMOUNT = 5000
UNLISTED_PARTICIPANT = "12345678"


def days_ago_at(days: int, hour: int, minute: int = 0) -> datetime:
    day = datetime.now(BRASILIA) - timedelta(days=days)
    return day.replace(hour=hour, minute=minute, second=0, microsecond=0)


def reasons_by_code(response: dict) -> dict:
    return {reason["code"]: reason for reason in response["metadata"]["reasons"]}


def post(**payload_fields) -> dict:
    payload = PayloadGenerator.create_pix_transaction_payload(**payload_fields)
    status, response = RequestGenerator.POST_pix_transaction(payload)
    assert status == 201, response
    return response


def new_destination() -> dict:
    return {
        "beneficiary_document": RandomGenerator.cpf(),
        "destination_account_number": RandomGenerator.account_number(),
        "destination_opening_date": days_ago_at(15, 9).isoformat(),
    }


def unlisted_destination() -> dict:
    return {
        "beneficiary_document": RandomGenerator.cpf(),
        "participant": UNLISTED_PARTICIPANT,
        "destination_account_number": RandomGenerator.account_number(),
    }


def seed_payer_attempts(
    payer_document: str, account_number: str, start: datetime, count: int, interval: timedelta, device_id: str = None
) -> None:
    for index in range(count):
        ObjectGenerator.create_pix_transaction(
            payer_document=payer_document,
            source_account_number=account_number,
            device_id=device_id or RandomGenerator.device_id(),
            amount=SMALL_AMOUNT,
            transaction_date=start + interval * index,
        )


class TestPixTransactionHistoryWindows:
    def test_third_attempt_in_ten_minutes_is_suspicious_velocity_and_requires_two_factor(self):
        payer_document, account_number = RandomGenerator.cpf(), RandomGenerator.account_number()
        device_id = RandomGenerator.device_id()
        start = days_ago_at(3, 14)
        seed_payer_attempts(payer_document, account_number, start, 2, timedelta(minutes=3), device_id=device_id)

        response = post(
            payer_document=payer_document,
            source_account_number=account_number,
            device_id=device_id,
            amount=SMALL_AMOUNT,
            transaction_date=start + timedelta(minutes=6),
        )

        assert response["status"] == "two_factor_required"
        velocity = reasons_by_code(response)["HOW_VELOCITY_EXCEEDED"]
        assert velocity["level"] == "suspicious"
        assert velocity["observed"] == {"attempts": 3}

    def test_sixth_attempt_in_ten_minutes_is_critical_velocity_and_rejected(self):
        payer_document, account_number = RandomGenerator.cpf(), RandomGenerator.account_number()
        start = days_ago_at(3, 14)
        seed_payer_attempts(payer_document, account_number, start, 5, timedelta(minutes=1))

        response = post(
            payer_document=payer_document,
            source_account_number=account_number,
            amount=SMALL_AMOUNT,
            transaction_date=start + timedelta(minutes=5),
        )

        assert response["status"] == "rejected"
        assert response["metadata"]["decision_basis"] == "critical_axis"
        velocity = reasons_by_code(response)["HOW_VELOCITY_EXCEEDED"]
        assert velocity["level"] == "critical"
        assert velocity["observed"] == {"attempts": 6}

    def test_attempts_older_than_ten_minutes_do_not_count_for_velocity(self):
        payer_document, account_number = RandomGenerator.cpf(), RandomGenerator.account_number()
        device_id = RandomGenerator.device_id()
        start = days_ago_at(3, 14)
        seed_payer_attempts(payer_document, account_number, start, 2, timedelta(minutes=1), device_id=device_id)

        response = post(
            payer_document=payer_document,
            source_account_number=account_number,
            device_id=device_id,
            amount=SMALL_AMOUNT,
            transaction_date=start + timedelta(minutes=12),
        )

        assert response["status"] == "approved"
        assert "HOW_VELOCITY_EXCEEDED" not in reasons_by_code(response)

    def test_night_amount_between_individuals_adds_the_previous_night_pix(self):
        payer_document, account_number = RandomGenerator.cpf(), RandomGenerator.account_number()
        night_start = days_ago_at(4, 20, 30)
        for hour in range(2):
            ObjectGenerator.create_pix_transaction(
                payer_document=payer_document,
                source_account_number=account_number,
                amount=50000,
                transaction_date=night_start + timedelta(hours=hour),
            )

        response = post(
            payer_document=payer_document,
            source_account_number=account_number,
            amount=SMALL_AMOUNT,
            transaction_date=night_start + timedelta(hours=2),
        )

        night_limit = reasons_by_code(response)["HOW_NIGHT_LIMIT_EXCEEDED"]
        assert night_limit["level"] == "suspicious"
        assert night_limit["observed"] == {"night_amount": 105000}
        assert response["status"] == "two_factor_required"

    def test_night_self_pix_does_not_count_for_the_night_amount(self):
        payer_document, account_number = RandomGenerator.cpf(), RandomGenerator.account_number()
        night_start = days_ago_at(4, 20, 30)
        for hour in range(2):
            ObjectGenerator.create_pix_transaction(
                payer_document=payer_document,
                source_account_number=account_number,
                beneficiary_document=payer_document,
                amount=50000,
                transaction_date=night_start + timedelta(hours=hour),
            )

        response = post(
            payer_document=payer_document,
            source_account_number=account_number,
            amount=SMALL_AMOUNT,
            transaction_date=night_start + timedelta(hours=2),
        )

        assert "HOW_NIGHT_LIMIT_EXCEEDED" not in reasons_by_code(response)
        assert response["status"] == "approved"

    def test_daily_amount_from_an_unknown_device_adds_the_same_day_pix_and_triggers_the_floor(self):
        payer_document, account_number = RandomGenerator.cpf(), RandomGenerator.account_number()
        device_id = RandomGenerator.device_id()
        morning = days_ago_at(5, 9)
        for hour in range(2):
            ObjectGenerator.create_pix_transaction(
                payer_document=payer_document,
                source_account_number=account_number,
                device_id=device_id,
                amount=50000,
                transaction_date=morning + timedelta(hours=hour),
            )

        response = post(
            payer_document=payer_document,
            source_account_number=account_number,
            device_id=device_id,
            amount=SMALL_AMOUNT,
            transaction_date=morning + timedelta(hours=2),
        )

        assert response["status"] == "two_factor_required"
        assert response["metadata"]["decision_basis"] == "regulatory_floor"
        assert response["metadata"]["floors"] == ["FLOOR_UNREGISTERED_DEVICE"]

    def test_unknown_device_pix_from_the_previous_day_does_not_count_for_the_daily_amount(self):
        payer_document, account_number = RandomGenerator.cpf(), RandomGenerator.account_number()
        device_id = RandomGenerator.device_id()
        morning = days_ago_at(5, 9)
        for hour in range(2):
            ObjectGenerator.create_pix_transaction(
                payer_document=payer_document,
                source_account_number=account_number,
                device_id=device_id,
                amount=50000,
                transaction_date=morning + timedelta(hours=hour),
            )

        response = post(
            payer_document=payer_document,
            source_account_number=account_number,
            device_id=device_id,
            amount=SMALL_AMOUNT,
            transaction_date=morning + timedelta(days=1),
        )

        assert response["status"] == "approved"
        assert response["metadata"]["floors"] == []

    def test_device_with_an_approved_pix_more_than_a_day_ago_is_trusted_and_skips_the_floor(self):
        payer_document, account_number = RandomGenerator.cpf(), RandomGenerator.account_number()
        device_id = RandomGenerator.device_id()
        first_use = days_ago_at(6, 10)
        ObjectGenerator.create_pix_transaction(
            payer_document=payer_document, source_account_number=account_number, device_id=device_id,
            amount=SMALL_AMOUNT, transaction_date=first_use,
        )

        response = post(
            payer_document=payer_document, source_account_number=account_number, device_id=device_id,
            amount=30000, transaction_date=first_use + timedelta(days=2),
        )

        assert response["status"] == "approved"
        assert response["metadata"]["floors"] == []

    def test_device_with_an_approved_pix_within_the_last_day_is_observing_and_skips_the_floor(self):
        payer_document, account_number = RandomGenerator.cpf(), RandomGenerator.account_number()
        device_id = RandomGenerator.device_id()
        first_use = days_ago_at(6, 10)
        ObjectGenerator.create_pix_transaction(
            payer_document=payer_document, source_account_number=account_number, device_id=device_id,
            amount=SMALL_AMOUNT, transaction_date=first_use,
        )

        response = post(
            payer_document=payer_document, source_account_number=account_number, device_id=device_id,
            amount=30000, transaction_date=first_use + timedelta(hours=1),
        )

        assert response["status"] == "approved"
        assert response["metadata"]["floors"] == []

    def test_device_with_only_non_approved_history_stays_unknown_and_triggers_the_floor(self):
        payer_document, account_number = RandomGenerator.cpf(), RandomGenerator.account_number()
        device_id = RandomGenerator.device_id()
        first_use = days_ago_at(6, 10)
        ObjectGenerator.create_pix_transaction(
            payer_document=payer_document, source_account_number=account_number, device_id=device_id,
            amount=50000, transaction_date=first_use,
        )

        response = post(
            payer_document=payer_document, source_account_number=account_number, device_id=device_id,
            amount=30000, transaction_date=first_use + timedelta(days=2),
        )

        assert response["status"] == "two_factor_required"
        assert response["metadata"]["floors"] == ["FLOOR_UNREGISTERED_DEVICE"]

    def test_first_pix_of_a_new_payer_on_a_device_used_by_three_holders_is_rejected(self):
        device_id = RandomGenerator.device_id()
        first_use = days_ago_at(12, 10)
        for index in range(3):
            ObjectGenerator.create_pix_transaction(
                device_id=device_id, amount=SMALL_AMOUNT, transaction_date=first_use + timedelta(days=2 * index)
            )

        response = post(device_id=device_id, amount=SMALL_AMOUNT, transaction_date=first_use + timedelta(days=6))

        assert response["status"] == "rejected"
        assert response["metadata"]["decision_basis"] == "critical_axis"
        assert response["metadata"]["payer_maturity_phase"] == 0
        compromised = reasons_by_code(response)["WHO_DEVICE_COMPROMISED"]
        assert compromised["level"] == "critical"
        assert compromised["observed"] == {"distinct_documents_total": 3, "distinct_documents_24h": 0}

    def test_device_used_by_two_holders_in_the_last_day_is_compromised(self):
        device_id = RandomGenerator.device_id()
        first_use = days_ago_at(12, 10)
        for index in range(2):
            ObjectGenerator.create_pix_transaction(
                device_id=device_id, amount=SMALL_AMOUNT, transaction_date=first_use + timedelta(hours=index)
            )

        response = post(device_id=device_id, amount=SMALL_AMOUNT, transaction_date=first_use + timedelta(hours=2))

        assert response["status"] == "rejected"
        compromised = reasons_by_code(response)["WHO_DEVICE_COMPROMISED"]
        assert compromised["observed"] == {"distinct_documents_total": 2, "distinct_documents_24h": 2}

    def test_device_shared_by_two_previous_holders_days_apart_is_not_compromised(self):
        device_id = RandomGenerator.device_id()
        first_use = days_ago_at(12, 10)
        for index in range(2):
            ObjectGenerator.create_pix_transaction(
                device_id=device_id, amount=SMALL_AMOUNT, transaction_date=first_use + timedelta(days=2 * index)
            )

        response = post(device_id=device_id, amount=SMALL_AMOUNT, transaction_date=first_use + timedelta(days=4))

        assert response["status"] == "approved"
        assert "WHO_DEVICE_COMPROMISED" not in reasons_by_code(response)

    def test_third_distinct_payer_in_a_day_to_a_new_destination_is_rejected_by_fan_in(self):
        destination = new_destination()
        start = days_ago_at(10, 10)
        for index in range(2):
            ObjectGenerator.create_pix_transaction(
                amount=SMALL_AMOUNT, transaction_date=start + timedelta(hours=index), **destination
            )

        response = post(amount=SMALL_AMOUNT, transaction_date=start + timedelta(hours=2), **destination)

        assert response["status"] == "rejected"
        fan_in = reasons_by_code(response)["WHERE_DESTINATION_FAN_IN"]
        assert fan_in["level"] == "critical"
        assert fan_in["observed"]["distinct_payers_24h"] == 3

    def test_repeated_pix_from_the_same_payer_to_a_new_destination_is_not_fan_in(self):
        destination = new_destination()
        payer_document, account_number = RandomGenerator.cpf(), RandomGenerator.account_number()
        start = days_ago_at(10, 10)
        for index in range(2):
            ObjectGenerator.create_pix_transaction(
                payer_document=payer_document, source_account_number=account_number,
                amount=SMALL_AMOUNT, transaction_date=start + timedelta(hours=index), **destination
            )

        response = post(
            payer_document=payer_document, source_account_number=account_number,
            amount=SMALL_AMOUNT, transaction_date=start + timedelta(hours=2), **destination
        )

        assert response["status"] == "two_factor_required"
        assert "WHERE_DESTINATION_FAN_IN" not in reasons_by_code(response)

    def test_destination_with_rejections_from_two_distinct_payers_rejects_the_next_payer(self):
        destination = unlisted_destination()
        night = days_ago_at(8, 21)
        for index in range(2):
            seeded = ObjectGenerator.create_pix_transaction(
                amount=150000, transaction_date=night + timedelta(hours=index), **destination
            )
            assert seeded["status"] == "rejected"

        response = post(amount=SMALL_AMOUNT, transaction_date=night + timedelta(hours=2), **destination)

        assert response["status"] == "rejected"
        rejections = reasons_by_code(response)["WHERE_DESTINATION_REJECTIONS"]
        assert rejections["level"] == "critical"
        assert rejections["observed"] == {"rejections_from_distinct_payers_24h": 2}

    def test_own_previous_rejection_does_not_count_as_destination_rejection(self):
        destination = unlisted_destination()
        payer_document, account_number = RandomGenerator.cpf(), RandomGenerator.account_number()
        night = days_ago_at(8, 21)
        ObjectGenerator.create_pix_transaction(amount=150000, transaction_date=night, **destination)
        ObjectGenerator.create_pix_transaction(
            payer_document=payer_document, source_account_number=account_number,
            amount=150000, transaction_date=night + timedelta(hours=1), **destination
        )

        response = post(
            payer_document=payer_document, source_account_number=account_number,
            amount=SMALL_AMOUNT, transaction_date=night + timedelta(hours=2), **destination
        )

        assert response["status"] == "two_factor_required"
        assert "WHERE_DESTINATION_REJECTIONS" not in reasons_by_code(response)

    def test_pix_dated_before_the_history_does_not_see_later_pix(self):
        payer_document, account_number = RandomGenerator.cpf(), RandomGenerator.account_number()
        start = days_ago_at(3, 15)
        seed_payer_attempts(payer_document, account_number, start + timedelta(minutes=1), 5, timedelta(minutes=1))

        response = post(
            payer_document=payer_document,
            source_account_number=account_number,
            amount=SMALL_AMOUNT,
            transaction_date=start,
        )

        assert response["status"] == "approved"
        assert "HOW_VELOCITY_EXCEEDED" not in reasons_by_code(response)

    def test_payer_with_five_approved_pix_over_thirty_days_reaches_maturity_phase_two(self):
        payer_document, account_number = RandomGenerator.cpf(), RandomGenerator.account_number()
        device_id = RandomGenerator.device_id()
        start = days_ago_at(50, 11)
        seed_payer_attempts(payer_document, account_number, start, 5, timedelta(days=8), device_id=device_id)

        response = post(
            payer_document=payer_document,
            source_account_number=account_number,
            device_id=device_id,
            amount=SMALL_AMOUNT,
            transaction_date=start + timedelta(days=40),
        )

        assert response["metadata"]["payer_maturity_phase"] == 2

    def test_payer_with_one_approved_pix_is_in_maturity_phase_one(self):
        payer_document, account_number = RandomGenerator.cpf(), RandomGenerator.account_number()
        start = days_ago_at(50, 11)
        seed_payer_attempts(payer_document, account_number, start, 1, timedelta(days=1))

        response = post(
            payer_document=payer_document,
            source_account_number=account_number,
            amount=SMALL_AMOUNT,
            transaction_date=start + timedelta(days=1),
        )

        assert response["metadata"]["payer_maturity_phase"] == 1
