"""
Tests for SqliteStorage.

All tests use an in-memory database for speed and isolation.
"""

import sqlite3
from collections.abc import Generator
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from app.sqlite_storage import (
    AsthmaMedicineEventData,
    CodeEntry,
    PasskeyCredential,
    RitalinEventData,
    SqliteStorage,
)


@pytest.fixture()
def storage() -> Generator[SqliteStorage]:
    s = SqliteStorage(":memory:")
    yield s
    s.close()


def _code_entry(
    *,
    code: str = "ABC123",
    created_at: str = "2026-01-01T00:00:00Z",
    token: str | None = None,
    token_generated_at: str | None = None,
    last_login_at: str | None = None,
) -> CodeEntry:
    result: CodeEntry = {"code": code, "created_at": created_at}
    if token is not None:
        result["token"] = token
    if token_generated_at is not None:
        result["token_generated_at"] = token_generated_at
    if last_login_at is not None:
        result["last_login_at"] = last_login_at
    return result


def _asthma_event(
    *,
    id: str = "event-1",
    date: str = "2026-03-01",
    timestamp: str = "2026-03-01T10:00:00.000Z",
    type: str = "spray",
    count: int = 2,
    preventive: bool = False,
) -> AsthmaMedicineEventData:
    return {
        "id": id,
        "date": date,
        "timestamp": timestamp,
        "type": type,
        "count": count,
        "preventive": preventive,
    }


def _ritalin_event(
    *,
    id: str = "ritalin-1",
    date: str = "2026-03-01",
    timestamp: str = "2026-03-01T08:00:00.000Z",
    count: int = 1,
) -> RitalinEventData:
    return {"id": id, "date": date, "timestamp": timestamp, "count": count}


# --- codes ---

def test_passkey_challenges_are_bound_and_single_use(storage: SqliteStorage) -> None:
    storage.upsert_code(_code_entry())
    challenge_id, challenge = storage.create_passkey_challenge("registration", "ABC123")
    assert len(challenge) == 32
    assert storage.consume_passkey_challenge(challenge_id, "registration", "OTHER1") is None
    assert storage.consume_passkey_challenge(challenge_id, "authentication") is None
    assert storage.consume_passkey_challenge(challenge_id, "registration", "ABC123") == challenge
    assert storage.consume_passkey_challenge(challenge_id, "registration", "ABC123") is None
    auth_id, auth_challenge = storage.create_passkey_challenge("authentication")
    assert storage.consume_passkey_challenge(auth_id, "authentication") == auth_challenge
    with pytest.raises(ValueError):
        storage.create_passkey_challenge("registration")
    with pytest.raises(ValueError):
        storage.create_passkey_challenge("authentication", "ABC123")
    with pytest.raises(ValueError, match="Unknown code"):
        storage.create_passkey_challenge("registration", "MISSING")


def test_passkey_challenge_expires_at_deadline(storage: SqliteStorage, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.sqlite_storage.time.time", lambda: 1000)
    challenge_id, _ = storage.create_passkey_challenge("authentication")
    monkeypatch.setattr("app.sqlite_storage.time.time", lambda: 1300)
    assert storage.consume_passkey_challenge(challenge_id, "authentication") is None


def test_passkey_challenge_consumed_once_across_workers(tmp_path: Path) -> None:
    db = tmp_path / "challenge.db"
    first = SqliteStorage(db)
    challenge_id, challenge = first.create_passkey_challenge("authentication")
    first.close()
    first = SqliteStorage(db)
    second = SqliteStorage(db)
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda worker: worker.consume_passkey_challenge(challenge_id, "authentication"), (first, second)))
        assert results.count(challenge) == 1
        assert results.count(None) == 1
    finally:
        first.close()
        second.close()

def test_passkey_handle_survives_account_updates_and_restart(tmp_path: Path) -> None:
    db = tmp_path / "storage.db"
    storage = SqliteStorage(db)
    storage.upsert_code(_code_entry())
    handle = storage.get_or_create_passkey_user_handle("ABC123")
    assert len(handle) == 32
    assert handle != b"ABC123"
    storage.upsert_code(_code_entry(last_login_at="2026-01-02"))
    storage.close()
    storage = SqliteStorage(db)
    try:
        assert storage.get_or_create_passkey_user_handle("ABC123") == handle
        storage.upsert_code(_code_entry(code="OTHER1"))
        assert storage.get_or_create_passkey_user_handle("OTHER1") != handle
        with pytest.raises(ValueError, match="Unknown code"):
            storage.get_or_create_passkey_user_handle("MISSING")
    finally:
        storage.close()


def test_concurrent_workers_create_one_passkey_handle(tmp_path: Path) -> None:
    db = tmp_path / "storage.db"
    first = SqliteStorage(db)
    first.upsert_code(_code_entry())
    second = SqliteStorage(db)
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            handles = list(pool.map(lambda storage: storage.get_or_create_passkey_user_handle("ABC123"), (first, second)))
        assert handles[0] == handles[1]
    finally:
        first.close()
        second.close()


def test_passkey_credentials_persist_and_are_scoped_to_account(tmp_path: Path) -> None:
    db = tmp_path / "credentials.db"
    storage = SqliteStorage(db)
    storage.upsert_code(_code_entry())
    storage.upsert_code(_code_entry(code="OTHER1"))
    storage.get_or_create_passkey_user_handle("ABC123")
    storage.get_or_create_passkey_user_handle("OTHER1")
    first = PasskeyCredential(credential_id=b"id-1", code="ABC123", public_key=b"key-1", sign_count=0, created_at="2026-01-01")
    second = PasskeyCredential(credential_id=b"id-2", code="ABC123", public_key=b"key-2", sign_count=4, created_at="2026-01-02")
    other = PasskeyCredential(credential_id=b"id-3", code="OTHER1", public_key=b"key-3", sign_count=0, created_at="2026-01-03")
    for credential in (first, second, other):
        storage.add_passkey_credential(credential)
    storage.upsert_code(_code_entry(last_login_at="2026-01-04"))
    storage.close()

    storage = SqliteStorage(db)
    try:
        assert storage.list_passkey_credentials("ABC123") == [first, second]
        assert storage.list_passkey_credentials("OTHER1") == [other]
        assert storage.get_passkey_credential(b"id-1") == first
        assert storage.get_passkey_credential(b"unknown") is None
        with pytest.raises(sqlite3.IntegrityError):
            storage.add_passkey_credential({**first, "code": "OTHER1"})
        assert storage.get_passkey_credential(b"id-1") == first
        with pytest.raises(ValueError, match="no passkey user handle"):
            storage.add_passkey_credential({**first, "credential_id": b"new", "code": "UNKNOWN"})
    finally:
        storage.close()


def test_passkey_metadata_and_counter_updates(storage: SqliteStorage) -> None:
    storage.upsert_code(_code_entry())
    storage.get_or_create_passkey_user_handle("ABC123")
    credential = PasskeyCredential(
        credential_id=b"id", code="ABC123", public_key=b"key", sign_count=3,
        created_at="2026-01-01", device_type="multi_device", backed_up=False,
        transports=["internal", "hybrid"],
    )
    storage.add_passkey_credential(credential)
    assert storage.get_passkey_credential(b"id") == credential
    assert storage.update_passkey_after_authentication(b"id", 3, 4, True)
    assert not storage.update_passkey_after_authentication(b"id", 3, 5, False)
    updated = storage.get_passkey_credential(b"id")
    assert updated is not None and updated["sign_count"] == 4 and updated["backed_up"] is True
    with pytest.raises(ValueError, match="counter"):
        storage.update_passkey_after_authentication(b"id", 4, 4, False)


def test_passkey_upgrade_preserves_existing_credential(tmp_path: Path) -> None:
    path = tmp_path / "old.db"
    with sqlite3.connect(path) as conn:
        conn.execute("CREATE TABLE passkey_credentials (credential_id BLOB PRIMARY KEY, code TEXT NOT NULL, public_key BLOB NOT NULL, sign_count INTEGER NOT NULL, created_at TEXT NOT NULL)")
        conn.execute("INSERT INTO passkey_credentials VALUES (?, ?, ?, ?, ?)", (b"id", "ABC123", b"key", 0, "2026-01-01"))
    storage = SqliteStorage(path)
    try:
        assert storage.get_passkey_credential(b"id") == {
            "credential_id": b"id", "code": "ABC123", "public_key": b"key",
            "sign_count": 0, "created_at": "2026-01-01",
        }
        assert storage.update_passkey_after_authentication(b"id", 0, 0, False)
    finally:
        storage.close()

def test_hashed_tokens_survive_reopen_and_code_updates(tmp_path: Path) -> None:
    path = tmp_path / "auth.db"
    storage = SqliteStorage(path)
    storage.upsert_code(_code_entry())
    storage.upsert_code(_code_entry(code="OTHER1"))
    storage.add_hashed_token("ABC123", "first-secret", "2026-01-01")
    storage.add_hashed_token("ABC123", "second-secret", "2026-01-02")
    storage.add_hashed_token("OTHER1", "other-secret", "2026-01-03")
    storage.upsert_code(_code_entry(last_login_at="2026-01-04"))
    storage.close()

    with sqlite3.connect(path) as conn:
        rows = conn.execute("SELECT token_hash FROM auth_tokens").fetchall()
        assert all("secret" not in row[0] for row in rows)

    storage = SqliteStorage(path)
    try:
        assert storage.get_code_for_hashed_token("first-secret") == "ABC123"
        assert storage.get_code_for_hashed_token("second-secret") == "ABC123"
        assert storage.get_code_for_hashed_token("other-secret") == "OTHER1"
        assert storage.get_code_for_hashed_token("unknown") is None
    finally:
        storage.close()


def test_hashed_token_requires_existing_code(storage: SqliteStorage) -> None:
    with pytest.raises(ValueError, match="Unknown code"):
        storage.add_hashed_token("MISSING", "secret", "2026-01-01")


def test_migrate_legacy_tokens_preserves_both_stores_and_is_repeatable(storage: SqliteStorage) -> None:
    storage.upsert_code(_code_entry(token="sqlite-token"))
    json_codes = [_code_entry(token="json-token")]
    storage.migrate_legacy_tokens(json_codes)
    storage.migrate_legacy_tokens(json_codes)
    assert storage.get_code_for_hashed_token("sqlite-token") == "ABC123"
    assert storage.get_code_for_hashed_token("json-token") == "ABC123"
    assert storage.validate_token("sqlite-token")


def test_migrate_legacy_tokens_rolls_back_on_conflict(storage: SqliteStorage) -> None:
    storage.upsert_code(_code_entry(token="first-token"))
    storage.upsert_code(_code_entry(code="OTHER1", token="shared-token"))
    with pytest.raises(ValueError, match="multiple accounts"):
        storage.migrate_legacy_tokens([_code_entry(token="shared-token")])
    assert storage.get_code_for_hashed_token("first-token") is None
    assert storage.get_code_for_hashed_token("shared-token") is None


def test_migrate_legacy_tokens_rejects_unknown_account(storage: SqliteStorage) -> None:
    with pytest.raises(ValueError, match="unknown SQLite account"):
        storage.migrate_legacy_tokens([_code_entry(token="secret")])


def test_remove_legacy_plaintext_tokens_preserves_digest_lookup(storage: SqliteStorage) -> None:
    storage.upsert_code(_code_entry(token="legacy-token"))
    storage.migrate_legacy_tokens([])
    storage.remove_legacy_plaintext_tokens()
    storage.remove_legacy_plaintext_tokens()
    assert storage.get_codes()[0]["token"] is None
    assert storage.get_code_for_hashed_token("legacy-token") == "ABC123"


def test_remove_legacy_plaintext_tokens_requires_all_hashes(storage: SqliteStorage) -> None:
    storage.upsert_code(_code_entry(token="first-token"))
    storage.upsert_code(_code_entry(code="OTHER1", token="second-token"))
    storage.add_hashed_token("ABC123", "first-token", "2026-01-01")
    with pytest.raises(ValueError, match="no matching account digest"):
        storage.remove_legacy_plaintext_tokens()
    assert {entry["token"] for entry in storage.get_codes()} == {"first-token", "second-token"}


def test_remove_legacy_plaintext_tokens_rejects_wrong_owner(storage: SqliteStorage) -> None:
    storage.upsert_code(_code_entry(token="legacy-token"))
    storage.upsert_code(_code_entry(code="OTHER1"))
    storage.add_hashed_token("OTHER1", "legacy-token", "2026-01-01")
    with pytest.raises(ValueError, match="no matching account digest"):
        storage.remove_legacy_plaintext_tokens()
    assert storage.validate_token("legacy-token")

def test_get_codes_returns_empty_initially(storage: SqliteStorage) -> None:
    assert storage.get_codes() == []


def test_upsert_code_stores_entry(storage: SqliteStorage) -> None:
    storage.upsert_code(_code_entry())
    codes = storage.get_codes()
    assert len(codes) == 1
    assert codes[0]["code"] == "ABC123"
    assert codes[0]["created_at"] == "2026-01-01T00:00:00Z"


def test_upsert_code_updates_existing_row(storage: SqliteStorage) -> None:
    storage.upsert_code(_code_entry())
    storage.upsert_code(_code_entry(token="tok123", token_generated_at="2026-01-02T00:00:00Z"))
    codes = storage.get_codes()
    assert len(codes) == 1
    assert codes[0]["token"] == "tok123"


# --- asthma events ---

def test_get_events_returns_empty_for_unknown_code(storage: SqliteStorage) -> None:
    assert storage.get_events("NOBODY") == []


def test_insert_event_stores_all_fields(storage: SqliteStorage) -> None:
    storage.insert_event("ABC123", _asthma_event(), "2026-03-01T10:01:00Z")
    events = storage.get_events("ABC123")
    assert len(events) == 1
    ev = events[0]
    assert ev["id"] == "event-1"
    assert ev["date"] == "2026-03-01"
    assert ev["timestamp"] == "2026-03-01T10:00:00.000Z"
    assert ev["type"] == "spray"
    assert ev["count"] == 2
    assert ev["preventive"] is False


def test_insert_event_is_idempotent(storage: SqliteStorage) -> None:
    storage.insert_event("ABC123", _asthma_event(), "2026-03-01T10:01:00Z")
    storage.insert_event("ABC123", _asthma_event(), "2026-03-01T10:01:00Z")
    assert len(storage.get_events("ABC123")) == 1


def test_get_events_filters_by_code(storage: SqliteStorage) -> None:
    storage.insert_event("USER1", _asthma_event(id="e1"), "2026-03-01T10:01:00Z")
    storage.insert_event("USER2", _asthma_event(id="e2"), "2026-03-01T10:01:00Z")
    assert len(storage.get_events("USER1")) == 1
    assert storage.get_events("USER1")[0]["id"] == "e1"


def test_preventive_true_is_returned_as_bool(storage: SqliteStorage) -> None:
    storage.insert_event("ABC123", _asthma_event(preventive=True), "2026-03-01T10:01:00Z")
    assert storage.get_events("ABC123")[0]["preventive"] is True


def test_preventive_false_is_returned_as_bool(storage: SqliteStorage) -> None:
    storage.insert_event("ABC123", _asthma_event(preventive=False), "2026-03-01T10:01:00Z")
    assert storage.get_events("ABC123")[0]["preventive"] is False


# --- ritalin events ---

def test_get_ritalin_events_returns_empty_for_unknown_code(storage: SqliteStorage) -> None:
    assert storage.get_ritalin_events("NOBODY") == []


def test_insert_ritalin_event_stores_all_fields(storage: SqliteStorage) -> None:
    storage.insert_ritalin_event("ABC123", _ritalin_event(), "2026-03-01T08:01:00Z")
    events = storage.get_ritalin_events("ABC123")
    assert len(events) == 1
    ev = events[0]
    assert ev["id"] == "ritalin-1"
    assert ev["date"] == "2026-03-01"
    assert ev["timestamp"] == "2026-03-01T08:00:00.000Z"
    assert ev["count"] == 1


def test_insert_ritalin_event_is_idempotent(storage: SqliteStorage) -> None:
    storage.insert_ritalin_event("ABC123", _ritalin_event(), "2026-03-01T08:01:00Z")
    storage.insert_ritalin_event("ABC123", _ritalin_event(), "2026-03-01T08:01:00Z")
    assert len(storage.get_ritalin_events("ABC123")) == 1


def test_get_ritalin_events_filters_by_code(storage: SqliteStorage) -> None:
    storage.insert_ritalin_event("USER1", _ritalin_event(id="r1"), "2026-03-01T08:01:00Z")
    storage.insert_ritalin_event("USER2", _ritalin_event(id="r2"), "2026-03-01T08:01:00Z")
    assert len(storage.get_ritalin_events("USER1")) == 1
    assert storage.get_ritalin_events("USER1")[0]["id"] == "r1"


# --- token queries ---

def test_validate_token_returns_false_when_no_codes(storage: SqliteStorage) -> None:
    assert storage.validate_token("tok") is False


def test_validate_token_returns_false_for_code_without_token(storage: SqliteStorage) -> None:
    storage.upsert_code(_code_entry())
    assert storage.validate_token("tok") is False


def test_validate_token_returns_true_for_valid_token(storage: SqliteStorage) -> None:
    storage.upsert_code(_code_entry(token="tok123"))
    assert storage.validate_token("tok123") is True


def test_validate_token_returns_false_for_wrong_token(storage: SqliteStorage) -> None:
    storage.upsert_code(_code_entry(token="tok123"))
    assert storage.validate_token("wrong") is False


def test_get_code_for_token_returns_none_when_not_found(storage: SqliteStorage) -> None:
    assert storage.get_code_for_token("tok") is None


def test_get_code_for_token_returns_correct_code(storage: SqliteStorage) -> None:
    storage.upsert_code(_code_entry(code="ABC123", token="tok123"))
    assert storage.get_code_for_token("tok123") == "ABC123"


def test_get_code_for_token_isolates_codes(storage: SqliteStorage) -> None:
    storage.upsert_code(_code_entry(code="USER1", token="tok-a"))
    storage.upsert_code(_code_entry(code="USER2", token="tok-b"))
    assert storage.get_code_for_token("tok-a") == "USER1"
    assert storage.get_code_for_token("tok-b") == "USER2"
