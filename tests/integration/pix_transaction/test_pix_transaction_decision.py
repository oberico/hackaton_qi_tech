from datetime import datetime, timezone

import pytest

from tests.utils import DatabaseInspector, PayloadGenerator, RandomGenerator, RequestGenerator

DAYTIME_MOMENT = datetime(2026, 10, 16, 17, 0, tzinfo=timezone.utc)
MAX_EXPECTED_LATENCY_MS = 1000
CHALLENGE_DESTINATION_AGE_DAYS = (7 * 24 + 13.25) / 24


class TestPixTransactionDecision:
    def test_challenge_example_is_rejected_by_two_suspicious_axes(self):
        payload = PayloadGenerator.create_challenge_example_payload()

        status, response = RequestGenerator.POST_pix_transaction(payload)

        assert status == 201, response
        assert response["status"] == "rejected"
        metadata = response["metadata"]
        assert metadata["decision_basis"] == "two_suspicious_axes"
        assert metadata["flow"] == "pf_pf"
        assert metadata["axes"] == {"who": "ok", "how": "suspicious", "where": "suspicious"}
        reason_codes = {reason["code"] for reason in metadata["reasons"]}
        assert {"HOW_NIGHT_LIMIT_EXCEEDED", "WHERE_DESTINATION_NEW_ACCOUNT"} <= reason_codes

    def test_challenge_example_reasons_carry_observed_and_threshold_in_the_response(self):
        payload = PayloadGenerator.create_challenge_example_payload()

        status, response = RequestGenerator.POST_pix_transaction(payload)

        assert status == 201, response
        reasons = {reason["code"]: reason for reason in response["metadata"]["reasons"]}
        assert reasons["HOW_NIGHT_LIMIT_EXCEEDED"]["observed"] == {"night_amount": 150000}
        assert reasons["HOW_NIGHT_LIMIT_EXCEEDED"]["threshold"] == {"night_amount": 100000}
        observed_age = reasons["WHERE_DESTINATION_NEW_ACCOUNT"]["observed"]["destination_account_age_days"]
        assert observed_age == pytest.approx(CHALLENGE_DESTINATION_AGE_DAYS, abs=0.01)
        assert reasons["WHERE_DESTINATION_NEW_ACCOUNT"]["threshold"] == {"destination_account_age_days": 30}

    def test_every_evaluated_rule_is_stored_with_its_outcome(self):
        payload = PayloadGenerator.create_challenge_example_payload()

        status, response = RequestGenerator.POST_pix_transaction(payload)

        assert status == 201, response
        rows = {row["rule_code"]: row for row in DatabaseInspector.rule_rows(payload["id"])}
        fired_codes = {code for code, row in rows.items() if row["outcome"] == "fired"}
        assert fired_codes == {reason["code"] for reason in response["metadata"]["reasons"]} | set(response["metadata"]["floors"])
        assert any(row["outcome"] == "not_fired" for row in rows.values())
        assert rows["HOW_NIGHT_LIMIT_EXCEEDED"]["axis"] == "how"
        assert rows["HOW_NIGHT_LIMIT_EXCEEDED"]["level"] == "suspicious"
        assert rows["HOW_NIGHT_LIMIT_EXCEEDED"]["observed"] == {"night_amount": 150000}
        assert rows["HOW_NIGHT_LIMIT_EXCEEDED"]["threshold"] == {"night_amount": 100000}
        assert rows["HOW_NIGHT_LIMIT_EXCEEDED"]["reason"]
        assert rows["WHERE_UNKNOWN_PARTICIPANT"]["outcome"] == "not_fired"
        assert rows["WHERE_UNKNOWN_PARTICIPANT"]["level"] is None
        assert rows["FLOOR_UNREGISTERED_DEVICE"]["axis"] == "floor"

    def test_the_three_axis_levels_are_stored(self):
        payload = PayloadGenerator.create_challenge_example_payload()

        status, response = RequestGenerator.POST_pix_transaction(payload)

        assert status == 201, response
        stored = {row["axis"]: row["level"] for row in DatabaseInspector.axis_rows(payload["id"])}
        assert stored == response["metadata"]["axes"]

    def test_latency_is_recorded_in_every_analysis(self):
        payload = PayloadGenerator.create_pix_transaction_payload(transaction_date=DAYTIME_MOMENT)

        status, response = RequestGenerator.POST_pix_transaction(payload)

        assert status == 201, response
        assert 0 < DatabaseInspector.latency_ms(payload["id"]) < MAX_EXPECTED_LATENCY_MS

    def test_new_payer_small_daytime_pix_is_approved_clean(self):
        payload = PayloadGenerator.create_pix_transaction_payload(
            amount=5000, transaction_date=DAYTIME_MOMENT, payer_document=RandomGenerator.cpf()
        )

        status, response = RequestGenerator.POST_pix_transaction(payload)

        assert status == 201, response
        assert response["status"] == "approved"
        metadata = response["metadata"]
        assert metadata["decision_basis"] == "clean"
        assert metadata["axes"] == {"who": "ok", "how": "ok", "where": "ok"}
        assert metadata["reasons"] == []
        assert metadata["floors"] == []
        assert metadata["payer_maturity_phase"] == 0
