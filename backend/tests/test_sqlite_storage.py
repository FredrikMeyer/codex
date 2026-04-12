"""
Tests for SqliteStorage.

All tests use an in-memory database for speed and isolation.
"""

from collections.abc import Generator

import pytest

from app.sqlite_storage import AsthmaMedicineEventData, CodeEntry, RitalinEventData, SqliteStorage


@pytest.fixture()
def storage() -> Generator[SqliteStorage, None, None]:
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
