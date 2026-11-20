"""Passkey login tests using real ECDSA signatures."""

import base64
import hashlib
import json
import sqlite3
from pathlib import Path

import cbor2
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec

from app.main import create_app
from app.sqlite_storage import PasskeyCredential, SqliteStorage


def b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def assertion(options: dict, key: ec.EllipticCurvePrivateKey, handle: bytes, *, origin: str = "https://fredrikmeyer.net", counter: int = 1, flags: int = 5) -> dict:
    client_data = json.dumps({"type": "webauthn.get", "challenge": options["challenge"], "origin": origin}).encode()
    auth_data = hashlib.sha256(b"fredrikmeyer.net").digest() + bytes([flags]) + counter.to_bytes(4, "big")
    signature = key.sign(auth_data + hashlib.sha256(client_data).digest(), ec.ECDSA(hashes.SHA256()))
    return {"id": b64(b"credential"), "rawId": b64(b"credential"), "type": "public-key", "response": {"clientDataJSON": b64(client_data), "authenticatorData": b64(auth_data), "signature": b64(signature), "userHandle": b64(handle)}}


def test_passkey_login_issues_new_token_and_rejects_replay(tmp_path: Path) -> None:
    data, db = tmp_path / "data.json", tmp_path / "data.db"
    app = create_app(data, db)
    key = ec.generate_private_key(ec.SECP256R1())
    public = key.public_key().public_numbers()
    cose = cbor2.dumps({1: 2, 3: -7, -1: 1, -2: public.x.to_bytes(32, "big"), -3: public.y.to_bytes(32, "big")})
    with app.test_client() as client:
        code = client.post("/generate-code").get_json()["code"]
        old = client.post("/generate-token", json={"code": code}).get_json()["token"]
        storage = SqliteStorage(db)
        handle = storage.get_or_create_passkey_user_handle(code)
        storage.add_passkey_credential(PasskeyCredential(credential_id=b"credential", code=code, public_key=cose, sign_count=0, created_at="2026-01-01", device_type="single_device", backed_up=False))
        storage.close()
        options = client.post("/passkeys/login/options").get_json()
        payload = {"challenge_id": options["challenge_id"], "credential": assertion(options["options"], key, handle)}
        response = client.post("/passkeys/login/verify", json=payload)
        assert response.status_code == 200
        token = response.get_json()["token"]
        assert token != old
        for value in (old, token):
            assert client.get("/code", headers={"Authorization": f"Bearer {value}"}).get_json()["code"] == code
        assert client.post("/passkeys/login/verify", json=payload).status_code == 400
        assert token not in data.read_text()
        with sqlite3.connect(db) as connection:
            assert connection.execute("SELECT COUNT(*) FROM auth_tokens WHERE token_hash = ?", (token,)).fetchone()[0] == 0

        for variant in ("origin", "signature", "user_handle", "user_verification", "counter", "credential_id"):
            options = client.post("/passkeys/login/options").get_json()
            bad_key = ec.generate_private_key(ec.SECP256R1()) if variant == "signature" else key
            bad_handle = b"incorrect" if variant == "user_handle" else handle
            origin = "https://evil.example" if variant == "origin" else "https://fredrikmeyer.net"
            flags = 1 if variant == "user_verification" else 5
            bad = assertion(options["options"], bad_key, bad_handle, origin=origin, flags=flags)
            if variant == "credential_id":
                bad["id"] = bad["rawId"] = b64(b"unknown")
            assert client.post("/passkeys/login/verify", json={"challenge_id": options["challenge_id"], "credential": bad}).status_code == 401

    restarted = create_app(data, db)
    with restarted.test_client() as client:
        for value in (old, token):
            assert client.get("/code", headers={"Authorization": f"Bearer {value}"}).get_json()["code"] == code
        options = client.post("/passkeys/login/options").get_json()
        payload = {"challenge_id": options["challenge_id"], "credential": assertion(options["options"], key, handle, counter=2)}
        assert client.post("/passkeys/login/verify", json=payload).status_code == 200
