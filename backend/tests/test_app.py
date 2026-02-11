from pathlib import Path

import pytest

from app.main import create_app
from app.storage import load_data


@pytest.fixture()
def client(tmp_path: Path):
    data_file = tmp_path / "data.json"
    app = create_app(data_file)
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client, data_file


def test_generate_code_creates_and_persists_code(client):
    test_client, data_file = client
    response = test_client.post("/generate-code")

    assert response.status_code == 200
    body = response.get_json()
    assert "code" in body
    assert len(body["code"]) == 6

    saved_data = load_data(data_file)
    assert any(entry["code"] == body["code"] for entry in saved_data["codes"])


def test_login_accepts_valid_code_and_rejects_invalid(client):
    test_client, data_file = client
    generated = test_client.post("/generate-code").get_json()["code"]

    ok_response = test_client.post("/login", json={"code": generated})
    assert ok_response.status_code == 200
    saved = load_data(data_file)
    assert any(entry.get("last_login_at") for entry in saved["codes"])

    bad_response = test_client.post("/login", json={"code": "ZZZZ"})
    assert bad_response.status_code == 400


def test_logs_endpoint_requires_known_code_and_persists_log(client):
    test_client, data_file = client
    generated = test_client.post("/generate-code").get_json()["code"]
    payload = {"code": generated, "log": {"date": "2024-01-01", "spray": 3}}

    ok_response = test_client.post("/logs", json=payload)
    assert ok_response.status_code == 200
    saved = load_data(data_file)
    assert saved["logs"][0]["log"] == payload["log"]

    bad_response = test_client.post(
        "/logs", json={"code": "FFFF", "log": {"date": "2024-01-01"}}
    )
    assert bad_response.status_code == 400


def test_health_endpoint_returns_ok(client):
    test_client, _ = client
    response = test_client.get("/health")

    assert response.status_code == 200
    body = response.get_json()
    assert body["status"] == "ok"
    assert "version" in body
