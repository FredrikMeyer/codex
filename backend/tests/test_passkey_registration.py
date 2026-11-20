"""Registration tests with real WebAuthn attestation data."""

import base64
import hashlib
import json
import secrets
from pathlib import Path

import cbor2
from cryptography.hazmat.primitives.asymmetric import ec

from app.main import create_app
from app.sqlite_storage import SqliteStorage


def b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode()


def registration(options: dict, *, origin: str = "https://fredrikmeyer.net", verified: bool = True) -> dict:
    key = ec.generate_private_key(ec.SECP256R1()).public_key().public_numbers()
    cose = cbor2.dumps({1: 2, 3: -7, -1: 1, -2: key.x.to_bytes(32, "big"), -3: key.y.to_bytes(32, "big")})
    credential_id = secrets.token_bytes(32)
    flags = b"\x45" if verified else b"\x41"
    auth_data = hashlib.sha256(b"fredrikmeyer.net").digest() + flags + bytes(4) + bytes(16) + len(credential_id).to_bytes(2, "big") + credential_id + cose
    client_data = json.dumps({"type": "webauthn.create", "challenge": options["challenge"], "origin": origin}).encode()
    attestation = cbor2.dumps({"fmt": "none", "attStmt": {}, "authData": auth_data})
    return {"id": b64(credential_id), "rawId": b64(credential_id), "type": "public-key", "response": {"clientDataJSON": b64(client_data), "attestationObject": b64(attestation), "transports": ["internal"]}}


def test_registration_verifies_and_stores_credential(tmp_path: Path) -> None:
    db = tmp_path / "data.db"
    app = create_app(tmp_path / "data.json", db)
    with app.test_client() as client:
        code = client.post("/generate-code").get_json()["code"]
        token = client.post("/generate-token", json={"code": code}).get_json()["token"]
        headers = {"Authorization": f"Bearer {token}"}
        result = client.post("/passkeys/register/options", headers=headers).get_json()
        assert result["options"]["rp"]["id"] == "fredrikmeyer.net"
        payload = {"challenge_id": result["challenge_id"], "credential": registration(result["options"])}
        assert client.post("/passkeys/register/verify", headers=headers, json=payload).status_code == 201
        assert client.post("/passkeys/register/verify", headers=headers, json=payload).status_code == 400
        storage = SqliteStorage(db)
        try:
            credentials = storage.list_passkey_credentials(code)
            assert len(credentials) == 1 and credentials[0]["transports"] == ["internal"]
        finally:
            storage.close()


def test_registration_rejects_wrong_origin_and_missing_verification(tmp_path: Path) -> None:
    app = create_app(tmp_path / "data.json", tmp_path / "data.db")
    with app.test_client() as client:
        code = client.post("/generate-code").get_json()["code"]
        token = client.post("/generate-token", json={"code": code}).get_json()["token"]
        headers = {"Authorization": f"Bearer {token}"}
        assert client.post("/passkeys/register/options").status_code == 401
        for origin, verified in (("https://attacker.example", True), ("https://fredrikmeyer.net", False)):
            result = client.post("/passkeys/register/options", headers=headers).get_json()
            payload = {"challenge_id": result["challenge_id"], "credential": registration(result["options"], origin=origin, verified=verified)}
            assert client.post("/passkeys/register/verify", headers=headers, json=payload).status_code == 400


def test_registration_cannot_be_completed_by_another_account(tmp_path: Path) -> None:
    app = create_app(tmp_path / "data.json", tmp_path / "data.db")
    with app.test_client() as client:
        codes = [client.post("/generate-code").get_json()["code"] for _ in range(2)]
        tokens = [client.post("/generate-token", json={"code": code}).get_json()["token"] for code in codes]
        first, second = [{"Authorization": f"Bearer {token}"} for token in tokens]
        result = client.post("/passkeys/register/options", headers=first).get_json()
        payload = {"challenge_id": result["challenge_id"], "credential": registration(result["options"])}
        assert client.post("/passkeys/register/verify", headers=second, json=payload).status_code == 400
        assert client.post("/passkeys/register/verify", headers=first, json=payload).status_code == 201


def test_registration_rejects_response_for_another_challenge(tmp_path: Path) -> None:
    app = create_app(tmp_path / "data.json", tmp_path / "data.db")
    with app.test_client() as client:
        code = client.post("/generate-code").get_json()["code"]
        token = client.post("/generate-token", json={"code": code}).get_json()["token"]
        headers = {"Authorization": f"Bearer {token}"}
        first = client.post("/passkeys/register/options", headers=headers).get_json()
        second = client.post("/passkeys/register/options", headers=headers).get_json()
        payload = {"challenge_id": first["challenge_id"], "credential": registration(second["options"])}
        assert client.post("/passkeys/register/verify", headers=headers, json=payload).status_code == 400
        payload["credential"] = registration(first["options"])
        assert client.post("/passkeys/register/verify", headers=headers, json=payload).status_code == 400


def test_registration_unavailable_in_json_only_mode(tmp_path: Path) -> None:
    app = create_app(tmp_path / "data.json")
    with app.test_client() as client:
        code = client.post("/generate-code").get_json()["code"]
        token = client.post("/generate-token", json={"code": code}).get_json()["token"]
        response = client.post("/passkeys/register/options", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 503
