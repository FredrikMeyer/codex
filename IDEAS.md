# Ideas & Improvement Areas

## Feature Ideas

### High-value medical insights

**Rescue vs preventive ratio chart**
The most clinically meaningful insight missing. GINA guidelines say >2 rescue uses/week = poorly controlled asthma. A line or ratio chart showing this over time would be genuinely useful for GP visits.

**Trigger tracking**
When logging a rescue dose, optionally tag the trigger: exercise, cold air, pollen, stress, illness, dust. Over time patterns emerge ("you use ventoline 3x more on high-pollen days"). Could be free-text or a preset list.

**Doctor report export**
A formatted PDF or printable HTML summary for GP appointments: total doses by month, rescue vs preventive ratio, worst weeks, any visible trends. Takes raw data and makes it medically actionable.

**Symptom severity on rescue doses**
A 1–3 scale (mild / moderate / severe) on rescue logs. Cheap to add, rich to analyse.

**Weekly trend summary**
A "this week vs last week" card at the top: `Rescue uses: 2 (↓1 from last week)`. Gives instant context without needing to read the chart.

---

### Ritalin-specific

**Weekend vs weekday pattern**
Ritalin is commonly skipped on weekends/holidays. A toggle "scheduled day / holiday" per entry, with a chart showing adherence patterns, would be more meaningful than raw dose counts.

**Intentional drug holiday tracking**
A separate "holiday" log type for planned medication breaks, distinct from simply not logging anything.

---

### UX improvements

**Quick-log button**
One tap to log "1 spray, rescue, today, now" with last-used defaults. The most common action shouldn't require date picking + type selection + counter adjustment.

**Calendar heatmap view**
A month grid where each day is colour-coded by total rescue dose. Instantly shows bad weeks. Much more intuitive than bar charts for spotting patterns.

**Extended chart time ranges**
Currently locked to 30 days. A 7 / 30 / 90 / 1-year switcher would reveal seasonal trends (asthma classically worsens in autumn).

**Undo delete**
Instead of permanent delete, show a toast with "Undo" for ~5 seconds. Simple to implement, saves accidental deletions.

**Dark mode**
Standard PWA expectation, especially for a health app used at night.

---

### Data & sync

**Sync status indicator**
Show "Last synced: 2 hours ago" or "3 local-only events" persistently, not just after a manual sync. Users shouldn't need to guess if their data is safe.

**JSON backup/restore**
Export full event array as JSON (beyond CSV). Allows full round-trip restore, not just data export. Especially important while backend is file-based.

**Import from CSV**
The current CSV export has no matching import. If someone loses their token or changes device, they're stuck.

**Auto-sync on reconnect**
Background Sync API — queue events while offline, flush automatically when connectivity is restored. Currently sync is entirely manual.

---

## Areas of Improvement

### Code quality

**`app.js` is 632 lines doing too much**
Handles event listeners, UI orchestration, sync logic, and state management. More to extract: a `syncService.js` for the cloud sync state machine, and moving edit dialog logic out.

**`localStorage` → `IndexedDB`**
localStorage is synchronous, size-limited (~5MB), and blocked in some private browsing modes. For a health app, IndexedDB is more reliable. The abstraction in `storage.js` makes this migration feasible without touching `app.js`.

**Remove the deprecated `/logs` endpoint**
Deferred since `EVENT_LOG_PLAN.md` was written. Dead code in production is a maintenance risk.

**Backend: JSON file → SQLite**
The JSON file storage works but is fragile — a crash mid-write corrupts the file. SQLite is just as zero-dependency, but transactional.

**Error handling in async ops**
Several sync functions have minimal error reporting. A failed individual event upload silently continues. Errors should surface with enough detail to diagnose (which event? what HTTP status?).

**No loading states during sync**
Sync buttons give no visual feedback while in progress. A simple "syncing…" state prevents double-clicks and reassures the user.

---

### Architecture

**Backend URL hardcoded in `config.js`**
Makes it hard to run against a local backend without editing a file. Even a simple `?backend=http://localhost:5000` query param override would help development.

**No app version shown in UI**
A small version string in the settings/sync area (matching the service worker cache key) helps diagnose issues with users.

**JSDoc type annotations + `tsc --checkJs`**
The codebase has good module separation but no type safety. Adding JSDoc types and running `tsc --checkJs --noEmit` (zero build step) would catch bugs like passing the wrong event shape to `smartMerge`.
