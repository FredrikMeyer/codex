"""
One-time migration from JSON storage to SQLite.

Reads the legacy storage.json and inserts all records into SQLite using
idempotent operations, then writes a sentinel file so the migration never
runs twice.
"""

import json
from pathlib import Path
from typing import Any, Dict

from .sqlite_storage import AsthmaMedicineEventData, CodeEntry, RitalinEventData, SqliteStorage


def migrate_json_to_sqlite(json_path: Path, storage: SqliteStorage) -> None:
    """
    Migrate all data from the JSON file into SQLite.

    - Skips if the JSON file does not exist (fresh install).
    - Skips if the sentinel file ``<json_path>.migrated`` already exists.
    - All inserts are idempotent: codes use UPSERT, events use INSERT OR IGNORE.
    - Writes the sentinel file on completion.
    """
    if not json_path.exists():
        return

    sentinel = json_path.with_suffix(".migrated")
    if sentinel.exists():
        return

    with json_path.open() as fp:
        data: Dict[str, Any] = json.load(fp)

    for code_entry in data.get("codes", []):
        storage.upsert_code(
            CodeEntry(
                code=code_entry["code"],
                created_at=code_entry["created_at"],
                last_login_at=code_entry.get("last_login_at"),
                token=code_entry.get("token"),
                token_generated_at=code_entry.get("token_generated_at"),
            )
        )

    for entry in data.get("events", []):
        code = entry["code"]
        event = entry["event"]
        received_at = entry["received_at"]
        storage.insert_event(code, AsthmaMedicineEventData(**event), received_at)

    for entry in data.get("ritalin_events", []):
        code = entry["code"]
        event = entry["event"]
        received_at = entry["received_at"]
        storage.insert_ritalin_event(code, RitalinEventData(**event), received_at)

    sentinel.write_text("")
