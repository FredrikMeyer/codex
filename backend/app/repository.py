"""
Repository layer for log and code storage.

Provides framework-independent data access, hiding storage implementation details.
"""

import secrets
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, cast

from .sqlite_storage import AsthmaMedicineEventData, CodeEntry, RitalinEventData, SqliteStorage
from .storage import load_data, save_data


def _to_code_entry(entry: Dict[str, Any]) -> CodeEntry:
    result: CodeEntry = {
        "code": entry["code"],
        "created_at": entry["created_at"],
    }
    if "last_login_at" in entry:
        result["last_login_at"] = entry["last_login_at"]
    if "token" in entry:
        result["token"] = entry["token"]
    if "token_generated_at" in entry:
        result["token_generated_at"] = entry["token_generated_at"]
    return result


class CodeRepository:
    """
    Repository for managing authentication codes and tokens.

    Hides the storage implementation and provides a clean interface
    for code and token lifecycle operations.
    """

    def __init__(self, data_file: Path, sqlite: SqliteStorage | None = None) -> None:
        self.data_file = data_file
        self._lock = threading.Lock()
        self._sqlite = sqlite

    def create_code(self, code: str) -> None:
        """Store a new authentication code."""
        with self._lock:
            created_at = datetime.now(timezone.utc).isoformat()
            data = load_data(self.data_file)
            data.setdefault("codes", []).append({"code": code, "created_at": created_at})
            save_data(self.data_file, data)
            if self._sqlite:
                self._sqlite.upsert_code(CodeEntry(code=code, created_at=created_at))

    def record_login(self, code: str) -> bool:
        """
        Record a login attempt for a code.

        Returns:
            True if the code exists and login was recorded, False if not found.
        """
        with self._lock:
            data = load_data(self.data_file)
            for entry in data.get("codes", []):
                if entry["code"] == code:
                    entry["last_login_at"] = datetime.now(timezone.utc).isoformat()
                    save_data(self.data_file, data)
                    if self._sqlite:
                        self._sqlite.upsert_code(_to_code_entry(entry))
                    return True
            return False

    def generate_token(self, code: str) -> str | None:
        """
        Return the token for a code, generating one if it does not exist yet.

        Returns:
            The token string, or None if the code does not exist.
        """
        with self._lock:
            data = load_data(self.data_file)
            for entry in data.get("codes", []):
                if entry["code"] == code:
                    if "token" not in entry:
                        entry["token"] = secrets.token_hex(32)
                        entry["token_generated_at"] = datetime.now(timezone.utc).isoformat()
                        save_data(self.data_file, data)
                    if self._sqlite:
                        self._sqlite.upsert_code(_to_code_entry(entry))
                    return entry["token"]
            return None

    def get_code_for_token(self, token: str) -> str | None:
        """
        Return the code associated with a token.

        Returns:
            The code string, or None if the token is not recognised.
        """
        with self._lock:
            data = load_data(self.data_file)
            for entry in data.get("codes", []):
                if entry.get("token") == token:
                    return entry["code"]
            return None

    def validate_token(self, token: str) -> bool:
        """Return True if the token is valid, False otherwise."""
        with self._lock:
            data = load_data(self.data_file)
            return any(
                entry.get("token") == token
                for entry in data.get("codes", [])
                if "token" in entry
            )


class LogRepository:
    """
    Repository for managing log entries and authentication codes.

    Hides the storage implementation (currently all logs in one file,
    filtered by code) and provides a clean interface for data access.
    """

    def __init__(self, data_file: Path, sqlite: SqliteStorage | None = None):
        self.data_file = data_file
        self._lock = threading.Lock()
        self._sqlite = sqlite

    def save_events_batch(self, code: str, events: List[Dict[str, Any]]) -> int:
        """
        Save multiple usage events in one operation, skipping any with IDs that already exist.

        Returns the number of new events saved.
        """
        with self._lock:
            data = load_data(self.data_file)
            existing_ids = {
                entry["event"].get("id")
                for entry in data.get("events", [])
                if entry.get("code") == code
            }
            received_at = datetime.now(timezone.utc).isoformat()
            new_entries = [
                {"code": code, "event": event_data, "received_at": received_at}
                for event_data in events
                if event_data.get("id") not in existing_ids
            ]
            if new_entries:
                data.setdefault("events", []).extend(new_entries)
                save_data(self.data_file, data)
                if self._sqlite:
                    for entry in new_entries:
                        self._sqlite.insert_event(code, cast(AsthmaMedicineEventData, entry["event"]), received_at)
            return len(new_entries)

    def save_event(self, code: str, event_data: Dict[str, Any]) -> None:
        """
        Save a usage event for a user, skipping if the same id already exists.
        """
        with self._lock:
            data = load_data(self.data_file)
            event_id = event_data.get("id")
            if event_id:
                existing_ids = {
                    entry["event"].get("id")
                    for entry in data.get("events", [])
                    if entry.get("code") == code
                }
                if event_id in existing_ids:
                    return
            received_at = datetime.now(timezone.utc).isoformat()
            data.setdefault("events", []).append({
                "code": code,
                "event": event_data,
                "received_at": received_at,
            })
            save_data(self.data_file, data)
            if self._sqlite:
                self._sqlite.insert_event(code, cast(AsthmaMedicineEventData, event_data), received_at)

    def get_events(self, code: str) -> List[Dict[str, Any]]:
        """
        Retrieve all usage events for a user.

        Args:
            code: User's authentication code

        Returns:
            List of events with id, date, timestamp, type, count, preventive, received_at
        """
        with self._lock:
            data = load_data(self.data_file)
            return [
                {
                    "id": entry["event"]["id"],
                    "date": entry["event"]["date"],
                    "timestamp": entry["event"]["timestamp"],
                    "type": entry["event"]["type"],
                    "count": entry["event"]["count"],
                    "preventive": entry["event"].get("preventive", False),
                    "received_at": entry["received_at"],
                }
                for entry in data.get("events", [])
                if entry.get("code") == code
            ]

    # Stable namespace for deterministic migration event IDs.
    _MIGRATION_NS = uuid.UUID("a1b2c3d4-e5f6-7890-abcd-ef1234567890")

    def migrate_logs_to_events(self) -> None:
        """
        One-time migration: convert old log entries in data["logs"] to events in data["events"].

        Each log entry with spray > 0 or ventoline > 0 becomes a separate event.
        Event IDs are derived deterministically from (code, date, type) so the
        migration is safe to run multiple times without creating duplicates.
        Timestamps default to midnight UTC for the event date.
        """
        if not self.data_file.exists():
            return

        with self._lock:
            data = load_data(self.data_file)
            logs = data.get("logs", [])
            if not logs:
                return

            existing_event_ids = {
                entry["event"].get("id")
                for entry in data.get("events", [])
            }

            new_entries: List[Dict[str, Any]] = []
            for log_entry in logs:
                code = log_entry.get("code", "")
                log = log_entry.get("log", {})
                date = log.get("date", "")
                received_at = log_entry.get("received_at", datetime.now(timezone.utc).isoformat())

                for medicine_type in ("spray", "ventoline"):
                    count = log.get(medicine_type) or 0
                    if count <= 0:
                        continue
                    event_id = str(uuid.uuid5(self._MIGRATION_NS, f"{code}:{date}:{medicine_type}"))
                    if event_id in existing_event_ids:
                        continue
                    new_entries.append({
                        "code": code,
                        "event": {
                            "id": event_id,
                            "date": date,
                            "timestamp": f"{date}T12:00:00.000Z",
                            "type": medicine_type,
                            "count": count,
                            "preventive": False,
                        },
                        "received_at": received_at,
                    })
                    existing_event_ids.add(event_id)

            if new_entries:
                data.setdefault("events", []).extend(new_entries)
                save_data(self.data_file, data)

    def save_ritalin_events_batch(self, code: str, events: List[Dict[str, Any]]) -> int:
        """
        Save multiple Ritalin dose events in one operation, skipping any with IDs that already exist.

        Returns the number of new events saved.
        """
        with self._lock:
            data = load_data(self.data_file)
            existing_ids = {
                entry["event"].get("id")
                for entry in data.get("ritalin_events", [])
                if entry.get("code") == code
            }
            received_at = datetime.now(timezone.utc).isoformat()
            new_entries = [
                {"code": code, "event": event_data, "received_at": received_at}
                for event_data in events
                if event_data.get("id") not in existing_ids
            ]
            if new_entries:
                data.setdefault("ritalin_events", []).extend(new_entries)
                save_data(self.data_file, data)
                if self._sqlite:
                    for entry in new_entries:
                        self._sqlite.insert_ritalin_event(code, cast(RitalinEventData, entry["event"]), received_at)
            return len(new_entries)

    def save_ritalin_event(self, code: str, event_data: Dict[str, Any]) -> None:
        """
        Save a Ritalin dose event for a user, skipping if the same id already exists.
        """
        with self._lock:
            data = load_data(self.data_file)
            event_id = event_data.get("id")
            if event_id:
                existing_ids = {
                    entry["event"].get("id")
                    for entry in data.get("ritalin_events", [])
                    if entry.get("code") == code
                }
                if event_id in existing_ids:
                    return
            received_at = datetime.now(timezone.utc).isoformat()
            data.setdefault("ritalin_events", []).append({
                "code": code,
                "event": event_data,
                "received_at": received_at,
            })
            save_data(self.data_file, data)
            if self._sqlite:
                self._sqlite.insert_ritalin_event(code, cast(RitalinEventData, event_data), received_at)

    def get_ritalin_events(self, code: str) -> List[Dict[str, Any]]:
        """
        Retrieve all Ritalin dose events for a user.

        Args:
            code: User's authentication code

        Returns:
            List of events with id, date, timestamp, count, received_at
        """
        with self._lock:
            data = load_data(self.data_file)
            return [
                {
                    "id": entry["event"]["id"],
                    "date": entry["event"]["date"],
                    "timestamp": entry["event"]["timestamp"],
                    "count": entry["event"]["count"],
                    "received_at": entry["received_at"],
                }
                for entry in data.get("ritalin_events", [])
                if entry.get("code") == code
            ]

    def code_exists(self, code: str) -> bool:
        """
        Check if a code exists in the system.

        Args:
            code: Authentication code to check

        Returns:
            True if code exists, False otherwise
        """
        with self._lock:
            data = load_data(self.data_file)
            return any(entry["code"] == code for entry in data.get("codes", []))
