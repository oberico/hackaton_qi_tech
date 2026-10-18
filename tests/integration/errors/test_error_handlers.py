from tests.utils import RequestGenerator

ERROR_FIELDS = {"title", "description", "translation", "code"}
UNKNOWN_ROUTES = [("GET", "/route-that-does-not-exist"), ("POST", "/route-that-does-not-exist"), ("GET", "/health_check/x/y")]
DISALLOWED_METHODS = [("PUT", "/health_check"), ("POST", "/"), ("DELETE", "/health_check")]


def assert_error_body(response, code: str) -> None:
    body = response.response_json
    assert set(body.keys()) == ERROR_FIELDS
    assert all(body[field] for field in ERROR_FIELDS)
    assert body["code"] == code
    assert response.response_headers.get("X-Request-ID")


class TestErrorHandlers:
    def test_unknown_route_answers_not_found_route_in_the_error_format(self):
        for method, endpoint in UNKNOWN_ROUTES:
            response = RequestGenerator.send_without_token(method, endpoint)

            assert response.response_status == 404, f"{method} {endpoint}"
            assert_error_body(response, "RNV000004")

    def test_disallowed_method_answers_method_not_allowed_and_keeps_the_allow_header(self):
        for method, endpoint in DISALLOWED_METHODS:
            response = RequestGenerator.send_without_token(method, endpoint)

            assert response.response_status == 405, f"{method} {endpoint}"
            assert_error_body(response, "RNV000005")
            assert "GET" in response.response_headers["Allow"]
