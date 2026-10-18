import uuid

import pytest

from tests.utils.payload_generator import PayloadGenerator
from tests.utils.pix_requests import PixRequests
from tests.utils.random_generator import RandomGenerator

ANALYSIS_STATUSES = {"approved", "two_factor_required", "rejected"}


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
