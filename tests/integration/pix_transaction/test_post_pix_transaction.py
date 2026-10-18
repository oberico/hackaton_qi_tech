import uuid

import pytest

from tests.utils.payload_generator import PayloadGenerator
from tests.utils.pix_requests import PixRequests
from tests.utils.random_generator import RandomGenerator

ANALYSIS_STATUSES = {"approved", "two_factor_required", "rejected"}
METADATA_KEYS = {"policy_version", "flow", "payer_maturity_phase", "decision_basis", "axes", "reasons", "floors", "trust"}
AXES = {"who", "how", "where"}
UNLISTED_PARTICIPANT = "12345678"


@pytest.fixture
def pix(api, internal_headers) -> PixRequests:
    return PixRequests(api, internal_headers)


class TestPostPixTransaction:
    def test_valid_payload_returns_created_with_key_and_status(self, pix):
        payload = PayloadGenerator.challenge_example(id=RandomGenerator.uuid())

        status, response = pix.post_transaction(payload)

        assert status == 201
        assert uuid.UUID(response["key"]).version == 4
        assert response["status"] in ANALYSIS_STATUSES

    def test_response_metadata_has_all_format_keys(self, pix):
        payload = PayloadGenerator.challenge_example(id=RandomGenerator.uuid())

        _, response = pix.post_transaction(payload)

        metadata = response["metadata"]
        assert set(metadata.keys()) == METADATA_KEYS
        assert set(metadata["axes"].keys()) == AXES
        assert all(isinstance(metadata[key], list) for key in ("reasons", "floors", "trust"))

    def test_flow_is_pf_pf_when_both_owners_are_individuals(self, pix):
        payload = PayloadGenerator.challenge_example(id=RandomGenerator.uuid())
        payload["destination_account"]["owner"]["document_number"] = RandomGenerator.cpf()

        _, response = pix.post_transaction(payload)

        assert response["metadata"]["flow"] == "pf_pf"

    def test_flow_is_pf_pj_when_destination_owner_is_a_company(self, pix):
        payload = PayloadGenerator.challenge_example(id=RandomGenerator.uuid())
        payload["destination_account"]["owner"]["document_number"] = RandomGenerator.cnpj()

        _, response = pix.post_transaction(payload)

        assert response["metadata"]["flow"] == "pf_pj"

    def test_destination_participant_outside_the_str_list_is_not_an_error(self, pix):
        payload = PayloadGenerator.challenge_example(id=RandomGenerator.uuid())
        payload["destination_account"]["participant"] = UNLISTED_PARTICIPANT

        status, response = pix.post_transaction(payload)

        assert status == 201
        assert response["status"] in ANALYSIS_STATUSES
