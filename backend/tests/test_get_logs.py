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


def test_get_logs_returns_user_logs(auth_token):
    """Returns all logs for authenticated user."""
    test_client, _, code, token = auth_token

    # Save some logs
    test_client.post(
        "/logs",
        json={"code": code, "log": {"date": "2026-02-12", "spray": 2, "ventoline": 1}},
    )
    test_client.post(
        "/logs",
        json={"code": code, "log": {"date": "2026-02-13", "spray": 0, "ventoline": 3}},
    )

    # Get logs
    response = test_client.get("/logs", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    data = response.get_json()
    assert len(data["logs"]) == 2

    # Verify structure
    log = data["logs"][0]
    assert "date" in log
    assert "spray" in log
    assert "ventoline" in log
    assert "received_at" in log


def test_get_logs_excludes_other_users(auth_token):
    """Only returns logs for authenticated user, not others."""
    test_client, _, code1, token1 = auth_token

    # Create second user
    code2_response = test_client.post("/generate-code")
    code2 = code2_response.get_json()["code"]

    # User 1 saves log
    test_client.post(
        "/logs",
        json={"code": code1, "log": {"date": "2026-02-12", "spray": 1, "ventoline": 0}},
    )

    # User 2 saves log
    test_client.post(
        "/logs",
        json={"code": code2, "log": {"date": "2026-02-13", "spray": 2, "ventoline": 0}},
    )

    # User 1 retrieves logs
    response = test_client.get("/logs", headers={"Authorization": f"Bearer {token1}"})

    assert response.status_code == 200
    data = response.get_json()
    assert len(data["logs"]) == 1
    assert data["logs"][0]["date"] == "2026-02-12"


def test_post_log_with_preventive_true_is_saved_and_returned(auth_token):
    """POST /logs with preventive:true saves the flag and GET /logs returns it."""
    test_client, _, code, token = auth_token

    test_client.post(
        "/logs",
        json={"code": code, "log": {"date": "2026-02-20", "spray": 2, "ventoline": 0, "preventive": True}},
    )

    response = test_client.get("/logs", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    logs = response.get_json()["logs"]
    assert len(logs) == 1
    assert logs[0]["preventive"] is True


def test_post_log_without_preventive_defaults_to_false(auth_token):
    """POST /logs without preventive field returns False for preventive in GET /logs."""
    test_client, _, code, token = auth_token

    test_client.post(
        "/logs",
        json={"code": code, "log": {"date": "2026-02-20", "spray": 1, "ventoline": 0}},
    )

    response = test_client.get("/logs", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    logs = response.get_json()["logs"]
    assert len(logs) == 1
    assert logs[0]["preventive"] is False


def test_get_logs_includes_preventive_field(auth_token):
    """GET /logs always includes the preventive field in each log entry."""
    test_client, _, code, token = auth_token

    test_client.post(
        "/logs",
        json={"code": code, "log": {"date": "2026-02-20", "ventoline": 2}},
    )

    response = test_client.get("/logs", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    log = response.get_json()["logs"][0]
    assert "preventive" in log


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
