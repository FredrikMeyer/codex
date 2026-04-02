# SQLite Migration Plan

## Goal

Replace the current JSON file storage (`storage.json`) with SQLite, while:
- Keeping all existing behaviour identical
- Adding a nightly JSON backup of the database
- Keeping `fetch-app-logs.sh` working (unaffected — it reads Docker stdout logs, not data files)

---

## Current Architecture (after Steps 1 & 2)

```
main.py  ──► CodeRepository  ──► storage.py  ──► storage.json
              (codes management)

main.py  ──► LogRepository   ──► storage.py  ──► storage.json
              (events, ritalin_events)

sqlite_storage.py  ──► codex.db   (exists, tested, not yet wired to repositories)
```

`CodeRepository` and `LogRepository` are fully extracted. `main.py` has no direct storage
calls. Both repositories still use the JSON backend exclusively.

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

## Backward Compatibility Principle

**Write to both JSON and SQLite until the very last step.** At every intermediate step the
JSON file remains a consistent, up-to-date copy of all data. Rolling back to JSON-only is
always possible by reverting a single commit.

---

## Incremental Steps (Expand → Migrate → Contract)

Every step must leave all tests passing before proceeding to the next.

### Step 1 — Add `sqlite_storage.py` alongside `storage.py` ✅ DONE

`SqliteStorage` class with `get_codes`, `upsert_code`, `insert_event`, `get_events`,
`insert_ritalin_event`, `get_ritalin_events`. Fully tested. JSON storage untouched.

### Step 2 — Add `CodeRepository` to `repository.py` ✅ DONE

`CodeRepository` extracted from `main.py`, backed by JSON. `main.py` updated to use it.
Tests written and passing.

### Step 3 — Expand `SqliteStorage` with missing code-query methods

`CodeRepository` needs two read operations that `SqliteStorage` does not yet have:
- `get_code_for_token(token: str) -> str | None`
- `validate_token(token: str) -> bool`

Add these to `SqliteStorage` with tests. No callers change yet. ✅ Tests pass.

### Step 4 — Dual-write: repositories write to JSON *and* SQLite ✅ DONE

Change `CodeRepository` and `LogRepository` constructors to accept both a `Path` (JSON)
and a `SqliteStorage` instance. Every mutation writes to **both** backends. Reads continue
to come from JSON (no behaviour change, easy rollback).

`create_app()` creates one `SqliteStorage(DB_FILE)` and passes it alongside the existing
`DATA_FILE` path to both repositories. Both `docker-compose.yml` and `docker-compose.prod.yml`
set `DB_FILE=/app/data/codex.db` so dual-write is active in production from this step.

All existing tests pass unchanged (they use JSON fixtures). Integration tests confirm
SQLite receives the same data on each write. ✅ Tests pass.

### Step 5 — One-time startup migration: JSON → SQLite

Add `migrate_json_to_sqlite(json_path: Path, storage: SqliteStorage) -> None` in
`backend/app/migrate.py`:

1. If `json_path` does not exist → skip (fresh install).
2. Load JSON.
3. Insert all `codes` via `upsert_code` (idempotent).
4. Insert all `events` via `insert_event` with `INSERT OR IGNORE`.
5. Insert all `ritalin_events` via `insert_ritalin_event` with `INSERT OR IGNORE`.
6. Write sentinel file `json_path.with_suffix('.migrated')` so it never runs twice.

Call from `create_app()` before serving requests. After this step SQLite is fully populated
with all historical data *and* receives every new write via Step 4's dual-write.

Write tests covering migrated data is readable through repositories. ✅ Tests pass.

### Step 6 — Switch reads to SQLite

Change `CodeRepository` and `LogRepository` to read from `SqliteStorage` instead of JSON.
Writes still go to both (dual-write continues — JSON remains a live backup).

This is the first step where SQLite becomes the source of truth for reads. Rollback is still
one commit away: swap reads back to JSON.

Update test fixtures to use `SqliteStorage(':memory:')` as the primary. ✅ Tests pass.

### Step 7 — Deploy and verify SQLite reads

Deploy and verify via logs that the migration sentinel is written and SQLite reads are
serving requests correctly.

### Step 8 — Contract: stop JSON writes, remove `storage.py`

Once production is confirmed stable on SQLite reads (Step 7), in a follow-up commit:
- Remove the `Path`/JSON arguments from `CodeRepository` and `LogRepository`
- Delete `storage.py`
- Remove `DATA_FILE` from `create_app()` and `docker-compose.yml`
- Remove `migrate_json_to_sqlite` call from `create_app()` (migration is history)

JSON file on disk is kept as a static backup but no longer written to. ✅ Tests pass.

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

| Action | File | Status |
|--------|------|--------|
| Create | `backend/app/sqlite_storage.py` | ✅ Done |
| Create | `backend/tests/test_sqlite_storage.py` | ✅ Done |
| Create | `backend/tests/test_code_repository.py` | ✅ Done |
| Modify | `backend/app/repository.py` — add `CodeRepository` (JSON-backed) | ✅ Done |
| Modify | `backend/app/main.py` — use `CodeRepository` | ✅ Done |
| Modify | `backend/app/sqlite_storage.py` — add `get_code_for_token`, `validate_token` | Step 3 |
| Modify | `backend/app/repository.py` — dual-write JSON + SQLite | ✅ Done |
| Modify | `backend/docker-compose.yml` and `docker-compose.prod.yml` — add `DB_FILE` | ✅ Done |
| Create | `backend/app/migrate.py` | Step 5 |
| Create | `backend/tests/test_migrate.py` | Step 5 |
| Modify | `backend/app/repository.py` — switch reads to SQLite | Step 6 |
| Create | `backend/backup.py` | Step 7 |
| Create | `fetch-backup.sh` | Step 7 |
| Delete | `backend/app/storage.py` | Step 8 |

---

## Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| Data loss during migration | Migration is additive (`INSERT OR IGNORE`); original JSON is never deleted |
| SQLite file corruption | WAL mode enabled (`PRAGMA journal_mode=WAL`) for crash safety |
| Concurrent writes under gunicorn (2 workers) | `threading.Lock` in `SqliteStorage`; gunicorn `--workers 1` is safer and sufficient for this load |
| Backup script fails silently | Script exits non-zero on error; cron logs to `/var/log/codex-backup.log` |
| Old backups filling disk | Script retains only last 30 days |
