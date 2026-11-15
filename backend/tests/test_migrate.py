"""
Tests for migrate_json_to_sqlite.

Each test uses an in-memory SQLite instance and a temporary JSON file
so there is no shared state between tests.
"""

import json
from pathlib import Path

import pytest

from app.cleanup_tokens import cleanup_plaintext_tokens
from app.main import create_app
from app.migrate import migrate_json_to_sqlite
from app.sqlite_storage import SqliteStorage


@pytest.fixture()
def storage():
    s = SqliteStorage(":memory:")
    yield s
    s.close()


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data))


def test_cleanup_preserves_existing_sessions_across_restart(tmp_path: Path) -> None:
    json_path = tmp_path / "storage.json"
    db_path = tmp_path / "data.db"
    write_json(json_path, {"codes": [{"code": "ABC123", "created_at": "2024-01-01", "token": "old-secret"}]})
    app = create_app(json_path, db_path)
    with app.test_client() as client:
        fresh = client.post("/generate-token", json={"code": "ABC123"}).get_json()["token"]
    storage = SqliteStorage(db_path)
    cleanup_plaintext_tokens(json_path, storage)
    cleanup_plaintext_tokens(json_path, storage)
    assert "token" not in json.loads(json_path.read_text())["codes"][0]
    assert storage.get_codes()[0]["token"] is None
    storage.close()
    app = create_app(json_path, db_path)
    with app.test_client() as client:
        for token in ("old-secret", fresh):
            assert client.get("/code", headers={"Authorization": f"Bearer {token}"}).get_json()["code"] == "ABC123"
        assert client.post("/login", json={"code": "ABC123"}).status_code == 200
    assert "token" not in json.loads(json_path.read_text())["codes"][0]


def test_cleanup_fails_without_modifying_files_if_hash_missing(tmp_path: Path, storage: SqliteStorage) -> None:
    json_path = tmp_path / "storage.json"
    write_json(json_path, {"codes": [{"code": "ABC123", "created_at": "2024-01-01", "token": "secret"}]})
    storage.upsert_code({"code": "ABC123", "created_at": "2024-01-01", "token": "secret"})
    original = json_path.read_bytes()
    with pytest.raises(ValueError, match="no matching account digest"):
        cleanup_plaintext_tokens(json_path, storage)
    assert json_path.read_bytes() == original
    assert storage.get_codes()[0]["token"] == "secret"


def test_cleanup_can_resume_after_interruption(tmp_path: Path, storage: SqliteStorage, monkeypatch: pytest.MonkeyPatch) -> None:
    json_path = tmp_path / "storage.json"
    write_json(json_path, {"codes": [{"code": "ABC123", "created_at": "2024-01-01", "token": "secret"}]})
    storage.upsert_code({"code": "ABC123", "created_at": "2024-01-01", "token": "secret"})
    storage.migrate_legacy_tokens([])
    original = storage.remove_legacy_plaintext_tokens

    def interrupted() -> None:
        raise OSError("simulated interruption")

    monkeypatch.setattr(storage, "remove_legacy_plaintext_tokens", interrupted)
    with pytest.raises(OSError, match="simulated interruption"):
        cleanup_plaintext_tokens(json_path, storage)
    assert storage.get_code_for_hashed_token("secret") == "ABC123"
    monkeypatch.setattr(storage, "remove_legacy_plaintext_tokens", original)
    cleanup_plaintext_tokens(json_path, storage)
    assert storage.get_codes()[0]["token"] is None


# --- no-op cases ---

def test_skips_when_json_file_missing(tmp_path: Path, storage: SqliteStorage) -> None:
    migrate_json_to_sqlite(tmp_path / "missing.json", storage)
    assert storage.get_codes() == []


def test_skips_when_sentinel_exists(tmp_path: Path, storage: SqliteStorage) -> None:
    json_path = tmp_path / "storage.json"
    write_json(json_path, {"codes": [{"code": "ABC123", "created_at": "2024-01-01T00:00:00+00:00"}]})
    sentinel = json_path.with_suffix(".migrated")
    sentinel.write_text("")

    migrate_json_to_sqlite(json_path, storage)

    assert storage.get_codes() == []


# --- codes migration ---

def test_migrates_codes(tmp_path: Path, storage: SqliteStorage) -> None:
    json_path = tmp_path / "storage.json"
    write_json(json_path, {
        "codes": [
            {"code": "ABC123", "created_at": "2024-01-01T00:00:00+00:00", "token": "tok1", "token_generated_at": "2024-01-02T00:00:00+00:00"},
        ]
    })

    migrate_json_to_sqlite(json_path, storage)

    codes = storage.get_codes()
    assert len(codes) == 1
    assert codes[0]["code"] == "ABC123"
    assert codes[0].get("token") == "tok1"


def test_migrates_codes_without_optional_fields(tmp_path: Path, storage: SqliteStorage) -> None:
    json_path = tmp_path / "storage.json"
    write_json(json_path, {
        "codes": [{"code": "XYZ999", "created_at": "2024-03-01T00:00:00+00:00"}]
    })

    migrate_json_to_sqlite(json_path, storage)

    codes = storage.get_codes()
    assert len(codes) == 1
    assert codes[0]["code"] == "XYZ999"
    assert codes[0].get("token") is None


# --- asthma events migration ---

def test_migrates_asthma_events(tmp_path: Path, storage: SqliteStorage) -> None:
    json_path = tmp_path / "storage.json"
    write_json(json_path, {
        "codes": [{"code": "ABC123", "created_at": "2024-01-01T00:00:00+00:00"}],
        "events": [
            {
                "code": "ABC123",
                "event": {
                    "id": "evt-1",
                    "date": "2024-01-15",
                    "timestamp": "2024-01-15T08:00:00+00:00",
                    "type": "spray",
                    "count": 2,
                    "preventive": False,
                },
                "received_at": "2024-01-15T08:01:00+00:00",
            }
        ],
    })

    migrate_json_to_sqlite(json_path, storage)

    events = storage.get_events("ABC123")
    assert len(events) == 1
    assert events[0]["id"] == "evt-1"
    assert events[0]["type"] == "spray"
    assert events[0]["count"] == 2
    assert events[0]["preventive"] is False


# --- ritalin events migration ---

def test_migrates_ritalin_events(tmp_path: Path, storage: SqliteStorage) -> None:
    json_path = tmp_path / "storage.json"
    write_json(json_path, {
        "ritalin_events": [
            {
                "code": "ABC123",
                "event": {
                    "id": "ritalin-1",
                    "date": "2024-02-10",
                    "timestamp": "2024-02-10T09:00:00+00:00",
                    "count": 1,
                },
                "received_at": "2024-02-10T09:01:00+00:00",
            }
        ],
    })

    migrate_json_to_sqlite(json_path, storage)

    events = storage.get_ritalin_events("ABC123")
    assert len(events) == 1
    assert events[0]["id"] == "ritalin-1"
    assert events[0]["count"] == 1


# --- sentinel ---

def test_writes_sentinel_after_migration(tmp_path: Path, storage: SqliteStorage) -> None:
    json_path = tmp_path / "storage.json"
    write_json(json_path, {})

    migrate_json_to_sqlite(json_path, storage)

    sentinel = json_path.with_suffix(".migrated")
    assert sentinel.exists()


def test_migration_is_idempotent(tmp_path: Path, storage: SqliteStorage) -> None:
    json_path = tmp_path / "storage.json"
    write_json(json_path, {
        "codes": [{"code": "ABC123", "created_at": "2024-01-01T00:00:00+00:00"}],
        "events": [
            {
                "code": "ABC123",
                "event": {
                    "id": "evt-1",
                    "date": "2024-01-15",
                    "timestamp": "2024-01-15T08:00:00+00:00",
                    "type": "spray",
                    "count": 2,
                    "preventive": False,
                },
                "received_at": "2024-01-15T08:01:00+00:00",
            }
        ],
    })

    # Delete sentinel manually after first run to simulate re-running without sentinel
    migrate_json_to_sqlite(json_path, storage)
    sentinel = json_path.with_suffix(".migrated")
    sentinel.unlink()

    migrate_json_to_sqlite(json_path, storage)

    assert len(storage.get_events("ABC123")) == 1
