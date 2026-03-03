"""
Tests for GET /logs endpoint (Phase 6.2).

Verifies data retrieval with token authentication.
"""

from pathlib import Path
import pytest
from app.main import create_app


@pytest.fixture()
def client(tmp_path: Path):
    """Create test client with temporary data file."""
    data_file = tmp_path / "data.json"
    app = create_app(data_file)
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client, data_file


@pytest.fixture()
def auth_token(client):
    """Generate valid token for testing."""
    test_client, data_file = client

    # Generate code
    code_response = test_client.post("/generate-code")
    code = code_response.get_json()["code"]

    # Generate token
    token_response = test_client.post("/generate-token", json={"code": code})
    token = token_response.get_json()["token"]

    return test_client, data_file, code, token


def test_get_logs_requires_authentication(client):
    """GET /logs requires token authentication."""
    test_client, _ = client
    response = test_client.get("/logs")
    assert response.status_code == 401


def test_get_logs_returns_empty_for_no_data(auth_token):
    """Returns empty array when user has no logs."""
    test_client, _, _, token = auth_token

    response = test_client.get("/logs", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    data = response.get_json()
    assert data["logs"] == []



def test_get_logs_rate_limiting(auth_token):
    """Rate limiting applies to GET /logs."""
    test_client, _, _, token = auth_token

    # Make 100 requests (rate limit)
    for _ in range(100):
        response = test_client.get("/logs", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 200

    # 101st request should be rate limited
    response = test_client.get("/logs", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 429
