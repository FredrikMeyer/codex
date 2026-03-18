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


def _code_entry(**overrides: object) -> CodeEntry:
    base: CodeEntry = {"code": "ABC123", "created_at": "2026-01-01T00:00:00Z"}
    return {**base, **overrides}  # type: ignore[return-value]


def _asthma_event(**overrides: object) -> AsthmaMedicineEventData:
    base: AsthmaMedicineEventData = {
        "id": "event-1",
        "date": "2026-03-01",
        "timestamp": "2026-03-01T10:00:00.000Z",
        "type": "spray",
        "count": 2,
        "preventive": False,
    }
    return {**base, **overrides}  # type: ignore[return-value]


def _ritalin_event(**overrides: object) -> RitalinEventData:
    base: RitalinEventData = {
        "id": "ritalin-1",
        "date": "2026-03-01",
        "timestamp": "2026-03-01T08:00:00.000Z",
        "count": 1,
    }
    return {**base, **overrides}  # type: ignore[return-value]


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
