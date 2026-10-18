from tests.utils import PayloadGenerator, RequestGenerator

ERROR_FIELDS = {"title", "description", "translation", "code"}
INVALID_CPF = "111.222.333-44"


class TestPostSemanticErrors:
    def test_invalid_source_cpf_returns_422_rnv001002(self):
        payload = PayloadGenerator.create_challenge_example_payload()
        payload["source_account"]["owner"]["document_number"] = INVALID_CPF

        status, response = RequestGenerator.POST_pix_transaction(payload)

        assert status == 422
        assert set(response.keys()) == ERROR_FIELDS
        assert response["code"] == "RNV001002"

        get_status, get_response = RequestGenerator.GET_pix_transaction(payload["id"])
        assert get_status == 404
        assert get_response["code"] == "RNV001039"

    def test_invalid_destination_cpf_returns_422_rnv001002(self):
        payload = PayloadGenerator.create_challenge_example_payload()
        payload["destination_account"]["owner"]["document_number"] = INVALID_CPF

        status, response = RequestGenerator.POST_pix_transaction(payload)

        assert status == 422
        assert set(response.keys()) == ERROR_FIELDS
        assert response["code"] == "RNV001002"

        get_status, get_response = RequestGenerator.GET_pix_transaction(payload["id"])
        assert get_status == 404
        assert get_response["code"] == "RNV001039"
