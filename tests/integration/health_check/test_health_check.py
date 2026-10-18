from tests.utils import RequestGenerator


class TestHealthCheck:
    def test_health_check_answers_ok_without_token(self):
        status, response = RequestGenerator.GET_health_check()

        assert status == 200
        assert response == {"status": "ok"}

    def test_home_answers_the_service_name_without_token(self):
        status, response = RequestGenerator.GET_home()

        assert status == 200
        assert response["service"]
