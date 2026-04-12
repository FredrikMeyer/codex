# Frontend E2E Tests with Playwright

## Overview

Comprehensive browser-based tests for the frontend using Playwright. These tests confirm the current behavior of the asthma tracker frontend.

## Test Coverage

**8 Playwright tests** covering all core functionality:

### ✅ UI Loading
- `test_frontend_loads` - Verifies page loads with correct title and subtitle

### ✅ Medicine Type Selection
- `test_medicine_type_selector` - Tests switching between Spray and Ventoline
- `test_switching_medicine_type_changes_counter` - Verifies counter tracks each type separately

### ✅ Counter Functionality
- `test_counter_increment_decrement` - Tests +/- buttons
- Counter doesn't go below 0

### ✅ Data Persistence
- `test_save_and_display_entry` - Saves entry and shows in history
- `test_delete_entry` - Removes entry from history
- `test_reset_day` - Resets counter for current day

### ✅ UI Elements
- `test_ui_elements_present` - All main elements visible

## Running Tests

### Quick Start
```bash
# From project root
./test.sh --frontend

# From backend directory
uv run pytest tests/test_frontend_e2e.py -v
```

### With visible browser (for debugging)
```bash
uv run pytest tests/test_frontend_e2e.py -v --headed
```

### Specific test
```bash
uv run pytest tests/test_frontend_e2e.py::test_counter_increment_decrement -v
```

## Test Results

```
✓ 8 passed in 7.01s
✓ Tests confirmed behavior:
  - Default medicine type: Ventoline
  - Counter increments/decrements correctly
  - Data saved to localStorage
  - History displays with medicine type breakdown
  - Toast notifications work
  - Delete and reset functions work
```

## How It Works

### Server Fixture
- Starts a local HTTP server on port 8080
- Serves static files from `frontend/` directory
- Runs in background thread during tests
- Automatically cleaned up after tests

### Browser Testing
- Uses Chromium browser (headless by default)
- Real DOM interactions
- Tests actual JavaScript execution
- Validates CSS styling and layout

## Test Structure

```python
def test_example(page: Page, frontend_url: str):
    """Test description."""
    page.goto(frontend_url)  # Navigate to app

    # Interact with elements
    button = page.locator("#increment")
    button.click()

    # Assert expectations
    counter = page.locator("#count")
    expect(counter).to_have_text("1")
```

## Current Behavior Validated

### Default State
- ✅ Ventoline selected by default
- ✅ Counter starts at 0
- ✅ Date picker shows today
- ✅ History shows "No history yet" when empty

### Medicine Type Switching
- ✅ Maintains separate counts for each type
- ✅ Counter updates when switching types
- ✅ Visual active state on selected button

### Saving Entries
- ✅ Toast notification appears
- ✅ Entry appears in history
- ✅ History shows total and breakdown by type
- ✅ Format: "3 doses (Spray: 1, Ventoline: 2)"

### Data Management
- ✅ Delete removes entry completely
- ✅ Reset sets counter to 0 and saves
- ✅ Export button present (CSV functionality)

## Benefits

### Regression Protection
- Any UI changes that break functionality will be caught
- Tests run in CI on every push
- Confidence when refactoring

### Documentation
- Tests serve as living documentation
- Show how the app should behave
- Examples for new features

### Fast Feedback
- 7 seconds for full frontend test suite
- Can run specific tests during development
- Headless mode for CI, headed mode for debugging

## Future Enhancements

### Additional Tests
- [ ] Export CSV functionality
- [ ] Date picker selection
- [ ] Service worker offline behavior
- [ ] LocalStorage persistence across sessions
- [ ] Multiple entries on different dates

### Test Improvements
- [ ] Visual regression testing (screenshots)
- [ ] Mobile viewport testing
- [ ] Accessibility testing
- [ ] Performance testing

### CI Integration
- [x] GitHub Actions runs tests automatically
- [x] Playwright browsers installed in CI
- [ ] Parallel test execution
- [ ] Test artifacts (screenshots on failure)

## Troubleshooting

### Port already in use
```bash
lsof -ti:8080 | xargs kill -9
```

### Browser not installed
```bash
uv run playwright install chromium
```

### Tests timeout
- Increase timeout in test: `page.wait_for_timeout(5000)`
- Check if frontend server started: `curl http://localhost:8080`
- Look for JavaScript errors in browser console

### Server won't stop
- Port reuse is enabled in fixture
- Module-scoped fixture reuses server across tests
- Server shuts down automatically after test session

## Technical Details

### Dependencies
- `pytest-playwright` - Playwright integration for pytest
- `playwright` - Browser automation library
- Chromium browser (~160MB download)

### Test Fixtures
- `frontend_url` - Module-scoped, starts HTTP server
- `page` - Function-scoped, provided by pytest-playwright
- Browser context isolated per test

### Performance
- Server startup: ~1s
- Per test execution: ~0.5-1s
- Total suite: ~7s

## Maintenance

When updating frontend:
1. Run tests to ensure no regressions
2. Update tests if behavior intentionally changes
3. Add new tests for new features
4. Keep tests focused and independent
5. Use clear, descriptive test names

## Resources

- [Playwright Python Docs](https://playwright.dev/python/)
- [Pytest-Playwright Docs](https://github.com/microsoft/playwright-pytest)
- [Playwright Best Practices](https://playwright.dev/docs/best-practices)
