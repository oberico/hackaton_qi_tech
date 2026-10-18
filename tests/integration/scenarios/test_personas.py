from tests.utils.personas import (
    generate_destination_fan_in_persona,
    generate_salaried_individual_persona,
)
from tests.utils.random_generator import RandomGenerator
from tests.utils.request_generator import RequestGenerator


class TestPersonas:
    def test_salaried_individual_persona_has_zero_rejections(self):
        seed = f"sal-{RandomGenerator.uuid()[:8]}"
        payloads = generate_salaried_individual_persona(seed=seed)
        assert len(payloads) >= 5

        decisions = []
        for payload in payloads:
            status, response = RequestGenerator.POST_pix_transaction(payload)
            assert status == 201
            decisions.append(response["status"])

        rejections = [d for d in decisions if d == "rejected"]
        assert len(rejections) == 0, f"Expected 0 rejections for salaried persona, got: {decisions}"

    def test_destination_fan_in_persona_rejects_third_payer(self):
        seed = f"fan-{RandomGenerator.uuid()[:8]}"
        payloads = generate_destination_fan_in_persona(seed=seed)
        assert len(payloads) >= 3

        decisions = []
        last_response = None
        for payload in payloads:
            status, response = RequestGenerator.POST_pix_transaction(payload)
            assert status == 201
            decisions.append(response["status"])
            last_response = response

        assert decisions[0] == "two_factor_required"
        assert decisions[1] == "two_factor_required"
        assert decisions[2] == "rejected"
        assert last_response["metadata"]["decision_basis"] == "critical_axis"
        codes = [r["code"] for r in last_response["metadata"]["reasons"]]
        assert "WHERE_DESTINATION_FAN_IN" in codes
