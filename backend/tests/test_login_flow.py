import tempfile
from pathlib import Path

import pytest

from app.main import create_app


@pytest.fixture
def app():
    with tempfile.TemporaryDirectory() as tmpdir:
        data_file = Path(tmpdir) / "test_storage.json"
        app = create_app(data_file=data_file)
        app.config["TESTING"] = True
        yield app


@pytest.fixture
def client(app):
    return app.test_client()


def test_generate_code_and_login(client):
    response = client.post("/generate-code")
    assert response.status_code == 200
    data = response.get_json()
    assert "code" in data
    code = data["code"]
    assert len(code) == 6

    login_response = client.post("/login", json={"code": code})
    assert login_response.status_code == 200
    login_data = login_response.get_json()
    assert login_data["status"] == "ok"


def test_login_with_invalid_code(client):
    response = client.post("/login", json={"code": "INVALID"})
    assert response.status_code == 400
    data = response.get_json()
    assert "error" in data
    assert data["error"] == "Invalid code"


def test_login_without_code(client):
    response = client.post("/login", json={})
    assert response.status_code == 400
    data = response.get_json()
    assert "error" in data
    assert data["error"] == "Code is required"
