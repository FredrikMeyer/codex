# Sync Section Polish Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Apply three polish fixes to the mobile Cloud Sync section's *configured* state — vertical-stack the secondary buttons, move the descriptive hint inside the "More options" details, and restyle the "More options" toggle as a subtle text link.

**Architecture:** Pure frontend (HTML + CSS). No JavaScript changes — `syncService.js` already iterates `querySelectorAll('.sync-collapse')` and `ui.js`' `closest('details')` still resolves the correct setup wrapper. Verification is visual via Playwright screenshots plus the existing test suite.

**Tech Stack:** vanilla HTML + CSS, native `<details>`/`<summary>`, no build step. Playwright (Python) via the backend venv for screenshot verification.

**Spec:** `docs/superpowers/specs/2026-05-17-sync-section-polish-design.md`.

---

## File Map

- Modify `frontend/index.html` (configured-state block, currently lines 82-94) — restructure markup.
- Modify `frontend/styles.css` — add `.sync-collapse--subtle > summary` rule and a mobile rule for `.sync-extras-buttons`.
- Modify `frontend/service-worker.js` (line 1) — bump cache version `v31` → `v32`.
- No new files. No test file changes (existing Playwright e2e tests don't reference the hint paragraph or secondary buttons' layout).

---

## Task 1: Restructure the configured-state HTML

**Files:**
- Modify: `frontend/index.html` (configured-state block currently at lines 82-94)

- [ ] **Step 1: Read the current configured-state block**

Open `frontend/index.html` and confirm the block currently looks like:

```html
      <div id="sync-configured" class="sync-configured" style="display: none;">
        <p class="hint">Syncs both asthma and Ritalin events across your devices.</p>
        <div class="button-group sync-actions">
          <button id="sync-from-cloud" class="primary">Sync from Cloud</button>
          <button id="sync-to-cloud" class="primary">Sync to Cloud</button>
        </div>
        <details class="sync-collapse" open>
          <summary class="sync-collapse-toggle">
            <span>More options</span>
            <span class="sync-collapse-chevron" aria-hidden="true">▸</span>
          </summary>
          <div class="button-group">
            <button id="show-code" class="ghost">Show My Code</button>
            <button id="disconnect-sync" class="ghost">Disconnect</button>
            <button id="clear-local-data" class="ghost danger">Clear local data</button>
          </div>
        </details>
      </div>
```

If the block already differs (e.g. someone has touched it in the meantime), STOP and re-read the spec before proceeding.

- [ ] **Step 2: Replace the entire `#sync-configured` block with the new structure**

Use the Edit tool with the exact `old_string` from Step 1 and this `new_string`:

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

Four changes summarised: hint paragraph moves inside the `<details>` (after the summary, before the button-group); the details gains `sync-collapse--subtle` modifier; the summary's chevron span comes before the label span; the inner button-group gains `sync-extras-buttons` class.

- [ ] **Step 3: Spot-check the diff**

Run `git diff frontend/index.html` and confirm only those four logical changes appear (hint moved; modifier class added; chevron reordered; button-group class added). The button IDs and `class="primary"` / `class="ghost"` / `class="ghost danger"` must all be unchanged so existing JS handlers and e2e selectors still resolve.

Do not commit yet — Task 2 and 3 land in the same logical change.

---

## Task 2: Add the subtle-summary CSS rule

**Files:**
- Modify: `frontend/styles.css` (add new rules immediately after the existing `.sync-collapse` block around line 320)

- [ ] **Step 1: Locate the existing `.sync-collapse` block**

Run `grep -n 'sync-collapse' frontend/styles.css | head -10` to confirm the existing block exists and find a good insertion point. Expected: rules for `.sync-collapse`, `.sync-collapse > summary`, `.sync-collapse > summary::-webkit-details-marker`, `.sync-collapse > summary:hover`, `.sync-collapse-chevron`, `.sync-collapse[open] > summary .sync-collapse-chevron`, and a `@media (min-width: 601px) { .sync-collapse > summary { display: none; } }`.

- [ ] **Step 2: Insert the subtle modifier rule before the existing `@media (min-width: 601px)` rule for `.sync-collapse > summary`**

Use the Edit tool to add this block immediately before the `@media (min-width: 601px) { .sync-collapse > summary { display: none; } }` rule:

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
```

Why before the desktop media query: the desktop rule hides the summary entirely on `min-width: 601px`, which is correct for both variants. Source order matters because `.sync-collapse--subtle > summary` and `.sync-collapse > summary` have equal specificity — the modifier must come *after* the base rule in source order so its overrides win.

- [ ] **Step 3: Verify the file parses**

Run `node -e 'require("fs").readFileSync("frontend/styles.css", "utf8")' && echo OK` (sanity that the file is still readable) and visually inspect with `grep -n 'sync-collapse--subtle' frontend/styles.css` — expect two matches (the rule and its hover variant).

---

## Task 3: Stack the secondary buttons vertically on mobile

**Files:**
- Modify: `frontend/styles.css` (add a rule inside or near the existing `@media (max-width: 600px)` block around line 401)

- [ ] **Step 1: Find the existing mobile media query**

Run `grep -nA5 '@media (max-width: 600px)' frontend/styles.css`. Expected: a block containing `body { padding: 16px; } .actions { flex-direction: column; } .counter { grid-template-columns: repeat(3, 1fr); } .code-input-group { flex-direction: column; }`.

- [ ] **Step 2: Add the `.sync-extras-buttons` rules inside that block**

Use the Edit tool to add `.sync-extras-buttons { flex-direction: column; }` and `.sync-extras-buttons > button { width: 100%; }` inside the existing `@media (max-width: 600px)` block. The block after edit should look like:

```css
@media (max-width: 600px) {
  body { padding: 16px; }
  .actions { flex-direction: column; }
  .counter { grid-template-columns: repeat(3, 1fr); }
  .code-input-group { flex-direction: column; }
  .sync-extras-buttons { flex-direction: column; }
  .sync-extras-buttons > button { width: 100%; }
}
```

- [ ] **Step 3: Verify**

`grep -n 'sync-extras-buttons' frontend/styles.css` — expect two matches, both inside the mobile media query.

---

## Task 4: Bump the service worker cache version

**Files:**
- Modify: `frontend/service-worker.js` (line 1)

- [ ] **Step 1: Bump v31 → v32**

Edit `frontend/service-worker.js` line 1: change `const CACHE = 'asthma-tracker-v31';` to `const CACHE = 'asthma-tracker-v32';`.

- [ ] **Step 2: Verify**

`head -1 frontend/service-worker.js` — expect `const CACHE = 'asthma-tracker-v32';`.

---

## Task 5: Visual verification of all six states via Playwright

**Files:**
- Read-only inspection of: `/tmp/poll-s1.png` through `/tmp/poll-s6.png`

- [ ] **Step 1: Start a local static server in the background**

```bash
cd frontend && python3 -m http.server 8765 >/tmp/srv.log 2>&1 &
echo $! > /tmp/srv.pid
sleep 1
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8765/index.html
```

Expected: `200`.

- [ ] **Step 2: Capture all six screenshots**

Run from project root (uses the backend venv's Playwright):

```bash
cd backend && .venv/bin/python3 - <<'PY'
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser = p.chromium.launch()

    # 1. mobile, not-configured, collapsed (default)
    ctx = browser.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, is_mobile=True)
    page = ctx.new_page()
    page.goto("http://localhost:8765/index.html", wait_until="domcontentloaded")
    page.wait_for_timeout(500)
    page.locator("section.card").first.screenshot(path="/tmp/poll-s1.png")
    # 2. mobile, not-configured, expanded (tap Set up sync)
    page.locator("summary.sync-collapse-toggle").first.click()
    page.wait_for_timeout(200)
    page.locator("section.card").first.screenshot(path="/tmp/poll-s2.png")
    ctx.close()

    # 3. mobile, configured, collapsed
    ctx2 = browser.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, is_mobile=True)
    ctx2.add_init_script("try { localStorage.setItem('asthma-auth-token', 'FAKE'); } catch(e) {}")
    page2 = ctx2.new_page()
    page2.goto("http://localhost:8765/index.html", wait_until="domcontentloaded")
    page2.wait_for_timeout(500)
    page2.locator("section.card").first.screenshot(path="/tmp/poll-s3.png")
    # 4. mobile, configured, expanded (tap More options)
    page2.locator("summary.sync-collapse-toggle:visible").first.click()
    page2.wait_for_timeout(200)
    page2.locator("section.card").first.screenshot(path="/tmp/poll-s4.png")
    ctx2.close()

    # 5. desktop, not-configured
    ctx3 = browser.new_context(viewport={"width": 1280, "height": 800})
    page3 = ctx3.new_page()
    page3.goto("http://localhost:8765/index.html", wait_until="domcontentloaded")
    page3.wait_for_timeout(500)
    page3.locator("section.card").first.screenshot(path="/tmp/poll-s5.png")
    ctx3.close()

    # 6. desktop, configured
    ctx4 = browser.new_context(viewport={"width": 1280, "height": 800})
    ctx4.add_init_script("try { localStorage.setItem('asthma-auth-token', 'FAKE'); } catch(e) {}")
    page4 = ctx4.new_page()
    page4.goto("http://localhost:8765/index.html", wait_until="domcontentloaded")
    page4.wait_for_timeout(500)
    page4.locator("section.card").first.screenshot(path="/tmp/poll-s6.png")
    ctx4.close()
    browser.close()
print("OK")
PY
```

Expected: `OK` printed. Six PNGs at `/tmp/poll-s{1..6}.png`.

- [ ] **Step 3: Inspect each screenshot and confirm the acceptance criteria**

Open each image with the Read tool. Acceptance criteria per state:

| # | State | Must show | Must NOT show |
| - | ----- | --------- | ------------- |
| 1 | mobile not-conf collapsed | "Set up sync ▸" pill toggle below status | the three setup options |
| 2 | mobile not-conf expanded | the three setup options (Generate Code / ABC123 / Paste token) | "More options" anywhere |
| 3 | mobile conf collapsed | "● Connected", Sync from Cloud, Sync to Cloud, "▸ More options" as a small left-aligned text link (no full-width pill, no border, transparent background) | the hint paragraph; Show My Code / Disconnect / Clear local data; full-pill More options toggle |
| 4 | mobile conf expanded | hint paragraph above three full-width vertically-stacked buttons (Show My Code / Disconnect / Clear local data) | wrapped buttons on two lines; horizontal layout |
| 5 | desktop not-conf | three setup options visible exactly like before, no summary toggle | the "Set up sync" summary text |
| 6 | desktop conf | Connected + the two sync buttons + hint + three horizontal secondary buttons | the "More options" summary text; vertical button stack |

If any criterion fails, STOP. Re-read the spec and the relevant task; fix and re-run this task.

- [ ] **Step 4: Stop the server and clean temp files**

```bash
kill $(cat /tmp/srv.pid) 2>/dev/null
rm -f /tmp/srv.pid /tmp/srv.log /tmp/poll-s*.png
```

---

## Task 6: Run the full test suite

**Files:** none modified.

- [ ] **Step 1: Run `./test.sh` from project root**

```bash
cd /Users/fredrikmeyer/code/codex && ./test.sh 2>&1 | tail -15
```

Expected last lines:
```
================= 190 passed, 2 skipped, 42 warnings in ~35s =================

✓ All tests passed!
```

- [ ] **Step 2: If any test fails, STOP**

Existing e2e tests (`backend/tests/test_frontend_e2e.py`) reference:
- `#sync-status`, `#sync-status-text`, `#sync-setup`, `#generate-code`, `#code-input`, `#complete-setup`

None of those selectors are affected by Task 1's restructure (the configured-state block is what changed; the setup block and its IDs are unchanged). If a test fails, diagnose root cause — do not skip or weaken tests to make them pass.

---

## Task 7: Single commit and push

**Files:** none additional — committing the changes from Tasks 1–4.

- [ ] **Step 1: Confirm the working tree state**

```bash
git status
git diff --stat
```

Expected modified files: `frontend/index.html`, `frontend/styles.css`, `frontend/service-worker.js`. Nothing else (no `uv.lock` etc.).

- [ ] **Step 2: Stage and commit the three frontend files together**

The three changes are one coordinated polish; landing them as a single commit avoids intermediate states where the HTML expects CSS that doesn't yet exist (or vice versa).

```bash
git add frontend/index.html frontend/styles.css frontend/service-worker.js
git commit -m "$(cat <<'EOF'
feat: polish configured-state sync section on mobile

Three coordinated changes to the Connected/configured view on mobile:
- Move the descriptive hint inside the More options details so it's
  hidden by default.
- Restyle the More options summary as a small subtle text link via a
  new .sync-collapse--subtle modifier, distinguishing it from the
  primary "Set up sync" pill.
- Stack the secondary buttons (Show My Code, Disconnect, Clear local
  data) vertically full-width on mobile so they don't wrap onto two
  lines each.

Desktop layout is unchanged because the new CSS only applies at the
mobile viewport (or to the modifier class which only the configured
details carries). Bumps service worker cache to v32.
EOF
)"
```

- [ ] **Step 3: Push**

```bash
git push 2>&1
```

If the push is rejected because `origin/main` has new commits, STOP and ask the user how to integrate (rebase vs merge). Do not force-push.

- [ ] **Step 4: Final sanity check**

```bash
git log --oneline -3
```

Expected: top line is the new `feat: polish configured-state sync section on mobile` commit, followed by `docs: spec for sync section polish` (7d1b632) and the previously-pushed `feat: collapse secondary sync buttons on mobile` (0872b57).

---

## Self-review notes (do not implement, for plan auditor)

- **Spec coverage:** Each spec decision is covered — buttons → Task 3, hint → Task 1, toggle style → Tasks 1 (chevron reorder + modifier class) and 2 (CSS).
- **Placeholders:** None. Every code block is complete and verbatim.
- **Type/name consistency:** `.sync-collapse--subtle` and `.sync-extras-buttons` are used identically across HTML and CSS tasks. Chevron span class `.sync-collapse-chevron` matches the existing rotation rule.
- **Order safety:** CSS modifier rule placed before the desktop media query and after the base `.sync-collapse > summary` rule — equal specificity, source order makes the override win on mobile while desktop's `display: none` still applies to both variants.
