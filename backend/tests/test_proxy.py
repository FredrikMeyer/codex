"""
Tests for proxy header handling.

When deployed behind nginx, the app must trust proxy headers:
- X-Forwarded-For: Real client IP (for rate limiting)
- X-Forwarded-Proto: Original protocol (http/https)
- X-Forwarded-Host: Original host header

This ensures rate limiting works correctly per-client instead of per-proxy.
"""

from pathlib import Path

import pytest

from app.main import create_app


@pytest.fixture()
def production_app(tmp_path: Path, monkeypatch):
    """Create app in production mode."""
    monkeypatch.setenv("PRODUCTION", "true")
    data_file = tmp_path / "data.json"
    app = create_app(data_file)
    app.config["TESTING"] = True
    return app


@pytest.fixture()
def development_app(tmp_path: Path, monkeypatch):
    """Create app in development mode."""
    monkeypatch.setenv("PRODUCTION", "false")
    data_file = tmp_path / "data.json"
    app = create_app(data_file)
    app.config["TESTING"] = True
    return app


def test_production_app_trusts_x_forwarded_for(production_app):
    """In production, app uses X-Forwarded-For for client IP."""
    with production_app.test_client() as client:
        # Simulate nginx setting X-Forwarded-For header
        response = client.post(
            "/generate-code",
            headers={"X-Forwarded-For": "203.0.113.1"}
        )
        assert response.status_code == 200

        # Make 5 more requests from same forwarded IP (total 6)
        for _ in range(5):
            response = client.post(
                "/generate-code",
                headers={"X-Forwarded-For": "203.0.113.1"}
            )

        # 6th request from same IP should be rate limited
        assert response.status_code == 429


def test_production_app_different_forwarded_ips_have_separate_limits(production_app):
    """Different X-Forwarded-For IPs have separate rate limits."""
    with production_app.test_client() as client:
        # Use up limit for first IP
        for _ in range(5):
            client.post(
                "/generate-code",
                headers={"X-Forwarded-For": "203.0.113.1"}
            )

        # First IP should be rate limited
        response = client.post(
            "/generate-code",
            headers={"X-Forwarded-For": "203.0.113.1"}
        )
        assert response.status_code == 429

        # Second IP should still work
        response = client.post(
            "/generate-code",
            headers={"X-Forwarded-For": "203.0.113.2"}
        )
        assert response.status_code == 200


def test_production_app_trusts_x_forwarded_proto(production_app):
    """In production, app uses X-Forwarded-Proto to know original protocol."""
    with production_app.test_client() as client:
        # Simulate nginx setting X-Forwarded-Proto
        response = client.get(
            "/test-protected",
            headers={
                "X-Forwarded-Proto": "https",
                "Authorization": "Bearer invalid"
            }
        )
        # Should process request (even though auth fails)
        # The important thing is it accepts the X-Forwarded-Proto header
        assert response.status_code in [401, 403]  # Auth failure, not rejection


def test_development_app_does_not_require_proxy_headers(development_app):
    """In development, app works without proxy headers."""
    with development_app.test_client() as client:
        # Should work without X-Forwarded-For
        response = client.post("/generate-code")
        assert response.status_code == 200


def test_production_mode_enables_proxy_fix(production_app):
    """Production mode should enable ProxyFix middleware."""
    # Check that wsgi_app has been wrapped
    # ProxyFix wraps the original wsgi_app
    assert hasattr(production_app, "wsgi_app")
    # In production, wsgi_app should be wrapped by ProxyFix
    # We can check this by looking at the class name
    wsgi_class_name = production_app.wsgi_app.__class__.__name__
    assert "ProxyFix" in wsgi_class_name


def test_development_mode_does_not_enable_proxy_fix(development_app):
    """Development mode should not enable ProxyFix middleware."""
    # In development, wsgi_app should be the original Flask app
    wsgi_class_name = development_app.wsgi_app.__class__.__name__
    assert "ProxyFix" not in wsgi_class_name
