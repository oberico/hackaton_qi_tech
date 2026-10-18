from concurrent.futures import ThreadPoolExecutor

from tests.utils import DatabaseInspector, PayloadGenerator, RequestGenerator


ERROR_FIELDS = {"title", "description", "translation", "code"}


def assert_error(status: int, response: dict, expected_status: int, expected_code: str) -> None:
    assert status == expected_status, f"{status} {response}"
    assert set(response.keys()) == ERROR_FIELDS
    assert response["code"] == expected_code


class TestPixTransactionIdempotency:
    def test_identical_retry_returns_200_with_the_same_body_as_the_original_201(self):
        payload = PayloadGenerator.create_pix_transaction_payload()
        original_status, original_response = RequestGenerator.POST_pix_transaction(payload)

        retry_status, retry_response = RequestGenerator.POST_pix_transaction(payload)

        assert original_status == 201
        assert retry_status == 200
        assert retry_response == original_response

    def test_same_id_with_a_different_payload_is_422_and_nothing_new_is_stored(self):
        payload = PayloadGenerator.create_pix_transaction_payload(amount=5000)
        original_status, original_response = RequestGenerator.POST_pix_transaction(payload)
        changed_payload = {**payload, "amount": 5001}

        status, response = RequestGenerator.POST_pix_transaction(changed_payload)

        assert original_status == 201
        assert_error(status, response, 422, "RNV001024")
        assert DatabaseInspector.transaction_count(payload["id"]) == 1
        assert DatabaseInspector.analysis_keys(payload["id"]) == [original_response["key"]]

    def test_ten_sequential_posts_with_the_same_id_produce_a_single_analysis(self):
        payload = PayloadGenerator.create_pix_transaction_payload()

        results = [RequestGenerator.POST_pix_transaction(payload) for _ in range(10)]

        assert [status for status, _ in results] == [201] + [200] * 9
        assert len({response["key"] for _, response in results}) == 1
        assert all(response == results[0][1] for _, response in results)
        assert DatabaseInspector.transaction_count(payload["id"]) == 1
        assert DatabaseInspector.analysis_keys(payload["id"]) == [results[0][1]["key"]]

    def test_retry_after_a_schema_error_is_analysed_and_not_cached(self):
        payload = PayloadGenerator.create_pix_transaction_payload()
        invalid_payload = {key: value for key, value in payload.items() if key != "amount"}

        invalid_status, invalid_response = RequestGenerator.POST_pix_transaction(invalid_payload)
        status, response = RequestGenerator.POST_pix_transaction(payload)

        assert_error(invalid_status, invalid_response, 400, "RNV000007")
        assert status == 201
        assert DatabaseInspector.transaction_count(payload["id"]) == 1

    def test_original_payload_still_gets_200_after_a_422_for_a_reused_id(self):
        payload = PayloadGenerator.create_pix_transaction_payload()
        _, original_response = RequestGenerator.POST_pix_transaction(payload)
        conflict_status, _ = RequestGenerator.POST_pix_transaction({**payload, "amount": payload["amount"] + 1})

        status, response = RequestGenerator.POST_pix_transaction(payload)

        assert conflict_status == 422
        assert status == 200
        assert response == original_response

    def test_ten_parallel_posts_with_the_same_id_give_one_201_nine_200_and_one_key(self):
        payload = PayloadGenerator.create_pix_transaction_payload()
        parallel_requests = 10

        with ThreadPoolExecutor(max_workers=parallel_requests) as executor:
            results = list(executor.map(lambda _: RequestGenerator.POST_pix_transaction(payload), range(parallel_requests)))

        statuses = sorted(status for status, _ in results)
        assert statuses == [200] * 9 + [201], statuses
        assert len({response["key"] for _, response in results}) == 1
        assert all(response == results[0][1] for _, response in results)
        assert DatabaseInspector.transaction_count(payload["id"]) == 1
        assert DatabaseInspector.analysis_keys(payload["id"]) == [results[0][1]["key"]]
