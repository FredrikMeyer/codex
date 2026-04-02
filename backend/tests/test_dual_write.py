"""
Tests that repositories dual-write to SQLite when a SqliteStorage is provided.

Each test uses a temporary JSON file and an in-memory SQLite database,
performing an operation via the repository and then asserting that
the same data is readable from SqliteStorage.
"""

from pathlib import Path

import pytest

from app.repository import CodeRepository, LogRepository
from app.sqlite_storage import SqliteStorage


@pytest.fixture()
def sqlite() -> SqliteStorage:
    return SqliteStorage(":memory:")


@pytest.fixture()
def code_repo(tmp_path: Path, sqlite: SqliteStorage) -> CodeRepository:
    return CodeRepository(tmp_path / "data.json", sqlite=sqlite)


@pytest.fixture()
def log_repo(tmp_path: Path, sqlite: SqliteStorage) -> LogRepository:
    return LogRepository(tmp_path / "data.json", sqlite=sqlite)


# --- CodeRepository dual-write ---

def test_create_code_writes_to_sqlite(code_repo: CodeRepository, sqlite: SqliteStorage) -> None:
    code_repo.create_code("ABC123")
    codes = sqlite.get_codes()
    assert len(codes) == 1
    assert codes[0]["code"] == "ABC123"


def test_record_login_writes_last_login_to_sqlite(code_repo: CodeRepository, sqlite: SqliteStorage) -> None:
    code_repo.create_code("ABC123")
    code_repo.record_login("ABC123")
    codes = sqlite.get_codes()
    assert codes[0]["last_login_at"] is not None


def test_generate_token_writes_token_to_sqlite(code_repo: CodeRepository, sqlite: SqliteStorage) -> None:
    code_repo.create_code("ABC123")
    token = code_repo.generate_token("ABC123")
    assert token is not None
    assert sqlite.validate_token(token)


def test_generate_token_idempotent_still_syncs_to_sqlite(code_repo: CodeRepository, sqlite: SqliteStorage) -> None:
    """Second call to generate_token (token already exists) still upserts to SQLite."""
    code_repo.create_code("ABC123")
    token1 = code_repo.generate_token("ABC123")
    token2 = code_repo.generate_token("ABC123")
    assert token1 == token2
    assert token1 is not None
    assert sqlite.validate_token(token1)


# --- LogRepository dual-write ---

def _asthma_event(id: str = "evt-1") -> dict:
    return {
        "id": id,
        "date": "2026-04-01",
        "timestamp": "2026-04-01T10:00:00.000Z",
        "type": "spray",
        "count": 2,
        "preventive": False,
    }


def _ritalin_event(id: str = "rit-1") -> dict:
    return {
        "id": id,
        "date": "2026-04-01",
        "timestamp": "2026-04-01T08:00:00.000Z",
        "count": 1,
    }


def test_save_event_writes_to_sqlite(log_repo: LogRepository, sqlite: SqliteStorage) -> None:
    log_repo.save_event("ABC123", _asthma_event())
    events = sqlite.get_events("ABC123")
    assert len(events) == 1
    assert events[0]["id"] == "evt-1"


def test_save_event_duplicate_not_written_to_sqlite(log_repo: LogRepository, sqlite: SqliteStorage) -> None:
    log_repo.save_event("ABC123", _asthma_event())
    log_repo.save_event("ABC123", _asthma_event())
    assert len(sqlite.get_events("ABC123")) == 1


def test_save_events_batch_writes_to_sqlite(log_repo: LogRepository, sqlite: SqliteStorage) -> None:
    events = [_asthma_event("e1"), _asthma_event("e2")]
    log_repo.save_events_batch("ABC123", events)
    assert len(sqlite.get_events("ABC123")) == 2


def test_save_events_batch_skips_duplicates_in_sqlite(log_repo: LogRepository, sqlite: SqliteStorage) -> None:
    log_repo.save_events_batch("ABC123", [_asthma_event("e1")])
    log_repo.save_events_batch("ABC123", [_asthma_event("e1"), _asthma_event("e2")])
    assert len(sqlite.get_events("ABC123")) == 2


def test_save_ritalin_event_writes_to_sqlite(log_repo: LogRepository, sqlite: SqliteStorage) -> None:
    log_repo.save_ritalin_event("ABC123", _ritalin_event())
    events = sqlite.get_ritalin_events("ABC123")
    assert len(events) == 1
    assert events[0]["id"] == "rit-1"


def test_save_ritalin_event_duplicate_not_written_to_sqlite(log_repo: LogRepository, sqlite: SqliteStorage) -> None:
    log_repo.save_ritalin_event("ABC123", _ritalin_event())
    log_repo.save_ritalin_event("ABC123", _ritalin_event())
    assert len(sqlite.get_ritalin_events("ABC123")) == 1


def test_save_ritalin_events_batch_writes_to_sqlite(log_repo: LogRepository, sqlite: SqliteStorage) -> None:
    log_repo.save_ritalin_events_batch("ABC123", [_ritalin_event("r1"), _ritalin_event("r2")])
    assert len(sqlite.get_ritalin_events("ABC123")) == 2
