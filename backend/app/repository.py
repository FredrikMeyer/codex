"""
Repository layer for log and code storage.

Provides framework-independent data access, hiding storage implementation details.
"""

import threading
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
