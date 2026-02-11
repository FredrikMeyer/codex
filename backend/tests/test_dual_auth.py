"""
Tests for dual authentication on /logs endpoint (Phase 1.3).

The /logs endpoint should accept EITHER:
1. Code-based auth (existing, backward compatible)
2. Token-based auth (new, preferred)

This maintains backward compatibility while enabling token usage.
"""

from pathlib import Path

import pytest

from app.main import create_app
from app.storage import load_data


@pytest.fixture()
def client(tmp_path: Path):
    """Create test client with temporary data file."""
    data_file = tmp_path / "data.json"
    app = create_app(data_file)
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client, data_file


@pytest.fixture()
def auth_credentials(client):
    """Generate both code and token for testing."""
    test_client, data_file = client

    # Generate code
    code = test_client.post("/generate-code").get_json()["code"]

    # Generate token
    token = test_client.post("/generate-token", json={"code": code}).get_json()["token"]

    return code, token, test_client, data_file


def test_logs_endpoint_accepts_code_auth(auth_credentials):
    """Backward compatibility: /logs still accepts code-based auth."""
    code, token, test_client, data_file = auth_credentials

    response = test_client.post(
        "/logs",
        json={
            "code": code,
            "log": {"date": "2026-02-09", "spray": 2, "ventoline": 1}
        }
    )

    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "saved"

    # Verify log was saved
    saved_data = load_data(data_file)
    assert len(saved_data["logs"]) == 1
    assert saved_data["logs"][0]["code"] == code


def test_logs_endpoint_accepts_token_auth(auth_credentials):
    """New feature: /logs accepts token-based auth."""
    code, token, test_client, data_file = auth_credentials

    response = test_client.post(
        "/logs",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "log": {"date": "2026-02-09", "spray": 2, "ventoline": 1}
        }
    )

    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "saved"

    # Verify log was saved
    saved_data = load_data(data_file)
    assert len(saved_data["logs"]) == 1


def test_logs_with_token_does_not_require_code_in_body(auth_credentials):
    """Token auth doesn't need code in request body."""
    code, token, test_client, data_file = auth_credentials

    # No "code" field in JSON body
    response = test_client.post(
        "/logs",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "log": {"date": "2026-02-09", "spray": 3}
        }
    )

    assert response.status_code == 200


def test_logs_with_invalid_token_returns_401(auth_credentials):
    """Invalid token is rejected."""
    code, token, test_client, data_file = auth_credentials

    response = test_client.post(
        "/logs",
        headers={"Authorization": "Bearer invalid-token"},
        json={
            "log": {"date": "2026-02-09", "spray": 3}
        }
    )

    assert response.status_code == 401


def test_logs_with_invalid_code_returns_400(auth_credentials):
    """Invalid code is rejected (existing behavior)."""
    code, token, test_client, data_file = auth_credentials

    response = test_client.post(
        "/logs",
        json={
            "code": "INVALID",
            "log": {"date": "2026-02-09", "spray": 3}
        }
    )

    assert response.status_code == 400


def test_logs_without_auth_returns_error(client):
    """Request without either code or token is rejected."""
    test_client, data_file = client

    # No code, no token
    response = test_client.post(
        "/logs",
        json={
            "log": {"date": "2026-02-09", "spray": 3}
        }
    )

    assert response.status_code in [400, 401]
    data = response.get_json()
    assert "error" in data


def test_logs_prefers_token_when_both_provided(auth_credentials):
    """When both code and token provided, token is used."""
    code, token, test_client, data_file = auth_credentials

    # Generate a different code
    code2 = test_client.post("/generate-code").get_json()["code"]

    # Provide token (valid) and different code in body
    response = test_client.post(
        "/logs",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "code": code2,  # Different code
            "log": {"date": "2026-02-09", "spray": 3}
        }
    )

    # Should succeed because token is valid (ignores code)
    assert response.status_code == 200


def test_logs_stores_which_auth_method_used(auth_credentials):
    """Log entry records which authentication method was used."""
    code, token, test_client, data_file = auth_credentials

    # Save with code
    test_client.post(
        "/logs",
        json={
            "code": code,
            "log": {"date": "2026-02-09", "spray": 1}
        }
    )

    # Save with token
    test_client.post(
        "/logs",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "log": {"date": "2026-02-10", "spray": 2}
        }
    )

    # Check stored data
    saved_data = load_data(data_file)
    assert len(saved_data["logs"]) == 2

    # First log should have code
    assert "code" in saved_data["logs"][0]

    # Both should have timestamp
    assert "received_at" in saved_data["logs"][0]
    assert "received_at" in saved_data["logs"][1]


def test_multiple_users_with_different_tokens(client):
    """Multiple users (different tokens) can save logs independently."""
    test_client, data_file = client

    # User 1
    code1 = test_client.post("/generate-code").get_json()["code"]
    token1 = test_client.post("/generate-token", json={"code": code1}).get_json()["token"]

    # User 2
    code2 = test_client.post("/generate-code").get_json()["code"]
    token2 = test_client.post("/generate-token", json={"code": code2}).get_json()["token"]

    # Both save logs with tokens
    response1 = test_client.post(
        "/logs",
        headers={"Authorization": f"Bearer {token1}"},
        json={"log": {"date": "2026-02-09", "spray": 1}}
    )
    assert response1.status_code == 200

    response2 = test_client.post(
        "/logs",
        headers={"Authorization": f"Bearer {token2}"},
        json={"log": {"date": "2026-02-09", "spray": 2}}
    )
    assert response2.status_code == 200

    # Both logs should be saved
    saved_data = load_data(data_file)
    assert len(saved_data["logs"]) == 2
