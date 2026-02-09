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
    port = 5001
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


def test_e2e_generate_code_and_login_flow(server_url):
    """Test the complete flow: generate code, login, and save logs."""

    # Step 1: Generate a code
    response = requests.post(f"{server_url}/generate-code")
    assert response.status_code == 200
    data = response.json()
    assert "code" in data
    code = data["code"]
    assert len(code) == 4

    # Step 2: Login with the code
    login_response = requests.post(
        f"{server_url}/login",
        json={"code": code}
    )
    assert login_response.status_code == 200
    login_data = login_response.json()
    assert login_data["status"] == "ok"

    # Step 3: Save a log entry
    log_payload = {
        "code": code,
        "log": {
            "date": "2026-02-09",
            "spray": 2,
            "ventoline": 1
        }
    }
    log_response = requests.post(
        f"{server_url}/logs",
        json=log_payload
    )
    assert log_response.status_code == 200
    log_data = log_response.json()
    assert log_data["status"] == "saved"


def test_e2e_invalid_code_rejection(server_url):
    """Test that invalid codes are rejected."""

    # Try to login with invalid code
    response = requests.post(
        f"{server_url}/login",
        json={"code": "INVALID"}
    )
    assert response.status_code == 400
    data = response.json()
    assert "error" in data

    # Try to save log with invalid code
    response = requests.post(
        f"{server_url}/logs",
        json={
            "code": "INVALID",
            "log": {"date": "2026-02-09", "spray": 1}
        }
    )
    assert response.status_code == 400
    data = response.json()
    assert "error" in data


def test_e2e_multiple_codes_are_independent(server_url):
    """Test that multiple codes can coexist."""

    # Generate first code
    response1 = requests.post(f"{server_url}/generate-code")
    code1 = response1.json()["code"]

    # Generate second code
    response2 = requests.post(f"{server_url}/generate-code")
    code2 = response2.json()["code"]

    assert code1 != code2

    # Both codes should work for login
    login1 = requests.post(f"{server_url}/login", json={"code": code1})
    assert login1.status_code == 200

    login2 = requests.post(f"{server_url}/login", json={"code": code2})
    assert login2.status_code == 200

    # Both codes should work for saving logs
    log1 = requests.post(
        f"{server_url}/logs",
        json={"code": code1, "log": {"date": "2026-02-09", "spray": 1}}
    )
    assert log1.status_code == 200

    log2 = requests.post(
        f"{server_url}/logs",
        json={"code": code2, "log": {"date": "2026-02-10", "spray": 2}}
    )
    assert log2.status_code == 200


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
    """Test the complete workflow: code → token → save log with token."""

    # Step 1: Generate a code
    code_response = requests.post(f"{server_url}/generate-code")
    code = code_response.json()["code"]

    # Step 2: Generate token
    token_response = requests.post(
        f"{server_url}/generate-token",
        json={"code": code}
    )
    token = token_response.json()["token"]

    # Step 3: Save log using token (no code needed)
    log_response = requests.post(
        f"{server_url}/logs",
        headers={"Authorization": f"Bearer {token}"},
        json={"log": {"date": "2026-02-09", "spray": 2, "ventoline": 1}}
    )
    assert log_response.status_code == 200
    assert log_response.json()["status"] == "saved"
