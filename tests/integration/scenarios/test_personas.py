from tests.utils.personas import (
    generate_company_payroll_persona,
    generate_destination_fan_in_persona,
    generate_device_compromised_persona,
    generate_mature_self_pix_persona,
    generate_night_high_amount_persona,
    generate_probe_after_rejection_persona,
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

    def test_company_payroll_persona_has_zero_rejections(self):
        seed = f"pay-{RandomGenerator.uuid()[:8]}"
        payloads = generate_company_payroll_persona(seed=seed)
        assert len(payloads) == 10

        decisions = []
        for payload in payloads:
            status, response = RequestGenerator.POST_pix_transaction(payload)
            assert status == 201
            decisions.append(response["status"])

        assert all(d == "approved" for d in decisions)

    def test_mature_self_pix_persona_has_zero_rejections(self):
        seed = f"slf-{RandomGenerator.uuid()[:8]}"
        payloads = generate_mature_self_pix_persona(seed=seed)
        assert len(payloads) == 3

        decisions = []
        for payload in payloads:
            status, response = RequestGenerator.POST_pix_transaction(payload)
            assert status == 201
            decisions.append(response["status"])

        assert all(d == "approved" for d in decisions)

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

    def test_device_compromised_persona_rejects_third_document(self):
        seed = f"dvc-{RandomGenerator.uuid()[:8]}"
        payloads = generate_device_compromised_persona(seed=seed)
        assert len(payloads) == 3

        decisions = []
        last_response = None
        for payload in payloads:
            status, response = RequestGenerator.POST_pix_transaction(payload)
            assert status == 201
            decisions.append(response["status"])
            last_response = response

        assert decisions[0] == "approved"
        assert decisions[1] == "approved"
        assert decisions[2] == "rejected"
        assert last_response["metadata"]["decision_basis"] == "critical_axis"
        codes = [r["code"] for r in last_response["metadata"]["reasons"]]
        assert "WHO_DEVICE_COMPROMISED" in codes

    def test_probe_after_rejection_triggers_retry_rule(self):
        seed = f"prb-{RandomGenerator.uuid()[:8]}"
        payloads = generate_probe_after_rejection_persona(seed=seed)
        assert len(payloads) == 2

        status1, resp1 = RequestGenerator.POST_pix_transaction(payloads[0])
        status2, resp2 = RequestGenerator.POST_pix_transaction(payloads[1])

        assert status1 == 201
        assert resp1["status"] == "rejected"

        assert status2 == 201
        assert resp2["status"] == "two_factor_required"
        codes2 = [r["code"] for r in resp2["metadata"]["reasons"]]
        assert "HOW_RETRY_AFTER_REJECTION" in codes2

    def test_night_high_amount_persona_is_rejected(self):
        seed = f"ngt-{RandomGenerator.uuid()[:8]}"
        payloads = generate_night_high_amount_persona(seed=seed)
        assert len(payloads) == 1

        status, response = RequestGenerator.POST_pix_transaction(payloads[0])
        assert status == 201
        assert response["status"] == "rejected"
        assert response["metadata"]["decision_basis"] == "two_suspicious_axes"
