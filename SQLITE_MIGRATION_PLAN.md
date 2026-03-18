# SQLite Migration Plan

## Goal

Replace the current JSON file storage (`storage.json`) with SQLite, while:
- Keeping all existing behaviour identical
- Adding a nightly JSON backup of the database
- Keeping `fetch-app-logs.sh` working (unaffected — it reads Docker stdout logs, not data files)

---

## Current Architecture

```
main.py  ──read_data()/write_data()──►  storage.py  ──► storage.json
              (codes management)

repository.py (LogRepository)
  ──load_data()/save_data()──►  storage.py  ──► storage.json
     (events, ritalin_events)
```

`main.py` directly calls `load_data`/`save_data` for all `codes` operations
(generate-code, login, generate-token, get-code, require_auth token lookup).

`repository.py` calls `load_data`/`save_data` for asthma events and ritalin events.

---

## Target Architecture

```
main.py  ──► CodeRepository  ──► sqlite_storage.py  ──► codex.db
repository.py (LogRepository)  ──► sqlite_storage.py  ──► codex.db

backup.py (standalone script)  ──► codex.db  ──► backups/YYYY-MM-DD.json
```

SQLite chosen over PostgreSQL because:
- Zero ops overhead (single file, no server process)
- Built into Python's standard library (`sqlite3`)
- Sufficient for the load (one household, occasional syncs)
- Simple backup: copy the file or dump to JSON

---

## Database Schema

```sql
CREATE TABLE codes (
    code               TEXT PRIMARY KEY,
    created_at         TEXT NOT NULL,
    last_login_at      TEXT,
    token              TEXT,
    token_generated_at TEXT
);

CREATE TABLE asthma_events (
    id          TEXT PRIMARY KEY,
    code        TEXT NOT NULL,
    date        TEXT NOT NULL,
    timestamp   TEXT NOT NULL,
    type        TEXT NOT NULL,
    count       INTEGER NOT NULL,
    preventive  INTEGER NOT NULL DEFAULT 0,   -- SQLite has no BOOLEAN
    received_at TEXT NOT NULL
);

CREATE TABLE ritalin_events (
    id          TEXT PRIMARY KEY,
    code        TEXT NOT NULL,
    date        TEXT NOT NULL,
    timestamp   TEXT NOT NULL,
    count       INTEGER NOT NULL,
    received_at TEXT NOT NULL
);
```

No foreign key constraints — keeps migration and tooling simple.

---

## Incremental Steps (Expand → Migrate → Contract)

Every step must leave all tests passing before proceeding to the next.

### Step 1 — Add `sqlite_storage.py` alongside `storage.py`

Create `backend/app/sqlite_storage.py` with:
- `init_db(path: Path) -> sqlite3.Connection` — creates tables if they don't exist, returns
  a thread-safe connection wrapper
- `SqliteStorage` class wrapping a `sqlite3.Connection` with the same conceptual operations
  the rest of the app needs:
  - `get_codes() → list[dict]`
  - `upsert_code(code_entry: dict) → None`
  - `get_events(code: str) → list[dict]`
  - `insert_event(code: str, event: dict, received_at: str) → None` (no-op if id exists)
  - `get_ritalin_events(code: str) → list[dict]`
  - `insert_ritalin_event(code: str, event: dict, received_at: str) → None` (no-op if id exists)

Use `sqlite3.connect(path, check_same_thread=False)` with `isolation_level=None` (autocommit).
Serialise all writes with a `threading.Lock` (same approach as the current JSON storage).

Write unit tests covering all methods. ✅ Tests pass.

### Step 2 — Add `CodeRepository` to `repository.py`

Move all codes-related logic out of `main.py` into a new `CodeRepository` class in
`repository.py`:

```python
class CodeRepository:
    def create_code(self, code: str) -> None: ...
    def record_login(self, code: str) -> bool: ...          # returns False if code not found
    def generate_token(self, code: str) -> str | None: ...  # returns existing or new token
    def get_code_for_token(self, token: str) -> str | None: ...
    def validate_token(self, token: str) -> bool: ...
```

At this step, implement `CodeRepository` backed by the *existing* `load_data`/`save_data`
(JSON), just like `LogRepository`. This moves the logic without changing storage.

Update `main.py` to use `CodeRepository` instead of inline `read_data()`/`write_data()`.

Write unit tests for `CodeRepository`. ✅ Tests pass.

### Step 3 — Wire both repositories to `SqliteStorage`

Replace the `load_data`/`save_data` calls inside `LogRepository` and `CodeRepository` with
calls to `SqliteStorage`.

`create_app()` changes:
- Read `DB_FILE` env var (default `backend/data/codex.db`) instead of `DATA_FILE`
- Create a single `SqliteStorage` instance
- Pass it to both `CodeRepository(storage)` and `LogRepository(storage)`

Keep `DATA_FILE` env var as a fallback alias during the transition (log a deprecation warning
if it is set).

All existing tests must still pass, now running against an in-memory SQLite db
(`":memory:"`). ✅ Tests pass.

### Step 4 — One-time data migration on startup

Add `migrate_json_to_sqlite(json_path: Path, storage: SqliteStorage) -> None` in a new
`backend/app/migrate.py`:

1. If `json_path` does not exist → skip (fresh install).
2. Load JSON.
3. Insert all `codes` entries (skip duplicates via `INSERT OR IGNORE`).
4. Insert all `events` entries (skip duplicates).
5. Insert all `ritalin_events` entries (skip duplicates).
6. Write a sentinel file `json_path.with_suffix('.migrated')` so the migration never runs
   twice.

Call this from `create_app()` before the app starts serving requests:

```python
if json_path.exists() and not sentinel.exists():
    migrate_json_to_sqlite(json_path, storage)
```

Write a test that verifies migrated data is readable through the repositories.
✅ Tests pass.

### Step 5 — Update `docker-compose.yml`

```yaml
environment:
  - PRODUCTION=true
  - ALLOWED_ORIGINS=${ALLOWED_ORIGINS:-https://fredrikmeyer.github.io}
  - DB_FILE=/app/data/codex.db
  # DATA_FILE kept pointing at old JSON so migration runs once, then ignored
  - DATA_FILE=/app/data/storage.json
```

Volume mount stays the same: `./data:/app/data`

### Step 6 — Remove `storage.py` and `DATA_FILE` references

Once the migration has run in production (confirmed via logs), in a follow-up commit:
- Delete `storage.py`
- Remove `DATA_FILE` fallback code from `create_app()`
- Remove `DATA_FILE` from `docker-compose.yml`

---

## Nightly JSON Backup

### `backend/backup.py` (standalone script)

```python
#!/usr/bin/env python3
"""
Export the SQLite database to a dated JSON backup file.

Usage:
    python backup.py --db /app/data/codex.db --out /app/data/backups/
"""
```

The script:
1. Reads `DB_FILE` from env (or `--db` arg).
2. Exports all three tables into the same JSON shape as the old `storage.json`:
   ```json
   {
     "codes": [...],
     "events": [...],
     "ritalin_events": [...]
   }
   ```
3. Writes to `<out-dir>/YYYY-MM-DD.json` (today's date in UTC).
4. Keeps the last 30 backups, deletes older ones.
5. Exits 0 on success, non-zero on error (so cron can email on failure).

### Running the backup — host-level cron on the droplet

The container does not have cron. Run the backup from the host:

```cron
# /etc/cron.d/codex-backup  (on the droplet)
0 2 * * * root docker exec asthma-backend python /app/backup.py >> /var/log/codex-backup.log 2>&1
```

The backup files land in `/app/data/backups/` inside the container, which maps to
`~/codex/backend/data/backups/` on the host (same volume mount). They survive container
restarts and upgrades.

### Retrieving a backup locally

Add `fetch-backup.sh` alongside `fetch-app-logs.sh`:

```bash
#!/usr/bin/env bash
# Copy latest backup JSON from the droplet.
ssh droplet "cat ~/codex/backend/data/backups/\$(ls -1 ~/codex/backend/data/backups/ | tail -1)"
```

---

## What Does Not Change

| Component | Status |
|-----------|--------|
| `fetch-app-logs.sh` | **Unchanged** — reads `docker logs` (stdout), not data files |
| All REST API endpoints | Unchanged (same request/response shapes) |
| Frontend JS | Unchanged |
| Service worker | Unchanged |
| Test runner (`test.sh`) | Unchanged |
| CI workflow | Unchanged |
| Rate limiting | Unchanged (still in-memory) |

---

## File Changelist Summary

| Action | File |
|--------|------|
| Create | `backend/app/sqlite_storage.py` |
| Create | `backend/app/migrate.py` |
| Create | `backend/backup.py` |
| Create | `backend/tests/test_sqlite_storage.py` |
| Create | `backend/tests/test_migrate.py` |
| Create | `fetch-backup.sh` |
| Modify | `backend/app/repository.py` — add `CodeRepository`, swap to `SqliteStorage` |
| Modify | `backend/app/main.py` — use `CodeRepository`, use `DB_FILE` |
| Modify | `backend/docker-compose.yml` — add `DB_FILE`, keep `DATA_FILE` for migration |
| Delete (later) | `backend/app/storage.py` |

---

## Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| Data loss during migration | Migration is additive (`INSERT OR IGNORE`); original JSON is never deleted |
| SQLite file corruption | WAL mode enabled (`PRAGMA journal_mode=WAL`) for crash safety |
| Concurrent writes under gunicorn (2 workers) | `threading.Lock` in `SqliteStorage`; gunicorn `--workers 1` is safer and sufficient for this load |
| Backup script fails silently | Script exits non-zero on error; cron logs to `/var/log/codex-backup.log` |
| Old backups filling disk | Script retains only last 30 days |
