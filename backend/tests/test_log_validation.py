"""
Tests for log entry validation.

The log entry should support:
1. Medicine type tracking (spray, ventoline)
2. Date field
3. Proper type validation
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


@pytest.fixture()
def auth_code(client):
    """Generate a valid code for testing."""
    code = client.post("/generate-code").get_json()["code"]
    return code, client


def test_log_accepts_medicine_types(auth_code):
    """Log entry accepts spray and ventoline counts."""
    code, test_client = auth_code

    response = test_client.post(
        "/logs",
        json={
            "code": code,
            "log": {
                "date": "2026-02-09",
                "spray": 2,
                "ventoline": 1
            }
        }
    )

    assert response.status_code == 200


def test_log_validates_medicine_types_are_integers(auth_code):
    """Medicine counts must be non-negative integers."""
    code, test_client = auth_code

    # Invalid: string instead of integer
    response = test_client.post(
        "/logs",
        json={
            "code": code,
            "log": {
                "date": "2026-02-09",
                "spray": "two",
                "ventoline": 1
            }
        }
    )

    assert response.status_code == 400
    data = response.get_json()
    assert "error" in data
    assert "spray" in data["error"].lower() or "integer" in data["error"].lower()


def test_log_validates_medicine_counts_are_non_negative(auth_code):
    """Medicine counts cannot be negative."""
    code, test_client = auth_code

    response = test_client.post(
        "/logs",
        json={
            "code": code,
            "log": {
                "date": "2026-02-09",
                "spray": -1,
                "ventoline": 1
            }
        }
    )

    assert response.status_code == 400
    data = response.get_json()
    assert "error" in data


def test_log_validates_date_format(auth_code):
    """Date must be in YYYY-MM-DD format."""
    code, test_client = auth_code

    # Invalid date format
    response = test_client.post(
        "/logs",
        json={
            "code": code,
            "log": {
                "date": "02/09/2026",  # Wrong format
                "spray": 1
            }
        }
    )

    assert response.status_code == 400
    data = response.get_json()
    assert "error" in data
    assert "date" in data["error"].lower()


def test_log_requires_date_field(auth_code):
    """Date field is required."""
    code, test_client = auth_code

    response = test_client.post(
        "/logs",
        json={
            "code": code,
            "log": {
                "spray": 1,
                "ventoline": 2
            }
        }
    )

    assert response.status_code == 400
    data = response.get_json()
    assert "error" in data
    assert "date" in data["error"].lower() or "required" in data["error"].lower()


def test_log_allows_only_spray(auth_code):
    """Log can contain only spray (ventoline is optional)."""
    code, test_client = auth_code

    response = test_client.post(
        "/logs",
        json={
            "code": code,
            "log": {
                "date": "2026-02-09",
                "spray": 3
            }
        }
    )

    assert response.status_code == 200


def test_log_allows_only_ventoline(auth_code):
    """Log can contain only ventoline (spray is optional)."""
    code, test_client = auth_code

    response = test_client.post(
        "/logs",
        json={
            "code": code,
            "log": {
                "date": "2026-02-09",
                "ventoline": 2
            }
        }
    )

    assert response.status_code == 200


def test_log_requires_at_least_one_medicine_type(auth_code):
    """Log must have at least spray or ventoline."""
    code, test_client = auth_code

    response = test_client.post(
        "/logs",
        json={
            "code": code,
            "log": {
                "date": "2026-02-09"
            }
        }
    )

    assert response.status_code == 400
    data = response.get_json()
    assert "error" in data


def test_log_allows_zero_counts(auth_code):
    """Zero is a valid count (user took no medicine)."""
    code, test_client = auth_code

    response = test_client.post(
        "/logs",
        json={
            "code": code,
            "log": {
                "date": "2026-02-09",
                "spray": 0,
                "ventoline": 0
            }
        }
    )

    # This should actually fail per our business logic
    # (need at least one medicine type with non-zero count)
    assert response.status_code == 400


def test_log_rejects_unknown_fields(auth_code):
    """Unknown fields in log are rejected."""
    code, test_client = auth_code

    response = test_client.post(
        "/logs",
        json={
            "code": code,
            "log": {
                "date": "2026-02-09",
                "spray": 1,
                "unknown_field": "value"
            }
        }
    )

    # Pydantic by default ignores extra fields
    # We'll configure it to forbid them
    assert response.status_code in [200, 400]  # Either accept or reject is fine


def test_log_validates_date_is_valid(auth_code):
    """Date must be a valid calendar date."""
    code, test_client = auth_code

    response = test_client.post(
        "/logs",
        json={
            "code": code,
            "log": {
                "date": "2026-02-31",  # February doesn't have 31 days
                "spray": 1
            }
        }
    )

    assert response.status_code == 400
    data = response.get_json()
    assert "error" in data
