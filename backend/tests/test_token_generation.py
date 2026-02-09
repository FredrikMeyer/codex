"""
Tests for token generation endpoint (Phase 1.1).

The token generation flow:
1. User has a valid code
2. User exchanges code for a long-lived token
3. Token is stored and can be used for authentication
"""

from pathlib import Path

import pytest

from app.main import create_app, _load_data


@pytest.fixture()
def client(tmp_path: Path):
    """Create test client with temporary data file."""
    data_file = tmp_path / "data.json"
    app = create_app(data_file)
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client, data_file


def test_generate_token_requires_valid_code(client):
    """Token generation requires a valid code."""
    test_client, data_file = client

    # Try to generate token without code
    response = test_client.post("/generate-token", json={})
    assert response.status_code == 400
    assert "error" in response.get_json()

    # Try with invalid code
    response = test_client.post("/generate-token", json={"code": "INVALID"})
    assert response.status_code == 400
    assert "error" in response.get_json()


def test_generate_token_with_valid_code(client):
    """Token is generated for a valid code."""
    test_client, data_file = client

    # Generate a code first
    code_response = test_client.post("/generate-code")
    code = code_response.get_json()["code"]

    # Generate token with valid code
    token_response = test_client.post("/generate-token", json={"code": code})
    assert token_response.status_code == 200

    data = token_response.get_json()
    assert "token" in data
    token = data["token"]

    # Token should be a long string (32+ characters)
    assert len(token) >= 32
    assert isinstance(token, str)


def test_token_is_cryptographically_random(client):
    """Tokens should be cryptographically random (not predictable)."""
    test_client, data_file = client

    # Generate two codes
    code1 = test_client.post("/generate-code").get_json()["code"]
    code2 = test_client.post("/generate-code").get_json()["code"]

    # Generate tokens for both
    token1 = test_client.post("/generate-token", json={"code": code1}).get_json()["token"]
    token2 = test_client.post("/generate-token", json={"code": code2}).get_json()["token"]

    # Tokens should be different
    assert token1 != token2

    # Tokens should be hex strings (using secrets.token_hex)
    assert all(c in "0123456789abcdef" for c in token1)
    assert all(c in "0123456789abcdef" for c in token2)


def test_token_is_persisted_with_code(client):
    """Generated token is stored in data file with the code."""
    test_client, data_file = client

    # Generate code and token
    code = test_client.post("/generate-code").get_json()["code"]
    token = test_client.post("/generate-token", json={"code": code}).get_json()["token"]

    # Check that token is stored
    saved_data = _load_data(data_file)

    # Find the code entry
    code_entry = next(entry for entry in saved_data["codes"] if entry["code"] == code)

    # Token should be stored with the code
    assert "token" in code_entry
    assert code_entry["token"] == token


def test_multiple_token_requests_return_same_token(client):
    """Requesting a token multiple times with same code returns the same token."""
    test_client, data_file = client

    # Generate code
    code = test_client.post("/generate-code").get_json()["code"]

    # Generate token first time
    token1 = test_client.post("/generate-token", json={"code": code}).get_json()["token"]

    # Generate token second time with same code
    token2 = test_client.post("/generate-token", json={"code": code}).get_json()["token"]

    # Should return the same token
    assert token1 == token2


def test_token_generation_updates_timestamp(client):
    """Token generation updates a timestamp."""
    test_client, data_file = client

    # Generate code and token
    code = test_client.post("/generate-code").get_json()["code"]
    test_client.post("/generate-token", json={"code": code})

    # Check timestamp exists
    saved_data = _load_data(data_file)
    code_entry = next(entry for entry in saved_data["codes"] if entry["code"] == code)

    assert "token_generated_at" in code_entry
    # ISO format with timezone offset
    assert code_entry["token_generated_at"].endswith("+00:00") or code_entry["token_generated_at"].endswith("Z")


def test_existing_endpoints_still_work(client):
    """Existing endpoints are not affected by token generation feature."""
    test_client, data_file = client

    # Generate code (existing endpoint)
    code_response = test_client.post("/generate-code")
    assert code_response.status_code == 200
    code = code_response.get_json()["code"]

    # Login with code (existing endpoint)
    login_response = test_client.post("/login", json={"code": code})
    assert login_response.status_code == 200

    # Save log with code (existing endpoint)
    log_response = test_client.post(
        "/logs",
        json={"code": code, "log": {"date": "2026-02-09", "spray": 1}}
    )
    assert log_response.status_code == 200
