from tests.utils import PayloadGenerator, RandomGenerator, RequestGenerator

ERROR_FIELDS = {"title", "description", "translation", "code"}


class TestPixTransactionGet:
    def test_get_returns_the_same_analysis_the_post_returned(self):
        payload = PayloadGenerator.create_challenge_example_payload()
        post_status, post_response = RequestGenerator.POST_pix_transaction(payload)

        status, response = RequestGenerator.GET_pix_transaction(payload["id"])

        assert post_status == 201
        assert status == 200
        assert response == post_response

    def test_get_of_unknown_id_returns_not_found(self):
        status, response = RequestGenerator.GET_pix_transaction(RandomGenerator.transaction_id())

        assert status == 404
        assert set(response.keys()) == ERROR_FIELDS
        assert response["code"] == "RNV001039"

    def test_get_without_token_is_forbidden(self):
        response = RequestGenerator.send_without_token("GET", f"/pix/transaction/{RandomGenerator.transaction_id()}")

        assert response.response_status == 403
        assert set(response.response_json.keys()) == ERROR_FIELDS
        assert response.response_json["code"] == "RNV000002"
