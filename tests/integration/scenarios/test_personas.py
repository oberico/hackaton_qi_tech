import pytest
from tests.utils.personas import generate_salaried_individual_persona
from tests.utils.request_generator import RequestGenerator


class TestPersonas:
    def test_salaried_individual_persona_has_zero_rejections(self):
        payloads = generate_salaried_individual_persona(seed="test-salaried-1")
        assert len(payloads) >= 5

        decisions = []
        for payload in payloads:
            status, response = RequestGenerator.POST_pix_transaction(payload)
            assert status == 201
            decisions.append(response["status"])

        rejections = [d for d in decisions if d == "rejected"]
        assert len(rejections) == 0, f"Expected 0 rejections for salaried persona, got: {decisions}"
