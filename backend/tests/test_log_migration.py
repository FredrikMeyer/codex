"""
Tests for the one-time migration that converts old log entries to events.

Old format: data["logs"] contains entries with {code, log: {date, spray, ventoline}, received_at}
New format: data["events"] contains entries with {code, event: {id, date, timestamp, type, count, preventive}, received_at}
"""

from pathlib import Path

import pytest

from app.repository import LogRepository
from app.storage import save_data


def _seed_logs(data_file: Path, log_entries: list) -> None:
    save_data(data_file, {"logs": log_entries, "events": [], "codes": []})


def _log_entry(code: str, date: str, spray: int = 0, ventoline: int = 0) -> dict:
    return {
        "code": code,
        "log": {"date": date, "spray": spray, "ventoline": ventoline},
        "received_at": f"{date}T10:00:00Z",
    }


def test_spray_log_is_converted_to_spray_event(tmp_path: Path):
    """A log with spray > 0 produces a spray event."""
    data_file = tmp_path / "data.json"
    _seed_logs(data_file, [_log_entry("CODE1", "2026-01-15", spray=3)])

    LogRepository(data_file).migrate_logs_to_events()

    events = LogRepository(data_file).get_events("CODE1")
    assert len(events) == 1
    assert events[0]["type"] == "spray"
    assert events[0]["count"] == 3
    assert events[0]["date"] == "2026-01-15"
    assert events[0]["preventive"] is False


def test_ventoline_log_is_converted_to_ventoline_event(tmp_path: Path):
    """A log with ventoline > 0 produces a ventoline event."""
    data_file = tmp_path / "data.json"
    _seed_logs(data_file, [_log_entry("CODE1", "2026-01-15", ventoline=2)])

    LogRepository(data_file).migrate_logs_to_events()

    events = LogRepository(data_file).get_events("CODE1")
    assert len(events) == 1
    assert events[0]["type"] == "ventoline"
    assert events[0]["count"] == 2


def test_log_with_both_types_produces_two_events(tmp_path: Path):
    """A log with both spray and ventoline > 0 produces two separate events."""
    data_file = tmp_path / "data.json"
    _seed_logs(data_file, [_log_entry("CODE1", "2026-01-15", spray=1, ventoline=2)])

    LogRepository(data_file).migrate_logs_to_events()

    events = LogRepository(data_file).get_events("CODE1")
    assert len(events) == 2
    types = {e["type"] for e in events}
    assert types == {"spray", "ventoline"}


def test_migrated_timestamp_defaults_to_midnight(tmp_path: Path):
    """Migrated events use midnight UTC as the timestamp."""
    data_file = tmp_path / "data.json"
    _seed_logs(data_file, [_log_entry("CODE1", "2026-01-15", ventoline=1)])

    LogRepository(data_file).migrate_logs_to_events()

    events = LogRepository(data_file).get_events("CODE1")
    assert events[0]["timestamp"] == "2026-01-15T12:00:00.000Z"


def test_migration_is_idempotent(tmp_path: Path):
    """Running the migration twice does not duplicate events."""
    data_file = tmp_path / "data.json"
    _seed_logs(data_file, [_log_entry("CODE1", "2026-01-15", spray=2, ventoline=1)])

    repo = LogRepository(data_file)
    repo.migrate_logs_to_events()
    repo.migrate_logs_to_events()

    events = LogRepository(data_file).get_events("CODE1")
    assert len(events) == 2


def test_migration_produces_stable_event_ids(tmp_path: Path):
    """Running the migration twice yields events with the same IDs."""
    data_file = tmp_path / "data.json"
    _seed_logs(data_file, [_log_entry("CODE1", "2026-01-15", ventoline=3)])

    repo = LogRepository(data_file)
    repo.migrate_logs_to_events()
    ids_first = {e["id"] for e in repo.get_events("CODE1")}

    repo.migrate_logs_to_events()
    ids_second = {e["id"] for e in repo.get_events("CODE1")}

    assert ids_first == ids_second


def test_zero_count_types_are_skipped(tmp_path: Path):
    """Medicine types with count 0 are not turned into events."""
    data_file = tmp_path / "data.json"
    _seed_logs(data_file, [_log_entry("CODE1", "2026-01-15", spray=0, ventoline=2)])

    LogRepository(data_file).migrate_logs_to_events()

    events = LogRepository(data_file).get_events("CODE1")
    assert len(events) == 1
    assert events[0]["type"] == "ventoline"


def test_migration_only_affects_target_user(tmp_path: Path):
    """Migration creates events scoped to the correct user code."""
    data_file = tmp_path / "data.json"
    _seed_logs(data_file, [
        _log_entry("CODE1", "2026-01-15", ventoline=1),
        _log_entry("CODE2", "2026-01-15", spray=2),
    ])

    LogRepository(data_file).migrate_logs_to_events()

    assert len(LogRepository(data_file).get_events("CODE1")) == 1
    assert len(LogRepository(data_file).get_events("CODE2")) == 1
    assert LogRepository(data_file).get_events("CODE1")[0]["type"] == "ventoline"
    assert LogRepository(data_file).get_events("CODE2")[0]["type"] == "spray"


def test_existing_events_are_not_duplicated_by_migration(tmp_path: Path):
    """If an event with the same stable ID already exists, migration skips it."""
    data_file = tmp_path / "data.json"
    _seed_logs(data_file, [_log_entry("CODE1", "2026-01-15", ventoline=1)])

    repo = LogRepository(data_file)
    repo.migrate_logs_to_events()
    existing_ids = {e["id"] for e in repo.get_events("CODE1")}

    # Run again — should not add a second event
    repo.migrate_logs_to_events()
    after_ids = {e["id"] for e in repo.get_events("CODE1")}

    assert existing_ids == after_ids
    assert len(repo.get_events("CODE1")) == 1


def test_empty_logs_produces_no_events(tmp_path: Path):
    """Migration with no log entries is a no-op."""
    data_file = tmp_path / "data.json"
    _seed_logs(data_file, [])

    LogRepository(data_file).migrate_logs_to_events()

    assert LogRepository(data_file).get_events("CODE1") == []
