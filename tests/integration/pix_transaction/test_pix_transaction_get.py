from tests.utils import PayloadGenerator, RequestGenerator


class TestPixTransactionGet:
    def test_get_returns_the_same_analysis_the_post_returned(self):
        payload = PayloadGenerator.create_challenge_example_payload()
        post_status, post_response = RequestGenerator.POST_pix_transaction(payload)

        status, response = RequestGenerator.GET_pix_transaction(payload["id"])

        assert post_status == 201
        assert status == 200
        assert response == post_response
