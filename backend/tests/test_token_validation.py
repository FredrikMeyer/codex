"""
Tests for token validation middleware (Phase 1.2).

The token validation middleware:
1. Checks for Authorization header with Bearer token
2. Validates token against stored tokens
3. Returns 401 if token missing or invalid
4. Allows request to proceed if token valid
"""

import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from app.main import create_app
from app.sqlite_storage import SqliteStorage


@pytest.fixture()
def client(tmp_path: Path):
    """Create test client with temporary data file."""
    data_file = tmp_path / "data.json"
    app = create_app(data_file)
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client, data_file


@pytest.fixture()
def valid_token(client):
    """Generate a valid token for testing."""
    test_client, _ = client

    # Generate code and token
    code = test_client.post("/generate-code").get_json()["code"]
    token = test_client.post("/generate-token", json={"code": code}).get_json()["token"]

    return token, test_client


def test_sqlite_hashed_token_authenticates_after_restart(tmp_path: Path):
    data_file = tmp_path / "data.json"
    db_file = tmp_path / "data.db"
    app = create_app(data_file, db_file)
    with app.test_client() as client:
        code = client.post("/generate-code").get_json()["code"]
        legacy = client.post("/generate-token", json={"code": code}).get_json()["token"]

    storage = SqliteStorage(db_file)
    storage.add_hashed_token(code, "device-token", "2026-01-01")
    storage.close()

    restarted = create_app(data_file, db_file)
    with restarted.test_client() as client:
        for token in (legacy, "device-token"):
            response = client.get("/code", headers={"Authorization": f"Bearer {token}"})
            assert response.status_code == 200
            assert response.get_json()["code"] == code


def test_startup_migrates_existing_tokens_without_signing_out(tmp_path: Path):
    data_file = tmp_path / "data.json"
    db_file = tmp_path / "data.db"
    data_file.write_text(json.dumps({"codes": [{
        "code": "ABC123", "created_at": "2026-01-01", "token": "old-token"
    }]}))

    for _ in range(2):
        app = create_app(data_file, db_file)
        with app.test_client() as client:
            response = client.get("/code", headers={"Authorization": "Bearer old-token"})
            assert response.status_code == 200
            assert response.get_json()["code"] == "ABC123"
        storage = SqliteStorage(db_file)
        assert storage.get_code_for_hashed_token("old-token") == "ABC123"
        storage.close()


def test_multiple_devices_survive_restart_and_are_isolated(tmp_path: Path):
    data_file = tmp_path / "data.json"
    db_file = tmp_path / "data.db"
    data_file.write_text(json.dumps({"codes": [
        {"code": "ABC123", "created_at": "2026-01-01", "token": "old-token"},
        {"code": "OTHER1", "created_at": "2026-01-01", "token": "other-token"},
    ]}))
    app = create_app(data_file, db_file)
    with app.test_client() as client:
        tokens = ["old-token"] + [
            client.post("/generate-token", json={"code": "ABC123"}).get_json()["token"]
            for _ in range(2)
        ]
        assert len(set(tokens)) == 3
        event = {"id": "private-event", "date": "2026-01-01", "timestamp": "2026-01-01T12:00:00Z", "type": "spray", "count": 1}
        assert client.post("/events", json={"event": event}, headers={"Authorization": f"Bearer {tokens[0]}"}).status_code == 200
    app = create_app(data_file, db_file)
    with app.test_client() as client:
        for token in tokens:
            response = client.get("/events", headers={"Authorization": f"Bearer {token}"})
            assert response.status_code == 200
            assert any(event["id"] == "private-event" for event in response.get_json()["events"])
        response = client.get("/events", headers={"Authorization": "Bearer other-token"})
        assert all(event["id"] != "private-event" for event in response.get_json()["events"])
    assert all(token not in data_file.read_text() for token in tokens[1:])


def test_concurrent_sqlite_token_issuance(tmp_path: Path):
    data_file = tmp_path / "data.json"
    db_file = tmp_path / "data.db"
    app = create_app(data_file, db_file)
    with app.test_client() as client:
        code = client.post("/generate-code").get_json()["code"]

    second_worker = create_app(data_file, db_file)

    def issue(worker):
        with worker.test_client() as client:
            return client.post("/generate-token", json={"code": code}).get_json()["token"]

    with ThreadPoolExecutor(max_workers=2) as pool:
        tokens = list(pool.map(issue, (app, second_worker)))
    assert len(set(tokens)) == 2
    with app.test_client() as client:
        for token in tokens:
            assert client.get("/code", headers={"Authorization": f"Bearer {token}"}).status_code == 200


def test_missing_authorization_header_returns_401(valid_token):
    """Request without Authorization header is rejected."""
    _token, test_client = valid_token

    # Try to access protected endpoint without header
    # Note: We'll create a test endpoint for this
    response = test_client.get("/test-protected")

    assert response.status_code == 401
    data = response.get_json()
    assert "error" in data
    assert "authorization" in data["error"].lower() or "token" in data["error"].lower()


def test_invalid_authorization_format_returns_401(valid_token):
    """Authorization header without 'Bearer' format is rejected."""
    token, test_client = valid_token

    # Wrong format: missing "Bearer"
    response = test_client.get(
        "/test-protected",
        headers={"Authorization": token}
    )
    assert response.status_code == 401

    # Wrong format: wrong prefix
    response = test_client.get(
        "/test-protected",
        headers={"Authorization": f"Token {token}"}
    )
    assert response.status_code == 401


def test_invalid_token_returns_401(valid_token):
    """Request with invalid token is rejected."""
    _token, test_client = valid_token

    # Invalid token
    response = test_client.get(
        "/test-protected",
        headers={"Authorization": "Bearer invalid-token-12345"}
    )

    assert response.status_code == 401
    data = response.get_json()
    assert "error" in data


def test_valid_token_allows_access(valid_token):
    """Request with valid token is allowed."""
    token, test_client = valid_token

    response = test_client.get(
        "/test-protected",
        headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "authorized"


def test_token_validation_is_case_sensitive(valid_token):
    """Token validation is case-sensitive."""
    token, test_client = valid_token

    # Try with uppercase token (should fail)
    response = test_client.get(
        "/test-protected",
        headers={"Authorization": f"Bearer {token.upper()}"}
    )

    assert response.status_code == 401


def test_multiple_valid_tokens_work(client):
    """Multiple different tokens can all be validated."""
    test_client, _data_file = client

    # Generate two different tokens
    code1 = test_client.post("/generate-code").get_json()["code"]
    token1 = test_client.post("/generate-token", json={"code": code1}).get_json()["token"]

    code2 = test_client.post("/generate-code").get_json()["code"]
    token2 = test_client.post("/generate-token", json={"code": code2}).get_json()["token"]

    # Both tokens should work
    response1 = test_client.get(
        "/test-protected",
        headers={"Authorization": f"Bearer {token1}"}
    )
    assert response1.status_code == 200

    response2 = test_client.get(
        "/test-protected",
        headers={"Authorization": f"Bearer {token2}"}
    )
    assert response2.status_code == 200


def test_decorator_preserves_endpoint_functionality(valid_token):
    """The decorator doesn't interfere with endpoint logic."""
    token, test_client = valid_token

    # The protected endpoint should still return its normal response
    response = test_client.get(
        "/test-protected",
        headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    data = response.get_json()
    assert "status" in data
    assert data["status"] == "authorized"


def test_whitespace_in_token_is_handled(valid_token):
    """Extra whitespace in Authorization header is handled correctly."""
    token, test_client = valid_token

    # Extra spaces around Bearer
    response = test_client.get(
        "/test-protected",
        headers={"Authorization": f"  Bearer   {token}  "}
    )

    # Should still work (or consistently fail)
    # Implementation choice: we'll trim whitespace
    assert response.status_code == 200


def test_empty_bearer_token_returns_401(valid_token):
    """Empty token after 'Bearer' is rejected."""
    _token, test_client = valid_token

    response = test_client.get(
        "/test-protected",
        headers={"Authorization": "Bearer "}
    )

    assert response.status_code == 401
