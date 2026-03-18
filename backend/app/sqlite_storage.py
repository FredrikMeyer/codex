"""
SQLite-backed storage for codes, asthma events, and ritalin events.

Provides thread-safe access to a single SQLite database file.
"""

import sqlite3
import threading
from pathlib import Path
from typing import NotRequired, TypedDict


class CodeEntry(TypedDict):
    code: str
    created_at: str
    last_login_at: NotRequired[str | None]
    token: NotRequired[str | None]
    token_generated_at: NotRequired[str | None]


class AsthmaMedicineEventData(TypedDict):
    """Input shape for inserting an asthma event."""

    id: str
    date: str
    timestamp: str
    type: str
    count: int
    preventive: NotRequired[bool]


class StoredAsthmaMedicineEvent(TypedDict):
    """Shape returned by get_events — all fields always present."""

    id: str
    date: str
    timestamp: str
    type: str
    count: int
    preventive: bool
    received_at: str


class RitalinEventData(TypedDict):
    """Input shape for inserting a ritalin event."""

    id: str
    date: str
    timestamp: str
    count: int


class StoredRitalinEvent(TypedDict):
    """Shape returned by get_ritalin_events — all fields always present."""

    id: str
    date: str
    timestamp: str
    count: int
    received_at: str


class SqliteStorage:
    """
    Thread-safe SQLite storage for all application data.

    All reads and writes are serialised with a single lock to prevent
    concurrent modification. Accepts a file path or ':memory:' for testing.
    """

    def __init__(self, path: Path | str) -> None:
        self._conn = sqlite3.connect(str(path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._lock = threading.Lock()
        self._init_schema()

    def _init_schema(self) -> None:
        with self._lock:
            self._conn.executescript("""
                PRAGMA journal_mode=WAL;

                CREATE TABLE IF NOT EXISTS codes (
                    code               TEXT PRIMARY KEY,
                    created_at         TEXT NOT NULL,
                    last_login_at      TEXT,
                    token              TEXT,
                    token_generated_at TEXT
                );

                CREATE TABLE IF NOT EXISTS asthma_events (
                    id          TEXT PRIMARY KEY,
                    code        TEXT NOT NULL,
                    date        TEXT NOT NULL,
                    timestamp   TEXT NOT NULL,
                    type        TEXT NOT NULL,
                    count       INTEGER NOT NULL,
                    preventive  INTEGER NOT NULL DEFAULT 0,
                    received_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS ritalin_events (
                    id          TEXT PRIMARY KEY,
                    code        TEXT NOT NULL,
                    date        TEXT NOT NULL,
                    timestamp   TEXT NOT NULL,
                    count       INTEGER NOT NULL,
                    received_at TEXT NOT NULL
                );
            """)

    def get_codes(self) -> list[CodeEntry]:
        """Return all code entries."""
        with self._lock:
            rows = self._conn.execute("SELECT * FROM codes").fetchall()
            return [
                CodeEntry(
                    code=row["code"],
                    created_at=row["created_at"],
                    last_login_at=row["last_login_at"],
                    token=row["token"],
                    token_generated_at=row["token_generated_at"],
                )
                for row in rows
            ]

    def upsert_code(self, entry: CodeEntry) -> None:
        """Insert or replace a code entry."""
        with self._lock:
            self._conn.execute(
                """
                INSERT OR REPLACE INTO codes
                    (code, created_at, last_login_at, token, token_generated_at)
                VALUES
                    (:code, :created_at, :last_login_at, :token, :token_generated_at)
                """,
                {
                    "code": entry["code"],
                    "created_at": entry["created_at"],
                    "last_login_at": entry.get("last_login_at"),
                    "token": entry.get("token"),
                    "token_generated_at": entry.get("token_generated_at"),
                },
            )
            self._conn.commit()

    def insert_event(self, code: str, event: AsthmaMedicineEventData, received_at: str) -> None:
        """Insert an asthma event, ignoring duplicates by id."""
        with self._lock:
            self._conn.execute(
                """
                INSERT OR IGNORE INTO asthma_events
                    (id, code, date, timestamp, type, count, preventive, received_at)
                VALUES
                    (:id, :code, :date, :timestamp, :type, :count, :preventive, :received_at)
                """,
                {
                    "id": event["id"],
                    "code": code,
                    "date": event["date"],
                    "timestamp": event["timestamp"],
                    "type": event["type"],
                    "count": event["count"],
                    "preventive": 1 if event.get("preventive") else 0,
                    "received_at": received_at,
                },
            )
            self._conn.commit()

    def get_events(self, code: str) -> list[StoredAsthmaMedicineEvent]:
        """Return all asthma events for a user."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM asthma_events WHERE code = ?", (code,)
            ).fetchall()
            return [
                StoredAsthmaMedicineEvent(
                    id=row["id"],
                    date=row["date"],
                    timestamp=row["timestamp"],
                    type=row["type"],
                    count=row["count"],
                    preventive=bool(row["preventive"]),
                    received_at=row["received_at"],
                )
                for row in rows
            ]

    def insert_ritalin_event(self, code: str, event: RitalinEventData, received_at: str) -> None:
        """Insert a ritalin event, ignoring duplicates by id."""
        with self._lock:
            self._conn.execute(
                """
                INSERT OR IGNORE INTO ritalin_events
                    (id, code, date, timestamp, count, received_at)
                VALUES
                    (:id, :code, :date, :timestamp, :count, :received_at)
                """,
                {
                    "id": event["id"],
                    "code": code,
                    "date": event["date"],
                    "timestamp": event["timestamp"],
                    "count": event["count"],
                    "received_at": received_at,
                },
            )
            self._conn.commit()

    def close(self) -> None:
        """Close the database connection."""
        self._conn.close()

    def get_ritalin_events(self, code: str) -> list[StoredRitalinEvent]:
        """Return all ritalin events for a user."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM ritalin_events WHERE code = ?", (code,)
            ).fetchall()
            return [
                StoredRitalinEvent(
                    id=row["id"],
                    date=row["date"],
                    timestamp=row["timestamp"],
                    count=row["count"],
                    received_at=row["received_at"],
                )
                for row in rows
            ]
