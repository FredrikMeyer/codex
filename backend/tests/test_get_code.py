"""
Tests for GET /code endpoint.

Verifies that authenticated users can retrieve their 6-character code.
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
    """Generate valid code and token for testing."""
    test_client, data_file = client

    # Generate code
    code_response = test_client.post("/generate-code")
    code = code_response.get_json()["code"]

    # Generate token
    token_response = test_client.post("/generate-token", json={"code": code})
    token = token_response.get_json()["token"]

    return test_client, data_file, code, token


def test_get_code_requires_authentication(client):
    """GET /code requires token authentication."""
    test_client, _ = client
    response = test_client.get("/code")
    assert response.status_code == 401


def test_get_code_returns_code_for_authenticated_user(auth_token):
    """Returns the 6-character code for authenticated user."""
    test_client, _, expected_code, token = auth_token

    response = test_client.get("/code", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    data = response.get_json()
    assert "code" in data
    assert data["code"] == expected_code
    assert len(data["code"]) == 6


def test_get_code_with_invalid_token_returns_401(client):
    """Invalid token returns 401."""
    test_client, _ = client
    response = test_client.get("/code", headers={"Authorization": "Bearer invalid-token"})
    assert response.status_code == 401


def test_get_code_with_malformed_auth_header_returns_401(client):
    """Malformed Authorization header returns 401."""
    test_client, _ = client

    # Missing "Bearer" prefix
    response = test_client.get("/code", headers={"Authorization": "just-a-token"})
    assert response.status_code == 401

    # No token after "Bearer"
    response = test_client.get("/code", headers={"Authorization": "Bearer "})
    assert response.status_code == 401


def test_get_code_rate_limiting(auth_token):
    """Rate limiting applies to GET /code."""
    test_client, _, _, token = auth_token

    # Make 10 requests (rate limit)
    for _ in range(10):
        response = test_client.get("/code", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 200

    # 11th request should be rate limited
    response = test_client.get("/code", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 429


def test_get_code_returns_same_code_on_multiple_calls(auth_token):
    """Multiple calls return the same code (idempotent)."""
    test_client, _, expected_code, token = auth_token

    # Call endpoint multiple times
    for _ in range(3):
        response = test_client.get("/code", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 200
        data = response.get_json()
        assert data["code"] == expected_code


def test_different_users_get_different_codes(client):
    """Different users receive their own codes, not others'."""
    test_client, _ = client

    # User 1
    code1_response = test_client.post("/generate-code")
    code1 = code1_response.get_json()["code"]
    token1_response = test_client.post("/generate-token", json={"code": code1})
    token1 = token1_response.get_json()["token"]

    # User 2
    code2_response = test_client.post("/generate-code")
    code2 = code2_response.get_json()["code"]
    token2_response = test_client.post("/generate-token", json={"code": code2})
    token2 = token2_response.get_json()["token"]

    # Verify different codes
    assert code1 != code2

    # User 1 retrieves their code
    response1 = test_client.get("/code", headers={"Authorization": f"Bearer {token1}"})
    assert response1.status_code == 200
    assert response1.get_json()["code"] == code1

    # User 2 retrieves their code
    response2 = test_client.get("/code", headers={"Authorization": f"Bearer {token2}"})
    assert response2.status_code == 200
    assert response2.get_json()["code"] == code2
