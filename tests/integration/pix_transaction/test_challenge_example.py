from tests.utils import PayloadGenerator, RequestGenerator

EXPECTED_AXES = {"who": "ok", "how": "suspicious", "where": "suspicious"}
EXPECTED_REASON_CODES = {"HOW_NIGHT_LIMIT_EXCEEDED", "WHERE_DESTINATION_NEW_ACCOUNT"}


class TestChallengeExample:
    def test_challenge_example_is_rejected_by_two_suspicious_axes(self):
        payload = PayloadGenerator.create_challenge_example_payload()

        status, response = RequestGenerator.POST_pix_transaction(payload)

        assert status == 201
        assert response["status"] == "rejected"
        metadata = response["metadata"]
        assert metadata["decision_basis"] == "two_suspicious_axes"
        assert metadata["axes"] == EXPECTED_AXES
        assert metadata["flow"] == "pf_pf"
        assert EXPECTED_REASON_CODES <= {reason["code"] for reason in metadata["reasons"]}

    def test_challenge_example_analysis_is_returned_unchanged_by_the_get(self):
        payload = PayloadGenerator.create_challenge_example_payload()
        post_status, post_response = RequestGenerator.POST_pix_transaction(payload)

        get_status, get_response = RequestGenerator.GET_pix_transaction(payload["id"])

        assert post_status == 201
        assert get_status == 200
        assert get_response == post_response
        assert get_response["status"] == "rejected"
