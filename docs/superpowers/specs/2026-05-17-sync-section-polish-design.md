# Sync section polish — design spec

**Date:** 2026-05-17
**Scope:** Three small polish fixes to the mobile Cloud Sync section in the *configured* state.

## Context

The Cloud Sync section now collapses its setup options behind a `<details>` toggle on mobile (commits `854722f`, `eff0692`, `0872b57`). The configured (Connected) mobile state still has three rough edges flagged in the most recent screenshot review:

1. **Button wrap.** Inside the expanded "More options", the three secondary buttons (`Show My Code` / `Disconnect` / `Clear local data`) share a single horizontal row. At 390 px viewport width each gets ~110 px and the labels wrap onto two lines apiece.
2. **Hint paragraph.** The "Syncs both asthma and Ritalin events across your devices." text takes two lines in the default configured view, adding height without giving information the section header doesn't already imply.
3. **Toggle styling.** The "More options" `<summary>` reuses the same full-width pill styling as the `● Connected` status indicator above it. Visually it reads as a header / separator, not as a disclosure control sitting under the primary sync buttons.

## Decisions

Brainstormed and approved by user:

1. **Buttons:** vertical full-width stack on mobile only.
2. **Hint paragraph:** move inside the "More options" details (hidden by default, revealed on tap).
3. **Toggle styling:** subtle text link with a leading chevron, no background or border — applied only to the "More options" details, not the "Set up sync" pill (which stays prominent because it's the primary CTA when not configured).

## Implementation

### 1. HTML — `frontend/index.html` (configured-state block, currently lines 82-94)

Restructure the `#sync-configured` block:

- Drop the `<p class="hint">` direct child of `#sync-configured`.
- Wrap that hint and the secondary button-group inside the existing "More options" `<details>`.
- Add modifier class `sync-collapse--subtle` to that `<details>`.
- Reorder the children of its `<summary>`: chevron span first, label span second (so it renders as `▸ More options`).
- Add a class `sync-extras-buttons` to the inner `.button-group` for the mobile-stack CSS rule.

Target structure:

```html
<div id="sync-configured" class="sync-configured" style="display: none;">
  <div class="button-group sync-actions">
    <button id="sync-from-cloud" class="primary">Sync from Cloud</button>
    <button id="sync-to-cloud" class="primary">Sync to Cloud</button>
  </div>
  <details class="sync-collapse sync-collapse--subtle" open>
    <summary class="sync-collapse-toggle">
      <span class="sync-collapse-chevron" aria-hidden="true">▸</span>
      <span>More options</span>
    </summary>
    <p class="hint">Syncs both asthma and Ritalin events across your devices.</p>
    <div class="button-group sync-extras-buttons">
      <button id="show-code" class="ghost">Show My Code</button>
      <button id="disconnect-sync" class="ghost">Disconnect</button>
      <button id="clear-local-data" class="ghost danger">Clear local data</button>
    </div>
  </details>
</div>
```

### 2. CSS — `frontend/styles.css`

Add new rules; do not modify the existing `.sync-collapse > summary` block (it stays correct for the "Set up sync" toggle):

```css
.sync-collapse--subtle > summary {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 4px;
  margin-bottom: 0;
  background: transparent;
  border: none;
  border-radius: 0;
  color: var(--muted);
  font-weight: 500;
  cursor: pointer;
  list-style: none;
}
.sync-collapse--subtle > summary:hover {
  background: transparent;
  color: var(--text);
}

@media (max-width: 600px) {
  .sync-extras-buttons { flex-direction: column; }
  .sync-extras-buttons > button { width: 100%; }
}
```

The existing `.sync-collapse[open] > summary .sync-collapse-chevron { transform: rotate(90deg); }` rule already covers the subtle variant because it targets `.sync-collapse-chevron` regardless of the modifier class.

### 3. Service worker — `frontend/service-worker.js`

Bump `CACHE` to `'asthma-tracker-v32'`.

### 4. No JS changes needed

- `frontend/syncService.js` already iterates `document.querySelectorAll('.sync-collapse')`, so the new `.sync-collapse--subtle` element receives the same matchMedia open/close behaviour automatically.
- `frontend/ui.js`' `syncSetupSection.closest('details')` continues to resolve only the "Set up sync" details (because `#sync-setup` is nested inside that one); the configured-state details is unrelated to that selector and stays untouched by `updateSyncStatus`.

## Files touched

- `frontend/index.html` — restructure 12 lines around line 82
- `frontend/styles.css` — add ~15 new lines
- `frontend/service-worker.js` — single-line cache bump

## Testing

Per the visual-verification rule in `CLAUDE.md`, before committing:

1. Run `./test.sh` (full suite; expected: 190 passed, 2 skipped — no test file references the hint paragraph or `.sync-extras-buttons` layout).
2. Capture Playwright screenshots of all six states and visually review each:
   - Mobile (390×844, `is_mobile=True`):
     - Not-configured, collapsed (`Cloud Sync — Not configured — Set up sync ▸`).
     - Not-configured, expanded (after tapping Set up sync).
     - Configured, collapsed (no hint visible; small `▸ More options` link below the two sync buttons).
     - Configured, expanded (hint above three full-width stacked buttons).
   - Desktop (1280×800):
     - Not-configured (all three setup options visible, no summary).
     - Configured (Connected + sync buttons + hint + three horizontal secondary buttons — visually similar to today, only hint position changes).

Mobile configured-collapsed must show only:
```
Cloud Sync
Optional backup to secure cloud storage.
● Connected
[Sync from Cloud]
[Sync to Cloud]
▸ More options
```
(no hint, no full-pill toggle bar.)

## Out of scope

- The "Set up sync" toggle styling stays as today (full-width pill). The subtle treatment applies only to the configured-state disclosure.
- No copy changes to button labels or status text.
- No accessibility refactor beyond what `<details>`/`<summary>` already provide natively.
