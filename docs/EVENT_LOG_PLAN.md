# Event-log refactor plan

## Goal
Replace the current per-day aggregate storage model (`{ spray: 2, ventoline: 1 }`) with a flat event log where each usage is one row. This lets us attach attributes (like `preventive`) to individual usages, not just to a whole day.

## New event shape
```json
{
  "id": "uuid",
  "date": "2026-02-21",
  "timestamp": "2026-02-21T14:30:00.000Z",
  "type": "ventoline",
  "count": 2,
  "preventive": true
}
```

- `id` — random UUID, used as deduplication key during cloud sync
- `date` — from date picker, used for grouping in history (timezone-safe)
- `timestamp` — actual datetime for ordering within a day
- `type` — `"spray"` or `"ventoline"`
- `count` — number of doses (≥ 1)
- `preventive` — boolean

---

## Step 1 — Backend: add `/events` endpoint ✅ DONE
*Old `/logs` endpoint stays untouched. Add a new one alongside it.*

- Add `UsageEvent` Pydantic model with validation:
  - `type` must be `"spray"` or `"ventoline"`
  - `count` ≥ 1
  - `timestamp` must be valid ISO 8601
  - `date` must be valid YYYY-MM-DD
- Add `Repository.save_event(code, event)`:
  - Idempotent: if an entry with the same `id` already exists for this code, skip it
- Add `Repository.get_events(code)`: returns all events for a user
- Add `POST /events` and `GET /events` with same auth as `/logs`
- Write tests in `backend/tests/test_events.py`
- **All existing tests must still pass**
- Commit: `feat: add event-based /events endpoint`

---

## Step 2 — Frontend: migrate localStorage to event array ✅ DONE
*Existing local data is preserved through a one-time migration.*

- Add v2 migration that runs once on startup:
  - Reads old `{ "2026-02-21": { spray: 2, ventoline: 1 } }` format
  - Converts each medicine type entry to a separate event (skipping zero counts)
  - Uses `{date}T12:00:00.000Z` as timestamp, generates a UUID per event
  - Marks done with key `asthma-migrated-v2`
- `loadEntries()` now returns an array (defaults to `[]`)
- Replace old date-keyed lookups with helper functions over the array:
  - `getEventsForDate(events, date)` — filter by `e.date`
  - Counter shows the sum for current date+type as context, but resets to 0 on type/date change
- Bump service worker cache to v9
- **All existing E2E tests must still pass**
- Commit: `feat: migrate frontend storage to event array`

---

## Step 3 — Frontend: new logging UI and history render ✅ DONE
*The "Save count" button now appends an event; preventive is per-usage.*

- Add "Preventivt" toggle button below the Spray/Ventoline buttons in HTML
  - Resets when medicine type or date changes
- `saveBtn` (label → "Log usage"):
  - Appends `{ id, date, timestamp, type, count, preventive }` to the array
  - Resets counter to 0 after saving
- `resetBtn` → removes all events for the selected date; resets counter to 0
- `render()`:
  - Groups events by date (newest first)
  - Shows each event as its own row with a Delete button (removes by `id`)
  - Shows "(preventivt)" label on preventive events
- Update CSV export: one row per event (`date, timestamp, type, count, preventive`)
- **All tests must pass**
- Commit: `feat: event-based usage logging with per-usage preventive flag`

---

## Step 4 — Frontend: switch cloud sync to `/events` ✅ DONE
*Sync now uses the new endpoint; old cloud data is not auto-migrated.*

- `syncToCloud`: POST each event to `POST /events` (server is idempotent by `id`)
- `syncFromCloud`: GET `/events`; merge into local array by `id` (add events not already present locally)
- Note: old cloud data (in `spray/ventoline` format) will not appear after this change. This is acceptable because the feature was only recently added.
- **All tests must pass**
- Commit: `feat: sync via /events endpoint`

---

## Step 5 — Backend: remove old `POST /logs` (deferred)
Once all clients have migrated (Step 4 deployed), the old `POST /logs` endpoint can be removed. `GET /logs` can stay for now. This step is deferred.

---

## Files to change
| File                           | Change                                                |
|--------------------------------|-------------------------------------------------------|
| `backend/app/main.py`          | Add `UsageEvent` model, `POST /events`, `GET /events` |
| `backend/app/repository.py`    | Add `save_event`, `get_events`                        |
| `backend/tests/test_events.py` | New test file for events endpoints                    |
| `frontend/app.js`              | Migration, event model, logging, render, sync         |
| `frontend/index.html`          | Preventivt toggle button, "Log usage" label           |
| `frontend/styles.css`          | `.preventive-toggle` rule                             |
| `frontend/service-worker.js`   | Cache bump v8 → v9                                    |

## Rules
- Run `./test.sh` after every step — must be green before committing
- Never mix structural and behavioural changes in the same commit
- Each step must leave the app in a working state
