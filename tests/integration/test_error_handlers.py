import pytest


ERROR_FIELDS = {"title", "description", "translation", "code"}

UNKNOWN_ROUTES = {
    "get_unknown_route": ("GET", "/route-that-does-not-exist"),
    "post_unknown_route": ("POST", "/route-that-does-not-exist"),
    "get_nested_unknown_route": ("GET", "/health_check/x/y"),
}

DISALLOWED_METHODS = {
    "put_health_check": ("PUT", "/health_check"),
    "post_home": ("POST", "/"),
    "delete_health_check": ("DELETE", "/health_check"),
}

ERROR_CASES = {
    "unknown_route": ("GET", "/route-that-does-not-exist"),
    "disallowed_method": ("PUT", "/health_check"),
}


class TestErrorHandlers:
    @pytest.mark.parametrize("method, path", UNKNOWN_ROUTES.values(), ids=UNKNOWN_ROUTES.keys())
    def test_unknown_route_returns_not_found_route(self, api, method, path):
        status, response = api.request_with_headers(method, path)[:2]
        assert status == 404
        assert response["code"] == "RNV000004"

    @pytest.mark.parametrize("method, path", DISALLOWED_METHODS.values(), ids=DISALLOWED_METHODS.keys())
    def test_disallowed_method_returns_method_not_allowed(self, api, method, path):
        status, response = api.request_with_headers(method, path)[:2]
        assert status == 405
        assert response["code"] == "RNV000005"

    @pytest.mark.parametrize("method, path", ERROR_CASES.values(), ids=ERROR_CASES.keys())
    def test_error_has_exactly_the_four_filled_fields(self, api, method, path):
        _, response = api.request_with_headers(method, path)[:2]
        assert set(response.keys()) == ERROR_FIELDS
        assert all(response[field] for field in ERROR_FIELDS)

    @pytest.mark.parametrize("method, path", ERROR_CASES.values(), ids=ERROR_CASES.keys())
    def test_error_response_carries_request_id(self, api, method, path):
        headers = api.request_with_headers(method, path)[2]
        assert headers.get("X-Request-ID")

    def test_method_not_allowed_preserves_allow_header(self, api):
        headers = api.request_with_headers("PUT", "/health_check")[2]
        assert "GET" in headers["Allow"]
