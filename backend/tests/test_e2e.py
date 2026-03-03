import threading
import time

import pytest
import requests
from werkzeug.serving import make_server

from app.main import create_app


class ServerThread(threading.Thread):
    """Thread to run Flask server for E2E testing."""

    def __init__(self, app, port):
        super().__init__(daemon=True)
        self.server = make_server("127.0.0.1", port, app)
        self.ctx = app.app_context()
        self.ctx.push()

    def run(self):
        self.server.serve_forever()

    def shutdown(self):
        self.server.shutdown()


@pytest.fixture(scope="module")
def server_url(tmp_path_factory):
    """Start Flask server in a separate thread for E2E testing."""
    tmp_dir = tmp_path_factory.mktemp("data")
    data_file = tmp_dir / "test_storage.json"

    app = create_app(data_file=data_file)
    # Use port 5556 to avoid conflicts with other test servers (5555 is used by frontend E2E tests)
    port = 5556
    server_thread = ServerThread(app, port)
    server_thread.start()

    # Wait for server to start
    url = f"http://127.0.0.1:{port}"
    max_retries = 30
    for _ in range(max_retries):
        try:
            requests.get(url, timeout=1)
            break
        except requests.exceptions.RequestException:
            time.sleep(0.1)

    yield url

    server_thread.shutdown()


def _make_event(date, medicine_type, count=1):
    import uuid
    return {
        "id": str(uuid.uuid4()),
        "date": date,
        "timestamp": f"{date}T12:00:00.000Z",
        "type": medicine_type,
        "count": count,
        "preventive": False,
    }


def test_e2e_generate_code_and_login_flow(server_url):
    """Test the complete flow: generate code, get token, and save event."""

    # Step 1: Generate a code
    response = requests.post(f"{server_url}/generate-code")
    assert response.status_code == 200
    data = response.json()
    assert "code" in data
    code = data["code"]
    assert len(code) == 6

    # Step 2: Exchange code for token
    token_response = requests.post(f"{server_url}/generate-token", json={"code": code})
    assert token_response.status_code == 200
    token = token_response.json()["token"]

    # Step 3: Save an event using token
    event_response = requests.post(
        f"{server_url}/events",
        headers={"Authorization": f"Bearer {token}"},
        json={"event": _make_event("2026-02-09", "spray", 2)},
    )
    assert event_response.status_code == 200
    assert event_response.json()["status"] == "saved"


def test_e2e_invalid_code_rejection(server_url):
    """Test that invalid codes and tokens are rejected."""

    # Try to login with invalid code
    response = requests.post(
        f"{server_url}/login",
        json={"code": "INVALID"}
    )
    assert response.status_code == 400
    data = response.json()
    assert "error" in data

    # Try to save event with invalid token
    response = requests.post(
        f"{server_url}/events",
        headers={"Authorization": "Bearer invalid-token"},
        json={"event": _make_event("2026-02-09", "spray", 1)},
    )
    assert response.status_code == 401
    assert "error" in response.json()


def test_e2e_multiple_codes_are_independent(server_url):
    """Test that multiple codes can coexist."""

    # Generate first code and token
    response1 = requests.post(f"{server_url}/generate-code")
    code1 = response1.json()["code"]
    token1 = requests.post(f"{server_url}/generate-token", json={"code": code1}).json()["token"]

    # Generate second code and token
    response2 = requests.post(f"{server_url}/generate-code")
    code2 = response2.json()["code"]
    token2 = requests.post(f"{server_url}/generate-token", json={"code": code2}).json()["token"]

    assert code1 != code2

    # Both tokens should work for saving events
    event1 = requests.post(
        f"{server_url}/events",
        headers={"Authorization": f"Bearer {token1}"},
        json={"event": _make_event("2026-02-09", "spray", 1)},
    )
    assert event1.status_code == 200

    event2 = requests.post(
        f"{server_url}/events",
        headers={"Authorization": f"Bearer {token2}"},
        json={"event": _make_event("2026-02-10", "spray", 2)},
    )
    assert event2.status_code == 200


def test_e2e_token_generation_flow(server_url):
    """Test the complete token generation flow."""

    # Step 1: Generate a code
    code_response = requests.post(f"{server_url}/generate-code")
    assert code_response.status_code == 200
    code = code_response.json()["code"]

    # Step 2: Exchange code for token
    token_response = requests.post(
        f"{server_url}/generate-token",
        json={"code": code}
    )
    assert token_response.status_code == 200
    data = token_response.json()
    assert "token" in data
    token = data["token"]

    # Token should be long and hex
    assert len(token) >= 32
    assert all(c in "0123456789abcdef" for c in token)

    # Step 3: Requesting token again with same code returns same token
    token_response2 = requests.post(
        f"{server_url}/generate-token",
        json={"code": code}
    )
    assert token_response2.status_code == 200
    assert token_response2.json()["token"] == token


def test_e2e_complete_token_auth_workflow(server_url):
    """Test the complete workflow: code → token → save event with token."""

    # Step 1: Generate a code
    code_response = requests.post(f"{server_url}/generate-code")
    code = code_response.json()["code"]

    # Step 2: Generate token
    token_response = requests.post(
        f"{server_url}/generate-token",
        json={"code": code}
    )
    token = token_response.json()["token"]

    # Step 3: Save event using token
    event_response = requests.post(
        f"{server_url}/events",
        headers={"Authorization": f"Bearer {token}"},
        json={"event": _make_event("2026-02-09", "spray", 2)},
    )
    assert event_response.status_code == 200
    assert event_response.json()["status"] == "saved"
