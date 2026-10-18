from datetime import datetime, timedelta, timezone

from tests.utils import PayloadGenerator, RandomGenerator, RequestGenerator

ERROR_FIELDS = {"title", "description", "translation", "code"}
INVALID_CPF = "111.222.333-44"
INVALID_CNPJ = "11.222.333/0001-44"


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

    def test_invalid_source_cnpj_returns_422_rnv001020(self):
        payload = PayloadGenerator.create_challenge_example_payload()
        payload["source_account"]["owner"]["document_number"] = INVALID_CNPJ

        status, response = RequestGenerator.POST_pix_transaction(payload)

        assert status == 422
        assert set(response.keys()) == ERROR_FIELDS
        assert response["code"] == "RNV001020"

        get_status, get_response = RequestGenerator.GET_pix_transaction(payload["id"])
        assert get_status == 404
        assert get_response["code"] == "RNV001039"

    def test_invalid_destination_cnpj_returns_422_rnv001020(self):
        payload = PayloadGenerator.create_challenge_example_payload()
        payload["destination_account"]["owner"]["document_number"] = INVALID_CNPJ

        status, response = RequestGenerator.POST_pix_transaction(payload)

        assert status == 422
        assert set(response.keys()) == ERROR_FIELDS
        assert response["code"] == "RNV001020"

        get_status, get_response = RequestGenerator.GET_pix_transaction(payload["id"])
        assert get_status == 404
        assert get_response["code"] == "RNV001039"

    def test_source_account_opening_date_after_transaction_date_returns_422_rnv001040(self):
        payload = PayloadGenerator.create_challenge_example_payload()
        payload["source_account"]["opening_date"] = "2026-10-18T00:00:00-03:00"
        payload["transaction_date"] = "2026-10-17T03:15:00-03:00"

        status, response = RequestGenerator.POST_pix_transaction(payload)

        assert status == 422
        assert set(response.keys()) == ERROR_FIELDS
        assert response["code"] == "RNV001040"

        get_status, get_response = RequestGenerator.GET_pix_transaction(payload["id"])
        assert get_status == 404
        assert get_response["code"] == "RNV001039"

    def test_destination_account_opening_date_after_transaction_date_returns_422_rnv001040(self):
        payload = PayloadGenerator.create_challenge_example_payload()
        payload["destination_account"]["opening_date"] = "2026-10-18T00:00:00-03:00"
        payload["transaction_date"] = "2026-10-17T03:15:00-03:00"

        status, response = RequestGenerator.POST_pix_transaction(payload)

        assert status == 422
        assert set(response.keys()) == ERROR_FIELDS
        assert response["code"] == "RNV001040"

        get_status, get_response = RequestGenerator.GET_pix_transaction(payload["id"])
        assert get_status == 404
        assert get_response["code"] == "RNV001039"

    def test_transaction_date_10_minutes_in_future_returns_422_rnv001041(self):
        payload = PayloadGenerator.create_challenge_example_payload()
        future_dt = datetime.now(timezone.utc) + timedelta(minutes=10)
        payload["transaction_date"] = future_dt.isoformat()

        status, response = RequestGenerator.POST_pix_transaction(payload)

        assert status == 422
        assert set(response.keys()) == ERROR_FIELDS
        assert response["code"] == "RNV001041"

        get_status, get_response = RequestGenerator.GET_pix_transaction(payload["id"])
        assert get_status == 404
        assert get_response["code"] == "RNV001039"

    def test_transaction_date_4_minutes_in_future_returns_201(self):
        payload = PayloadGenerator.create_challenge_example_payload()
        future_dt = datetime.now(timezone.utc) + timedelta(minutes=4)
        payload["transaction_date"] = future_dt.isoformat()

        status, response = RequestGenerator.POST_pix_transaction(payload)

        assert status == 201
        assert response["status"] in ("approved", "two_factor_required", "rejected")

    def test_source_and_destination_accounts_are_the_same_returns_422_rnv001042(self):
        payload = PayloadGenerator.create_challenge_example_payload()
        payload["destination_account"]["participant"] = "99999999"
        payload["destination_account"]["branch"] = payload["source_account"]["branch"]
        payload["destination_account"]["account_number"] = payload["source_account"]["account_number"]

        status, response = RequestGenerator.POST_pix_transaction(payload)

        assert status == 422
        assert set(response.keys()) == ERROR_FIELDS
        assert response["code"] == "RNV001042"

        get_status, get_response = RequestGenerator.GET_pix_transaction(payload["id"])
        assert get_status == 404
        assert get_response["code"] == "RNV001039"

    def test_invalid_ip_returns_422_rnv001043(self):
        payload = PayloadGenerator.create_challenge_example_payload()
        payload["source"]["ip"] = "999.999.999.999"

        status, response = RequestGenerator.POST_pix_transaction(payload)

        assert status == 422
        assert set(response.keys()) == ERROR_FIELDS
        assert response["code"] == "RNV001043"

        get_status, get_response = RequestGenerator.GET_pix_transaction(payload["id"])
        assert get_status == 404
        assert get_response["code"] == "RNV001039"

    def test_known_account_with_different_holder_returns_409_rnv001044(self):
        dest_account_number = RandomGenerator.account_number()
        first_payload = PayloadGenerator.create_challenge_example_payload()
        first_payload["id"] = RandomGenerator.transaction_id()
        first_payload["destination_account"]["account_number"] = dest_account_number
        first_payload["destination_account"]["owner"]["document_number"] = RandomGenerator.cpf()

        status, _ = RequestGenerator.POST_pix_transaction(first_payload)
        assert status == 201

        conflicting_payload = PayloadGenerator.create_challenge_example_payload()
        conflicting_payload["id"] = RandomGenerator.transaction_id()
        conflicting_payload["destination_account"]["participant"] = first_payload["destination_account"]["participant"]
        conflicting_payload["destination_account"]["branch"] = first_payload["destination_account"]["branch"]
        conflicting_payload["destination_account"]["account_number"] = dest_account_number
        conflicting_payload["destination_account"]["owner"]["document_number"] = RandomGenerator.cpf()

        status, response = RequestGenerator.POST_pix_transaction(conflicting_payload)

        assert status == 409
        assert set(response.keys()) == ERROR_FIELDS
        assert response["code"] == "RNV001044"

        get_status, get_response = RequestGenerator.GET_pix_transaction(conflicting_payload["id"])
        assert get_status == 404
        assert get_response["code"] == "RNV001039"

    def test_known_account_with_different_opening_date_returns_409_rnv001044(self):
        dest_account_number = RandomGenerator.account_number()
        first_payload = PayloadGenerator.create_challenge_example_payload()
        first_payload["id"] = RandomGenerator.transaction_id()
        first_payload["destination_account"]["account_number"] = dest_account_number
        first_payload["destination_account"]["opening_date"] = "2023-01-15T08:00:00-03:00"

        status, _ = RequestGenerator.POST_pix_transaction(first_payload)
        assert status == 201

        conflicting_payload = PayloadGenerator.create_challenge_example_payload()
        conflicting_payload["id"] = RandomGenerator.transaction_id()
        conflicting_payload["destination_account"]["participant"] = first_payload["destination_account"]["participant"]
        conflicting_payload["destination_account"]["branch"] = first_payload["destination_account"]["branch"]
        conflicting_payload["destination_account"]["account_number"] = dest_account_number
        conflicting_payload["destination_account"]["owner"]["document_number"] = (
            first_payload["destination_account"]["owner"]["document_number"]
        )
        conflicting_payload["destination_account"]["opening_date"] = "2024-06-01T10:00:00-03:00"

        status, response = RequestGenerator.POST_pix_transaction(conflicting_payload)

        assert status == 409
        assert set(response.keys()) == ERROR_FIELDS
        assert response["code"] == "RNV001044"

        get_status, get_response = RequestGenerator.GET_pix_transaction(conflicting_payload["id"])
        assert get_status == 404
        assert get_response["code"] == "RNV001039"

    def test_same_cpf_with_different_account_number_returns_201(self):
        shared_cpf = RandomGenerator.cpf()
        first_payload = PayloadGenerator.create_challenge_example_payload()
        first_payload["id"] = RandomGenerator.transaction_id()
        first_payload["source_account"]["owner"]["document_number"] = shared_cpf
        first_payload["source_account"]["account_number"] = RandomGenerator.account_number()

        status, _ = RequestGenerator.POST_pix_transaction(first_payload)
        assert status == 201

        second_payload = PayloadGenerator.create_challenge_example_payload()
        second_payload["id"] = RandomGenerator.transaction_id()
        second_payload["source_account"]["owner"]["document_number"] = shared_cpf
        second_payload["source_account"]["account_number"] = RandomGenerator.account_number()

        status, response = RequestGenerator.POST_pix_transaction(second_payload)
        assert status == 201
        assert response["status"] in ("approved", "two_factor_required", "rejected")
