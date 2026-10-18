class TestHealthCheck:
    def test_health_check_returns_ok_without_token(self, api):
        status, response = api.get("/health_check")
        assert status == 200
        assert response == {"status": "ok"}

    def test_home_returns_ok_without_token(self, api):
        status, response = api.get("/")
        assert status == 200
        assert "service" in response
