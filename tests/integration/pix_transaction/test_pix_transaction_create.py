import uuid

from tests.utils import ObjectGenerator, PayloadGenerator, RandomGenerator, RequestGenerator

ANALYSIS_STATUSES = {"approved", "two_factor_required", "rejected"}
METADATA_KEYS = {"policy_version", "flow", "payer_maturity_phase", "decision_basis", "axes", "reasons", "floors", "trust"}
AXES = {"who", "how", "where"}
ERROR_FIELDS = {"title", "description", "translation", "code"}
UNLISTED_PARTICIPANT = "12345678"


def assert_error(status: int, response: dict, expected_status: int, expected_code: str, case: str = "") -> None:
    assert status == expected_status, f"{case}: {status} {response}"
    assert set(response.keys()) == ERROR_FIELDS, case
    assert response["code"] == expected_code, f"{case}: {response}"


def payload_with(change) -> dict:
    payload = PayloadGenerator.create_challenge_example_payload()
    change(payload)
    return payload


class TestPixTransactionCreate:
    def test_challenge_example_is_analysed_with_key_status_and_full_metadata(self):
        payload = PayloadGenerator.create_challenge_example_payload()

        status, response = RequestGenerator.POST_pix_transaction(payload)

        assert status == 201
        assert set(response.keys()) == {"key", "status", "metadata"}
        assert uuid.UUID(response["key"]).version == 4
        assert response["status"] in ANALYSIS_STATUSES
        metadata = response["metadata"]
        assert set(metadata.keys()) == METADATA_KEYS
        assert set(metadata["axes"].keys()) == AXES
        assert metadata["flow"] == "pf_pf"
        assert metadata["policy_version"]
        assert all(isinstance(metadata[key], list) for key in ("reasons", "floors", "trust"))

    def test_flow_follows_the_document_type_of_each_owner(self):
        flows = {
            "pf_pf": (RandomGenerator.cpf(), RandomGenerator.cpf()),
            "pf_pj": (RandomGenerator.cpf(), RandomGenerator.cnpj()),
            "pj_pf": (RandomGenerator.cnpj(), RandomGenerator.cpf()),
            "pj_pj": (RandomGenerator.cnpj(), RandomGenerator.cnpj()),
        }
        for expected_flow, (payer_document, beneficiary_document) in flows.items():
            response = ObjectGenerator.create_pix_transaction(payer_document=payer_document, beneficiary_document=beneficiary_document)

            assert response["metadata"]["flow"] == expected_flow

    def test_destination_participant_outside_the_str_list_is_not_an_error(self):
        payload = PayloadGenerator.create_pix_transaction_payload(participant=UNLISTED_PARTICIPANT)

        status, response = RequestGenerator.POST_pix_transaction(payload)

        assert status == 201
        assert response["status"] in ANALYSIS_STATUSES

    def test_same_owner_with_two_source_accounts_is_accepted_on_both(self):
        owner_document = RandomGenerator.cpf()

        first = PayloadGenerator.create_pix_transaction_payload(payer_document=owner_document)
        second = PayloadGenerator.create_pix_transaction_payload(payer_document=owner_document)

        assert first["source_account"]["account_number"] != second["source_account"]["account_number"]
        assert RequestGenerator.POST_pix_transaction(first)[0] == 201
        assert RequestGenerator.POST_pix_transaction(second)[0] == 201

    def test_refuses_request_without_a_valid_internal_token(self):
        for token in (None, "wrong-token"):
            status, response = RequestGenerator.POST_pix_transaction_with_token(PayloadGenerator.create_challenge_example_payload(), token)

            assert_error(status, response, 403, "RNV000002", f"token={token}")

    def test_refuses_body_that_is_not_a_json_object(self):
        cases = {"array": "[1, 2]", "string": '"pix"', "not_json": "not json", "no_body": ""}
        for case, raw_body in cases.items():
            status, response = RequestGenerator.POST_pix_transaction_raw_body(raw_body)

            assert_error(status, response, 400, "RNV000001", case)

    def test_refuses_missing_field(self):
        cases = {
            "empty_object": lambda payload: payload.clear(),
            "amount": lambda payload: payload.pop("amount"),
            "owner_document": lambda payload: payload["source_account"]["owner"].pop("document_number"),
            "geolocation_longitude": lambda payload: payload["source"]["geolocation"].pop("longitude"),
        }
        for case, change in cases.items():
            status, response = RequestGenerator.POST_pix_transaction(payload_with(change))

            assert_error(status, response, 400, "RNV000007", case)

    def test_refuses_unknown_field(self):
        cases = {
            "root": lambda payload: payload.update(unknown=1),
            "nested": lambda payload: payload["source"].update(unknown=1),
        }
        for case, change in cases.items():
            status, response = RequestGenerator.POST_pix_transaction(payload_with(change))

            assert_error(status, response, 400, "RNV000008", case)

    def test_refuses_wrong_type_or_format(self):
        cases = {
            "amount_as_string": lambda payload: payload.update(amount="150000"),
            "amount_as_boolean": lambda payload: payload.update(amount=True),
            "amount_with_cents_fraction": lambda payload: payload.update(amount=1500.5),
            "cpf_without_mask": lambda payload: payload["source_account"]["owner"].update(document_number="12345678909"),
            "date_without_time_and_offset": lambda payload: payload.update(transaction_date="2026-10-17"),
        }
        for case, change in cases.items():
            status, response = RequestGenerator.POST_pix_transaction(payload_with(change))

            assert_error(status, response, 400, "RNV000009", case)

    def test_refuses_value_out_of_range(self):
        cases = {
            "amount_zero": lambda payload: payload.update(amount=0),
            "amount_above_maximum": lambda payload: payload.update(amount=100000000001),
            "empty_id": lambda payload: payload.update(id=""),
            "latitude_above_ninety": lambda payload: payload["source"]["geolocation"].update(latitude=91),
        }
        for case, change in cases.items():
            status, response = RequestGenerator.POST_pix_transaction(payload_with(change))

            assert_error(status, response, 400, "RNV000010", case)
