import os

import pytest
import requests

from tests.utils.request_generator import RequestGenerator

API_URL = os.getenv("API_URL", "http://localhost:8001")
INTERNAL_TOKEN = os.getenv("INTERNAL_TOKEN", "internal-token-dev")


@pytest.fixture(scope="session")
def api_url() -> str:
    return API_URL


@pytest.fixture(scope="session")
def api_is_up(api_url) -> None:
    try:
        requests.get(f"{api_url}/health_check", timeout=5)
    except requests.exceptions.RequestException:
        pytest.exit(f"could not reach the API at {api_url}; run `docker compose up -d` first", returncode=1)


@pytest.fixture(scope="session")
def api(api_url, api_is_up) -> RequestGenerator:
    return RequestGenerator(api_url)


@pytest.fixture(scope="session")
def internal_token() -> str:
    return INTERNAL_TOKEN


@pytest.fixture(scope="session")
def internal_headers(internal_token) -> dict:
    return {"INTERNAL-TOKEN": internal_token}
