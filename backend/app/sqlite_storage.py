"""
SQLite-backed storage for codes, asthma events, and ritalin events.

Provides thread-safe access to a single SQLite database file.
"""

import hashlib
import json
import secrets
import sqlite3
import threading
import time
from pathlib import Path
from typing import Literal, NotRequired, TypedDict


class CodeEntry(TypedDict):
    code: str
    created_at: str
    last_login_at: NotRequired[str | None]
    token: NotRequired[str | None]
    token_generated_at: NotRequired[str | None]


class PasskeyCredential(TypedDict):
    credential_id: bytes
    code: str
    public_key: bytes
    sign_count: int
    created_at: str
    device_type: NotRequired[str | None]
    backed_up: NotRequired[bool | None]
    transports: NotRequired[list[str] | None]


def _passkey_credential_from_row(row: sqlite3.Row) -> PasskeyCredential:
    credential = PasskeyCredential(
        credential_id=row["credential_id"], code=row["code"], public_key=row["public_key"],
        sign_count=row["sign_count"], created_at=row["created_at"],
    )
    if row["device_type"] is not None:
        credential["device_type"] = row["device_type"]
    if row["backed_up"] is not None:
        credential["backed_up"] = bool(row["backed_up"])
    if row["transports"] is not None:
        credential["transports"] = json.loads(row["transports"])
    return credential


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

                CREATE TABLE IF NOT EXISTS auth_tokens (
                    token_hash TEXT PRIMARY KEY,
                    code TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_auth_tokens_code ON auth_tokens(code);

                CREATE TABLE IF NOT EXISTS passkey_accounts (
                    code TEXT PRIMARY KEY,
                    user_handle BLOB NOT NULL UNIQUE
                );

                CREATE TABLE IF NOT EXISTS passkey_credentials (
                    credential_id BLOB PRIMARY KEY,
                    code TEXT NOT NULL,
                    public_key BLOB NOT NULL,
                    sign_count INTEGER NOT NULL CHECK(sign_count >= 0),
                    created_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_passkey_credentials_code ON passkey_credentials(code);

                CREATE TABLE IF NOT EXISTS passkey_challenges (
                    challenge_id TEXT PRIMARY KEY,
                    challenge BLOB NOT NULL,
                    ceremony TEXT NOT NULL CHECK(ceremony IN ('registration', 'authentication')),
                    code TEXT,
                    expires_at INTEGER NOT NULL,
                    CHECK((ceremony = 'registration' AND code IS NOT NULL) OR
                          (ceremony = 'authentication' AND code IS NULL))
                );

                CREATE INDEX IF NOT EXISTS idx_passkey_challenges_expiry ON passkey_challenges(expires_at);

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
            # Serialize schema upgrades across application workers.
            with self._conn:
                self._conn.execute("BEGIN IMMEDIATE")
                columns = {row["name"] for row in self._conn.execute("PRAGMA table_info(passkey_credentials)")}
                for name, sql_type in (("device_type", "TEXT"), ("backed_up", "INTEGER"), ("transports", "TEXT")):
                    if name not in columns:
                        self._conn.execute(f"ALTER TABLE passkey_credentials ADD COLUMN {name} {sql_type}")

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

    def get_or_create_passkey_user_handle(self, code: str) -> bytes:
        """Return a stable opaque handle for an existing account across workers."""
        with self._lock, self._conn:
            self._conn.execute("BEGIN IMMEDIATE")
            if not self._conn.execute("SELECT 1 FROM codes WHERE code = ?", (code,)).fetchone():
                raise ValueError("Unknown code")
            row = self._conn.execute(
                "SELECT user_handle FROM passkey_accounts WHERE code = ?", (code,)
            ).fetchone()
            if row:
                return bytes(row["user_handle"])
            handle = secrets.token_bytes(32)
            self._conn.execute(
                "INSERT INTO passkey_accounts (code, user_handle) VALUES (?, ?)",
                (code, handle),
            )
            return handle

    def create_passkey_challenge(
        self, ceremony: Literal["registration", "authentication"], code: str | None = None,
    ) -> tuple[str, bytes]:
        """Create a five-minute challenge, binding registration to an account."""
        if (ceremony == "registration" and not code) or (ceremony == "authentication" and code is not None):
            raise ValueError("Invalid challenge account binding")
        if ceremony not in ("registration", "authentication"):
            raise ValueError("Invalid ceremony")
        challenge_id = secrets.token_urlsafe(32)
        challenge = secrets.token_bytes(32)
        with self._lock, self._conn:
            self._conn.execute("BEGIN IMMEDIATE")
            now = int(time.time())
            if code and not self._conn.execute("SELECT 1 FROM codes WHERE code = ?", (code,)).fetchone():
                raise ValueError("Unknown code")
            self._conn.execute("DELETE FROM passkey_challenges WHERE expires_at <= ?", (now,))
            self._conn.execute(
                "INSERT INTO passkey_challenges VALUES (?, ?, ?, ?, ?)",
                (challenge_id, challenge, ceremony, code, now + 300),
            )
        return challenge_id, challenge

    def consume_passkey_challenge(
        self, challenge_id: str, ceremony: Literal["registration", "authentication"], code: str | None = None,
    ) -> bytes | None:
        """Consume one unexpired matching challenge atomically across workers."""
        with self._lock, self._conn:
            self._conn.execute("BEGIN IMMEDIATE")
            now = int(time.time())
            row = self._conn.execute(
                "DELETE FROM passkey_challenges WHERE challenge_id = ? AND ceremony = ? AND code IS ? AND expires_at > ? RETURNING challenge",
                (challenge_id, ceremony, code, now),
            ).fetchone()
            return bytes(row["challenge"]) if row else None

    def add_passkey_credential(self, credential: PasskeyCredential) -> None:
        """Store a verified credential for an account that has a user handle.

        The caller is responsible for verifying the WebAuthn ceremony. A
        duplicate credential ID raises IntegrityError rather than changing its owner.
        """
        with self._lock, self._conn:
            self._conn.execute("BEGIN IMMEDIATE")
            if not self._conn.execute(
                "SELECT 1 FROM passkey_accounts WHERE code = ?", (credential["code"],)
            ).fetchone():
                raise ValueError("Account has no passkey user handle")
            self._conn.execute(
                """INSERT INTO passkey_credentials
                   (credential_id, code, public_key, sign_count, created_at, device_type, backed_up, transports)
                   VALUES (:credential_id, :code, :public_key, :sign_count, :created_at, :device_type, :backed_up, :transports)""",
                {**credential, "device_type": credential.get("device_type"),
                 "backed_up": credential.get("backed_up"),
                 "transports": json.dumps(credential["transports"]) if credential.get("transports") is not None else None},
            )

    def update_passkey_after_authentication(
        self, credential_id: bytes, expected_count: int, new_count: int, backed_up: bool
    ) -> bool:
        """Atomically save verifier output if the stored counter is still current."""
        if new_count < 0 or (expected_count != 0 or new_count != 0) and new_count <= expected_count:
            raise ValueError("Invalid signature counter")
        with self._lock, self._conn:
            cursor = self._conn.execute(
                "UPDATE passkey_credentials SET sign_count = ?, backed_up = ? WHERE credential_id = ? AND sign_count = ?",
                (new_count, backed_up, credential_id, expected_count),
            )
            return cursor.rowcount == 1

    def get_passkey_credential(self, credential_id: bytes) -> PasskeyCredential | None:
        """Look up a credential and its owning account by credential ID."""
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM passkey_credentials WHERE credential_id = ?", (credential_id,)
            ).fetchone()
            return _passkey_credential_from_row(row) if row else None

    def list_passkey_credentials(self, code: str) -> list[PasskeyCredential]:
        """List credentials belonging to one account."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM passkey_credentials WHERE code = ? ORDER BY created_at, credential_id",
                (code,),
            ).fetchall()
            return [_passkey_credential_from_row(row) for row in rows]

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

    def delete_event(self, code: str, event_id: str) -> None:
        """Delete an asthma event by ID for a user. No-op if not found."""
        with self._lock:
            self._conn.execute(
                "DELETE FROM asthma_events WHERE id = ? AND code = ?", (event_id, code)
            )
            self._conn.commit()

    def delete_ritalin_event(self, code: str, event_id: str) -> None:
        """Delete a ritalin event by ID for a user. No-op if not found."""
        with self._lock:
            self._conn.execute(
                "DELETE FROM ritalin_events WHERE id = ? AND code = ?", (event_id, code)
            )
            self._conn.commit()

    def validate_token(self, token: str) -> bool:
        """Return True if the token matches any stored code entry."""
        with self._lock:
            row = self._conn.execute(
                "SELECT 1 FROM codes WHERE token = ?", (token,)
            ).fetchone()
            return row is not None

    def add_hashed_token(self, code: str, token: str, created_at: str) -> None:
        """Store a token digest for an existing code; never persist the token itself."""
        digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
        with self._lock:
            if not self._conn.execute("SELECT 1 FROM codes WHERE code = ?", (code,)).fetchone():
                raise ValueError("Unknown code")
            self._conn.execute(
                "INSERT INTO auth_tokens (token_hash, code, created_at) VALUES (?, ?, ?)",
                (digest, code, created_at),
            )
            self._conn.commit()

    def get_code_for_hashed_token(self, token: str) -> str | None:
        """Look up the owner of a token by its digest."""
        digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
        with self._lock:
            row = self._conn.execute(
                "SELECT code FROM auth_tokens WHERE token_hash = ?", (digest,)
            ).fetchone()
            return row["code"] if row else None

    def migrate_legacy_tokens(self, json_codes: list[CodeEntry]) -> None:
        """Copy legacy tokens from both stores into digest storage atomically.

        Keep the original values for the compatibility and rollback period.
        A token associated with different accounts is an error, never a guess.
        """
        with self._lock, self._conn:
            # Serialize concurrent worker startups before reading migration state.
            self._conn.execute("BEGIN IMMEDIATE")
            rows = self._conn.execute(
                "SELECT code, token, token_generated_at, created_at FROM codes"
            ).fetchall()
            known_codes = {row["code"] for row in rows}
            candidates = [
                (row["code"], row["token"], row["token_generated_at"] or row["created_at"])
                for row in rows if row["token"]
            ]
            for entry in json_codes:
                token = entry.get("token")
                if token:
                    if entry["code"] not in known_codes:
                        raise ValueError("JSON token belongs to an unknown SQLite account")
                    candidates.append((
                        entry["code"], token,
                        entry.get("token_generated_at") or entry["created_at"],
                    ))
            for code, token, created_at in candidates:
                digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
                existing = self._conn.execute(
                    "SELECT code FROM auth_tokens WHERE token_hash = ?", (digest,)
                ).fetchone()
                if existing and existing["code"] != code:
                    raise ValueError("Legacy token belongs to multiple accounts")
                self._conn.execute(
                    "INSERT OR IGNORE INTO auth_tokens (token_hash, code, created_at) VALUES (?, ?, ?)",
                    (digest, code, created_at),
                )

    def remove_legacy_plaintext_tokens(self) -> None:
        """Clear SQLite plaintext tokens only after every token has a matching digest."""
        with self._lock, self._conn:
            self._conn.execute("BEGIN IMMEDIATE")
            rows = self._conn.execute(
                "SELECT code, token FROM codes WHERE token IS NOT NULL AND token != ''"
            ).fetchall()
            for row in rows:
                digest = hashlib.sha256(row["token"].encode("utf-8")).hexdigest()
                owner = self._conn.execute(
                    "SELECT code FROM auth_tokens WHERE token_hash = ?", (digest,)
                ).fetchone()
                if owner is None or owner["code"] != row["code"]:
                    raise ValueError("Legacy token has no matching account digest")
            self._conn.execute("UPDATE codes SET token = NULL WHERE token IS NOT NULL")

    def get_code_for_token(self, token: str) -> str | None:
        """Return the code associated with a token, or None if not found."""
        with self._lock:
            row = self._conn.execute(
                "SELECT code FROM codes WHERE token = ?", (token,)
            ).fetchone()
            return row["code"] if row else None

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
