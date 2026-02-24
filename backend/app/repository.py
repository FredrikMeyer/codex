"""
Repository layer for log and code storage.

Provides framework-independent data access, hiding storage implementation details.
"""

import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from .storage import load_data, save_data


class LogRepository:
    """
    Repository for managing log entries and authentication codes.

    Hides the storage implementation (currently all logs in one file,
    filtered by code) and provides a clean interface for data access.
    """

    def __init__(self, data_file: Path):
        self.data_file = data_file
        self._lock = threading.Lock()

    def save_log(self, code: str, log_data: Dict[str, Any]) -> None:
        """
        Save a log entry for a specific user (identified by code).

        Args:
            code: User's authentication code
            log_data: The log entry data (date, spray, ventoline counts)
        """
        with self._lock:
            data = load_data(self.data_file)
            log_entry = {
                "code": code,
                "log": log_data,
                "received_at": datetime.now(timezone.utc).isoformat(),
            }
            data["logs"].append(log_entry)
            save_data(self.data_file, data)

    def get_logs_for_code(self, code: str) -> List[Dict[str, Any]]:
        """
        Retrieve all log entries for a specific user.

        Args:
            code: User's authentication code

        Returns:
            List of log entries for this user
        """
        with self._lock:
            data = load_data(self.data_file)
            return [
                entry["log"]
                for entry in data.get("logs", [])
                if entry.get("code") == code
            ]

    def get_logs_with_metadata(self, code: str) -> List[Dict[str, Any]]:
        """
        Retrieve all log entries with metadata for a specific user.

        Args:
            code: User's authentication code

        Returns:
            List of entries with 'date', 'spray', 'ventoline', and 'received_at' fields
        """
        with self._lock:
            data = load_data(self.data_file)
            return [
                {
                    "date": entry["log"]["date"],
                    "spray": entry["log"].get("spray", 0),
                    "ventoline": entry["log"].get("ventoline", 0),
                    "received_at": entry["received_at"],
                }
                for entry in data.get("logs", [])
                if entry.get("code") == code
            ]

    def save_event(self, code: str, event_data: Dict[str, Any]) -> None:
        """
        Save a usage event for a user, skipping if the same id already exists.

        Args:
            code: User's authentication code
            event_data: The event data (id, date, timestamp, type, count, preventive)
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
            data.setdefault("events", []).append({
                "code": code,
                "event": event_data,
                "received_at": datetime.now(timezone.utc).isoformat(),
            })
            save_data(self.data_file, data)

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
