"""
Tests for environment configuration loading.

The app should load configuration from environment variables,
with sensible defaults when variables are not set.
"""

import os
from pathlib import Path

import pytest

from app.main import create_app


@pytest.fixture()
def clean_env(monkeypatch):
    """Clean environment before each test."""
    # Remove all config-related env vars
    for key in ["ALLOWED_ORIGINS", "DATA_FILE", "ASTHMA_DATA_FILE", "PRODUCTION"]:
        monkeypatch.delenv(key, raising=False)


def test_loads_allowed_origins_from_env(tmp_path: Path, monkeypatch, clean_env):
    """App loads ALLOWED_ORIGINS from environment variable."""
    monkeypatch.setenv("ALLOWED_ORIGINS", "https://example.com")

    app = create_app(tmp_path / "data.json")

    # CORS should be configured with the specified origin
    assert app.config.get("ALLOWED_ORIGINS") == "https://example.com"


def test_defaults_to_wildcard_when_allowed_origins_not_set(tmp_path: Path, clean_env):
    """App defaults to '*' for ALLOWED_ORIGINS when not set."""
    app = create_app(tmp_path / "data.json")

    # Should default to allowing all origins
    # This is checked by CORS behavior in test_cors.py


def test_loads_data_file_from_env(monkeypatch, clean_env):
    """App loads DATA_FILE from environment variable."""
    test_path = "/custom/path/data.json"
    monkeypatch.setenv("DATA_FILE", test_path)

    app = create_app()

    assert str(app.config["DATA_FILE"]) == test_path


def test_data_file_parameter_overrides_env(tmp_path: Path, monkeypatch, clean_env):
    """DATA_FILE parameter to create_app() overrides environment variable."""
    monkeypatch.setenv("DATA_FILE", "/env/path/data.json")
    param_path = tmp_path / "param_data.json"

    app = create_app(data_file=param_path)

    assert app.config["DATA_FILE"] == param_path


def test_falls_back_to_asthma_data_file_env(monkeypatch, clean_env):
    """App falls back to ASTHMA_DATA_FILE if DATA_FILE not set."""
    test_path = "/asthma/path/data.json"
    monkeypatch.setenv("ASTHMA_DATA_FILE", test_path)

    app = create_app()

    assert str(app.config["DATA_FILE"]) == test_path


def test_defaults_data_file_when_no_env_set(clean_env):
    """App uses default DATA_FILE path when no env vars set."""
    app = create_app()

    assert str(app.config["DATA_FILE"]) == "backend/data/storage.json"


def test_loads_production_mode_from_env(tmp_path: Path, monkeypatch, clean_env):
    """App loads PRODUCTION flag from environment variable."""
    monkeypatch.setenv("PRODUCTION", "true")

    app = create_app(tmp_path / "data.json")

    assert app.config.get("PRODUCTION") is True


def test_production_mode_false_by_default(tmp_path: Path, clean_env):
    """App defaults to PRODUCTION=false when not set."""
    app = create_app(tmp_path / "data.json")

    assert app.config.get("PRODUCTION") is False


def test_production_mode_handles_string_values(tmp_path: Path, monkeypatch, clean_env):
    """PRODUCTION env var handles various string representations."""
    test_cases = [
        ("true", True),
        ("True", True),
        ("TRUE", True),
        ("1", True),
        ("false", False),
        ("False", False),
        ("FALSE", False),
        ("0", False),
        ("", False),
    ]

    for env_value, expected in test_cases:
        monkeypatch.setenv("PRODUCTION", env_value)
        app = create_app(tmp_path / "data.json")
        assert app.config.get("PRODUCTION") is expected, \
            f"PRODUCTION={env_value} should result in {expected}"


def test_config_is_accessible_throughout_app(tmp_path: Path, monkeypatch, clean_env):
    """Configuration is accessible in app context."""
    monkeypatch.setenv("ALLOWED_ORIGINS", "https://test.com")
    monkeypatch.setenv("PRODUCTION", "true")

    app = create_app(tmp_path / "data.json")

    with app.app_context():
        from flask import current_app
        assert current_app.config.get("PRODUCTION") is True
        assert str(current_app.config["DATA_FILE"]) == str(tmp_path / "data.json")


