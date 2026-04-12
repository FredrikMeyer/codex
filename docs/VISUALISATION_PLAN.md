# Asthma Usage Visualisation + Framework Consideration (✅ Implemented)

## Context

This plan has been implemented. The chart is live. `frontend/charts.js` provides
`buildAsthmaChartSvg` and `buildRitalinChartSvg`, and `frontend/tracker.js` provides
`aggregateByDate` and `aggregateRitalinByDate`. This document is kept for architectural
reference.

---

## Framework Decision

**Recommendation: Stay vanilla JS, but split `app.js` into ES modules.**

Rationale:
- `app.js` is 614 lines — large but still readable and well-structured.
- Adding a chart adds ~80–100 lines; at ~700 lines it is still manageable.
- The script already uses `type="module"` (line 114 of `index.html`), so native ES module splitting is available with zero tooling changes.
- A framework (Alpine.js, Preact) would impose a build step or CDN dependency, complicating the offline PWA story.
- **Right next architectural step**: split into `storage.js`, `sync.js`, `chart.js`, `app.js` using ES module imports — not a framework migration.
- Revisit framework question if: (a) state management becomes painful, (b) component reuse becomes needed, or (c) the module count exceeds ~8 files.

---

## Visualisation Feature

### What it shows
A grouped bar chart of **daily dose totals for the last 30 days** (or fewer if less data exists), with one bar per medicine type per day:
- **Spray** — blue (`var(--accent)`)
- **Ventoline** — amber (`#f59e0b`)

Empty days within the range are omitted (not shown as zero bars) to keep the chart focused on actual usage data.

### Implementation approach — pure SVG (no library)

SVG gives precise control over bar positioning and labels. No external dependencies. Fully inline in `app.js`.

Chart dimensions: fixed `viewBox="0 0 600 180"` with `width="100%"` for responsive scaling.

### Files changed

| File | Change |
|------|--------|
| `frontend/index.html` | Add `<section id="trends-card" class="card">` with a `<div id="chart"></div>` before the History card |
| `frontend/app.js` | Add `aggregateByDate(events, days)` helper and `renderChart(events)` function; call via `renderAll(events)` wherever `render` is called |
| `frontend/styles.css` | Add SVG styles (axis text colour, bar colours, grid line) |
| `frontend/service-worker.js` | Bump cache version from v12 → v13 |

---

## Detailed Implementation

### 1. `aggregateByDate(events, days = 30)` (pure helper in `app.js`)

- Walk the last `days` dates backwards from today
- For each date, compute sprayTotal and ventolineTotal using `sumForType()`
- Return an array of `{ date, spray, ventoline }` objects
- Only include dates that have at least one dose > 0

### 2. `renderChart(events)` (DOM function in `app.js`)

- Call `aggregateByDate(events)`
- If no data, render a "No data yet" placeholder and return
- Compute `maxDoses = max(spray + ventoline)` across all days
- Build an SVG string:
  - For each day: two rects (spray, ventoline) scaled to bar height
  - Date labels on x-axis (abbreviated: "Mar 1"), shown every ~8th entry to avoid crowding
  - A single horizontal gridline at the top (max value)
- Set `innerHTML` of `#chart` element

### 3. `renderAll(events)` (coordinator in `app.js`)

Thin function calling both `render(events)` and `renderChart(events)`. All existing
`render(entries)` call sites replaced with `renderAll(entries)`.

### 4. HTML addition (`index.html`)

Added before the History `<section>`:
```html
<section class="card" id="trends-card">
  <div class="label">Trends</div>
  <div class="subtitle">Last 30 days of usage.</div>
  <div id="chart"></div>
</section>
```

### 5. CSS additions (`styles.css`)

```css
#chart svg { width: 100%; display: block; }
#chart .axis-label { fill: var(--muted); font-size: 10px; }
#chart .bar-spray { fill: var(--accent); }
#chart .bar-ventoline { fill: #f59e0b; }
#chart .grid-line { stroke: var(--border); }
```

### 6. Wiring

`renderAll(entries)` is called in the same places `render(entries)` was called:
- Initial page load
- After save, delete, reset-day, sync-from-cloud, clear-local-data

---

## Rules
- Run `./test.sh` after every step — must be green before committing
- Never mix structural and behavioural changes in the same commit
- Each step must leave the app in a working state
