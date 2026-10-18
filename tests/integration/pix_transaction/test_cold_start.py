from datetime import datetime, timedelta, timezone

import pytest

from tests.utils import PayloadGenerator, RandomGenerator, RequestGenerator
from tests.utils.payload_generator import BRASILIA, iso_in_brasilia

NIGHT_AMOUNT = 150000
ABOVE_DEVICE_LIMIT_AMOUNT = 30000
NEW_DESTINATION_AGE = timedelta(days=7)
DAYTIME_HOUR = 14
NIGHT_HOUR, NIGHT_MINUTE = 22, 15
FAN_IN_PAYERS = 3
COMPROMISED_DEVICE_DOCUMENTS = 3
REJECTING_PAYERS = 2


def yesterday_at(hour: int, minute: int = 0) -> datetime:
    day = datetime.now(BRASILIA) - timedelta(days=1)
    return day.replace(hour=hour, minute=minute, second=0, microsecond=0)


def opening_date_before(moment: datetime, age: timedelta = NEW_DESTINATION_AGE) -> str:
    return iso_in_brasilia(moment - age)


def last_night_before_now() -> datetime:
    now = datetime.now(BRASILIA)
    night = now.replace(hour=NIGHT_HOUR - 1, minute=NIGHT_MINUTE, second=0, microsecond=0)
    return night if night < now - timedelta(hours=1) else night - timedelta(days=1)


def one_minute_ago() -> datetime:
    return datetime.now(timezone.utc) - timedelta(minutes=1)


def new_destination(moment: datetime) -> dict:
    return {
        "participant": PayloadGenerator.create_pix_transaction_payload()["destination_account"]["participant"],
        "destination_account_number": RandomGenerator.account_number(),
        "beneficiary_document": RandomGenerator.cpf(),
        "destination_opening_date": opening_date_before(moment),
    }


def post(**fields) -> dict:
    status, response = RequestGenerator.POST_pix_transaction(PayloadGenerator.create_pix_transaction_payload(**fields))
    assert status == 201, response
    return response


def reason_codes(response: dict) -> set:
    return {reason["code"] for reason in response["metadata"]["reasons"]}


class TestColdStart:
    def test_first_pix_without_any_evidence_is_approved(self):
        response = post(amount=5000, transaction_date=yesterday_at(DAYTIME_HOUR))

        assert response["status"] == "approved"
        assert response["metadata"]["decision_basis"] == "clean"
        assert response["metadata"]["payer_maturity_phase"] == 0
        assert response["metadata"]["reasons"] == []
        assert response["metadata"]["floors"] == []

    def test_first_pix_with_one_payload_evidence_asks_for_two_factor_and_is_never_rejected(self):
        moment = yesterday_at(DAYTIME_HOUR)

        response = post(amount=5000, transaction_date=moment, destination_opening_date=opening_date_before(moment))

        assert response["status"] == "two_factor_required"
        assert response["metadata"]["decision_basis"] == "single_suspicious_axis"
        assert response["metadata"]["axes"] == {"who": "ok", "how": "ok", "where": "suspicious"}
        assert reason_codes(response) == {"WHERE_DESTINATION_NEW_ACCOUNT"}

    def test_first_pix_from_a_new_device_above_the_regulatory_limit_gets_the_floor_and_is_never_rejected(self):
        response = post(amount=ABOVE_DEVICE_LIMIT_AMOUNT, transaction_date=yesterday_at(DAYTIME_HOUR))

        assert response["status"] == "two_factor_required"
        assert response["metadata"]["decision_basis"] == "regulatory_floor"
        assert response["metadata"]["floors"] == ["FLOOR_UNREGISTERED_DEVICE"]
        assert response["metadata"]["axes"] == {"who": "ok", "how": "ok", "where": "ok"}

    def test_first_pix_with_payload_evidence_in_two_axes_is_rejected(self):
        moment = yesterday_at(NIGHT_HOUR, NIGHT_MINUTE)

        response = post(amount=NIGHT_AMOUNT, transaction_date=moment, destination_opening_date=opening_date_before(moment))

        assert response["status"] == "rejected"
        assert response["metadata"]["decision_basis"] == "two_suspicious_axes"
        assert response["metadata"]["axes"] == {"who": "ok", "how": "suspicious", "where": "suspicious"}
        assert response["metadata"]["payer_maturity_phase"] == 0
        assert {"HOW_NIGHT_LIMIT_EXCEEDED", "WHERE_DESTINATION_NEW_ACCOUNT"} <= reason_codes(response)

    @pytest.mark.xfail(strict=True, reason="until T14 and T15: fan-in needs the destination window query")
    def test_first_pix_to_a_destination_with_many_payers_is_rejected_by_the_destination(self):
        earlier = datetime.now(timezone.utc) - timedelta(hours=2)
        destination = new_destination(earlier)
        for _ in range(FAN_IN_PAYERS):
            post(transaction_date=earlier, **destination)

        response = post(transaction_date=one_minute_ago(), **destination)

        assert response["status"] == "rejected"
        assert response["metadata"]["decision_basis"] == "critical_axis"
        assert response["metadata"]["payer_maturity_phase"] == 0
        assert response["metadata"]["axes"]["where"] == "critical"
        assert "WHERE_DESTINATION_FAN_IN" in reason_codes(response)

    @pytest.mark.xfail(strict=True, reason="until T16 and T15: compromised device needs the device window query")
    def test_first_pix_from_a_device_used_by_many_holders_is_rejected_by_the_device(self):
        earlier = datetime.now(timezone.utc) - timedelta(hours=2)
        device_id = RandomGenerator.device_id()
        for _ in range(COMPROMISED_DEVICE_DOCUMENTS):
            post(transaction_date=earlier, device_id=device_id)

        response = post(transaction_date=one_minute_ago(), device_id=device_id)

        assert response["status"] == "rejected"
        assert response["metadata"]["decision_basis"] == "critical_axis"
        assert response["metadata"]["payer_maturity_phase"] == 0
        assert response["metadata"]["axes"]["who"] == "critical"
        assert "WHO_DEVICE_COMPROMISED" in reason_codes(response)

    @pytest.mark.xfail(strict=True, reason="until T14 and T15: rejections need the destination window query")
    def test_first_pix_to_a_destination_with_rejections_from_distinct_payers_is_rejected_by_the_destination(self):
        night = last_night_before_now()
        destination = new_destination(night)
        for _ in range(REJECTING_PAYERS):
            prior = post(amount=NIGHT_AMOUNT, transaction_date=night, **destination)
            assert prior["status"] == "rejected"

        response = post(amount=5000, transaction_date=one_minute_ago(), **destination)

        assert response["status"] == "rejected"
        assert response["metadata"]["decision_basis"] == "critical_axis"
        assert response["metadata"]["payer_maturity_phase"] == 0
        assert "WHERE_DESTINATION_REJECTIONS" in reason_codes(response)
