"""
Tests for CORS (Cross-Origin Resource Sharing) support.

CORS headers must be properly configured to allow the frontend
(hosted on GitHub Pages) to communicate with the backend
(hosted on Digital Ocean).
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
        yield client


def test_cors_headers_present_on_generate_code(client):
    """CORS headers are present on /generate-code endpoint."""
    response = client.post(
        "/generate-code",
        headers={"Origin": "https://example.github.io"}
    )

    assert response.status_code == 200
    assert "Access-Control-Allow-Origin" in response.headers


def test_cors_headers_present_on_login(client):
    """CORS headers are present on /login endpoint."""
    response = client.post(
        "/login",
        json={"code": "TEST"},
        headers={"Origin": "https://example.github.io"}
    )

    # Even on error, CORS headers should be present
    assert "Access-Control-Allow-Origin" in response.headers


def test_cors_headers_present_on_generate_token(client):
    """CORS headers are present on /generate-token endpoint."""
    response = client.post(
        "/generate-token",
        json={"code": "TEST"},
        headers={"Origin": "https://example.github.io"}
    )

    # Even on error, CORS headers should be present
    assert "Access-Control-Allow-Origin" in response.headers


def test_cors_headers_present_on_logs(client):
    """CORS headers are present on /logs endpoint."""
    response = client.post(
        "/logs",
        json={"log": {"date": "2026-02-09", "spray": 1}},
        headers={"Origin": "https://example.github.io"}
    )

    # Even on error, CORS headers should be present
    assert "Access-Control-Allow-Origin" in response.headers


def test_cors_allows_credentials(client):
    """CORS configuration allows credentials (needed for auth headers)."""
    response = client.post(
        "/generate-code",
        headers={"Origin": "https://example.github.io"}
    )

    # Credentials must be allowed for Authorization header
    assert response.headers.get("Access-Control-Allow-Credentials") == "true"


def test_cors_preflight_request(client):
    """CORS preflight (OPTIONS) requests are handled correctly."""
    response = client.options(
        "/logs",
        headers={
            "Origin": "https://example.github.io",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "Content-Type,Authorization"
        }
    )

    # Preflight should return 200
    assert response.status_code == 200

    # Should include CORS headers
    assert "Access-Control-Allow-Origin" in response.headers
    assert "Access-Control-Allow-Methods" in response.headers
    assert "Access-Control-Allow-Headers" in response.headers


def test_cors_allows_authorization_header(client):
    """CORS configuration allows Authorization header."""
    response = client.options(
        "/logs",
        headers={
            "Origin": "https://example.github.io",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "Authorization"
        }
    )

    # Authorization header should be allowed
    allowed_headers = response.headers.get("Access-Control-Allow-Headers", "")
    assert "Authorization" in allowed_headers or "*" in allowed_headers


def test_cors_allows_content_type_header(client):
    """CORS configuration allows Content-Type header."""
    response = client.options(
        "/logs",
        headers={
            "Origin": "https://example.github.io",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "Content-Type"
        }
    )

    # Content-Type header should be allowed
    allowed_headers = response.headers.get("Access-Control-Allow-Headers", "")
    assert "Content-Type" in allowed_headers or "*" in allowed_headers


def test_cors_allows_post_method(client):
    """CORS configuration allows POST method."""
    response = client.options(
        "/logs",
        headers={
            "Origin": "https://example.github.io",
            "Access-Control-Request-Method": "POST"
        }
    )

    # POST method should be allowed
    allowed_methods = response.headers.get("Access-Control-Allow-Methods", "")
    assert "POST" in allowed_methods or "*" in allowed_methods
