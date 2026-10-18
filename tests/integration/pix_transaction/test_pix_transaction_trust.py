from datetime import datetime, timedelta, timezone

from tests.utils import DatabaseInspector, ObjectGenerator, PayloadGenerator, RandomGenerator, RequestGenerator

BRASILIA = timezone(timedelta(hours=-3))
SMALL_AMOUNT = 5000
RECURRENT_BENEFICIARY = "TRUST_RECURRENT_BENEFICIARY"
MATURE_SELF_PIX = "TRUST_MATURE_SELF_PIX"


def days_ago_at(days: int, hour: int, minute: int = 0) -> datetime:
    day = datetime.now(BRASILIA) - timedelta(days=days)
    return day.replace(hour=hour, minute=minute, second=0, microsecond=0)


def new_payer() -> dict:
    return {
        "payer_document": RandomGenerator.cpf(),
        "source_account_number": RandomGenerator.account_number(),
        "device_id": RandomGenerator.device_id(),
    }


def known_beneficiary() -> dict:
    return {"beneficiary_document": RandomGenerator.cpf(), "destination_account_number": RandomGenerator.account_number()}


def seed_approved(payer: dict, destination: dict, transaction_date: datetime) -> None:
    response = ObjectGenerator.create_pix_transaction(**payer, **destination, amount=SMALL_AMOUNT, transaction_date=transaction_date)
    assert response["status"] == "approved", response


def seed_attempts_to_other_destinations(payer: dict, start: datetime, count: int) -> None:
    for index in range(count):
        ObjectGenerator.create_pix_transaction(**payer, amount=SMALL_AMOUNT, transaction_date=start + timedelta(minutes=index))


def post(payer: dict, destination: dict, transaction_date: datetime) -> tuple:
    payload = PayloadGenerator.create_pix_transaction_payload(**payer, **destination, amount=SMALL_AMOUNT, transaction_date=transaction_date)
    status, response = RequestGenerator.POST_pix_transaction(payload)
    assert status == 201, response
    return payload, response


def reason_codes(response: dict) -> set:
    return {reason["code"] for reason in response["metadata"]["reasons"]}


class TestPixTransactionTrust:
    def test_recurrent_beneficiary_turns_a_single_suspicious_velocity_into_approved(self):
        payer, beneficiary = new_payer(), known_beneficiary()
        seed_approved(payer, beneficiary, days_ago_at(3, 10))
        seed_approved(payer, beneficiary, days_ago_at(2, 10))
        burst_start = days_ago_at(1, 14)
        seed_attempts_to_other_destinations(payer, burst_start, 2)

        _, response = post(payer, beneficiary, burst_start + timedelta(minutes=2))

        assert response["status"] == "approved"
        metadata = response["metadata"]
        assert metadata["decision_basis"] == "trust_downgrade"
        assert metadata["trust"] == [RECURRENT_BENEFICIARY]
        assert metadata["axes"] == {"who": "ok", "how": "ok", "where": "ok"}
        assert "HOW_VELOCITY_EXCEEDED" in reason_codes(response)

    def test_a_single_approved_pix_to_the_beneficiary_is_not_recurrent(self):
        payer, beneficiary = new_payer(), known_beneficiary()
        seed_approved(payer, beneficiary, days_ago_at(3, 10))
        burst_start = days_ago_at(1, 14)
        seed_attempts_to_other_destinations(payer, burst_start, 2)

        payload, response = post(payer, beneficiary, burst_start + timedelta(minutes=2))

        assert response["status"] == "two_factor_required"
        assert response["metadata"]["decision_basis"] == "single_suspicious_axis"
        assert response["metadata"]["trust"] == []
        rules = {row["rule_code"]: row for row in DatabaseInspector.rule_rows(payload["id"])}
        assert rules[RECURRENT_BENEFICIARY]["outcome"] == "not_fired"
        assert rules[RECURRENT_BENEFICIARY]["axis"] == "trust"

    def test_mature_self_pix_from_a_trusted_device_turns_a_single_suspicious_velocity_into_approved(self):
        payer = new_payer()
        seed_approved(payer, known_beneficiary(), days_ago_at(3, 10))
        own_account = {"beneficiary_document": payer["payer_document"], "destination_account_number": RandomGenerator.account_number()}
        burst_start = days_ago_at(1, 14)
        seed_attempts_to_other_destinations(payer, burst_start, 2)

        _, response = post(payer, own_account, burst_start + timedelta(minutes=2))

        assert response["status"] == "approved"
        assert response["metadata"]["decision_basis"] == "trust_downgrade"
        assert response["metadata"]["trust"] == [MATURE_SELF_PIX]

    def test_self_pix_from_a_device_without_history_is_not_trusted(self):
        payer = new_payer()
        own_account = {"beneficiary_document": payer["payer_document"], "destination_account_number": RandomGenerator.account_number()}
        burst_start = days_ago_at(1, 14)
        seed_attempts_to_other_destinations(payer, burst_start, 2)

        _, response = post(payer, own_account, burst_start + timedelta(minutes=2))

        assert response["status"] == "two_factor_required"
        assert response["metadata"]["trust"] == []

    def test_recurrent_beneficiary_never_downgrades_a_critical_velocity(self):
        payer, beneficiary = new_payer(), known_beneficiary()
        seed_approved(payer, beneficiary, days_ago_at(3, 10))
        seed_approved(payer, beneficiary, days_ago_at(2, 10))
        burst_start = days_ago_at(1, 14)
        seed_attempts_to_other_destinations(payer, burst_start, 5)

        payload, response = post(payer, beneficiary, burst_start + timedelta(minutes=5))

        assert response["status"] == "rejected"
        assert response["metadata"]["decision_basis"] == "critical_axis"
        assert response["metadata"]["axes"]["how"] == "critical"
        assert response["metadata"]["trust"] == []
        rules = {row["rule_code"]: row for row in DatabaseInspector.rule_rows(payload["id"])}
        assert rules[RECURRENT_BENEFICIARY]["outcome"] == "fired"
