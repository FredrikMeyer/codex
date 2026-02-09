"""
Tests for rate limiting.

Rate limits prevent abuse and ensure fair usage:
- /generate-code: 5 per hour (prevents code generation spam)
- /login: 10 per minute (prevents brute force)
- /generate-token: 10 per minute (prevents token generation spam)
- /logs: 100 per minute (generous for normal usage)
"""

import time
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
        yield client


def test_generate_code_rate_limit(client):
    """POST /generate-code is rate limited to 5 per hour."""
    # First 5 requests should succeed
    for i in range(5):
        response = client.post("/generate-code")
        assert response.status_code == 200, f"Request {i+1} should succeed"

    # 6th request should be rate limited
    response = client.post("/generate-code")
    assert response.status_code == 429  # Too Many Requests
    data = response.get_json()
    assert "error" in data or "message" in data


def test_login_rate_limit(client):
    """POST /login is rate limited to 10 per minute."""
    # First 10 requests should succeed (or fail with 400 for invalid code)
    for i in range(10):
        response = client.post("/login", json={"code": "TEST"})
        assert response.status_code in [200, 400], f"Request {i+1} should not be rate limited"

    # 11th request should be rate limited
    response = client.post("/login", json={"code": "TEST"})
    assert response.status_code == 429


def test_generate_token_rate_limit(client):
    """POST /generate-token is rate limited to 10 per minute."""
    # First 10 requests should succeed (or fail with 400 for invalid code)
    for i in range(10):
        response = client.post("/generate-token", json={"code": "TEST"})
        assert response.status_code in [200, 400], f"Request {i+1} should not be rate limited"

    # 11th request should be rate limited
    response = client.post("/generate-token", json={"code": "TEST"})
    assert response.status_code == 429


def test_logs_rate_limit(client):
    """POST /logs is rate limited to 100 per minute."""
    # First 100 requests should succeed (or fail with 400/401 for auth)
    for i in range(100):
        response = client.post("/logs", json={"log": {"date": "2026-02-09", "spray": 1}})
        assert response.status_code in [200, 400, 401], f"Request {i+1} should not be rate limited"

    # 101st request should be rate limited
    response = client.post("/logs", json={"log": {"date": "2026-02-09", "spray": 1}})
    assert response.status_code == 429


def test_rate_limit_includes_retry_after_header(client):
    """Rate limit response includes Retry-After header."""
    # Exceed rate limit
    for _ in range(6):
        client.post("/generate-code")

    # Check rate limit response headers
    response = client.post("/generate-code")
    assert response.status_code == 429
    assert "Retry-After" in response.headers or "X-RateLimit-Reset" in response.headers


def test_different_endpoints_have_separate_limits(client):
    """Each endpoint has its own rate limit counter."""
    # Use up generate-code limit
    for _ in range(5):
        client.post("/generate-code")

    # generate-code should be rate limited
    response = client.post("/generate-code")
    assert response.status_code == 429

    # But login should still work (separate limit)
    response = client.post("/login", json={"code": "TEST"})
    assert response.status_code in [200, 400]  # Not rate limited


def test_rate_limits_are_per_ip_address(client):
    """Rate limits are applied per IP address.

    Note: In test environment, all requests come from the same IP,
    so we just verify that the limit applies.
    """
    # Verify rate limit applies to this IP
    for _ in range(5):
        client.post("/generate-code")

    response = client.post("/generate-code")
    assert response.status_code == 429


def test_successful_requests_count_toward_limit(client):
    """Successful requests count toward rate limit."""
    # Generate a valid code
    code_response = client.post("/generate-code")
    assert code_response.status_code == 200
    code = code_response.get_json()["code"]

    # Use up login limit with successful requests
    for _ in range(9):
        client.post("/login", json={"code": code})

    # 10th request should succeed
    response = client.post("/login", json={"code": code})
    assert response.status_code == 200

    # 11th should be rate limited
    response = client.post("/login", json={"code": code})
    assert response.status_code == 429


def test_failed_requests_count_toward_limit(client):
    """Failed requests (400, 401) still count toward rate limit."""
    # Make 10 failed requests (invalid code)
    for _ in range(10):
        response = client.post("/login", json={"code": "INVALID"})
        assert response.status_code == 400

    # 11th request should be rate limited (even though previous failed)
    response = client.post("/login", json={"code": "INVALID"})
    assert response.status_code == 429


def test_rate_limit_response_format(client):
    """Rate limit error response has proper format."""
    # Exceed limit
    for _ in range(6):
        client.post("/generate-code")

    # Check response format
    response = client.post("/generate-code")
    assert response.status_code == 429
    data = response.get_json()

    # Should have error message or rate limit info
    assert data is not None
    assert isinstance(data, dict)
