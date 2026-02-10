# Testing Setup

## Overview

The project now has automated testing configured with:
- **GitHub Actions CI** for backend tests
- **Pytest** for unit and integration tests
- **E2E tests** using requests (HTTP API testing)
- **Playwright** ready for browser-based E2E tests (future)

## Current Test Coverage

```
Name              Stmts   Miss  Cover
-------------------------------------
app/__init__.py       2      0   100%
app/main.py          73      2    97%
-------------------------------------
TOTAL                75      2    97%
```

## Test Structure

```
backend/tests/
├── test_app.py              # Unit tests for endpoints
├── test_login_flow.py       # Integration tests for auth flow
├── test_e2e.py              # E2E tests (HTTP API)
└── test_playwright_example.py  # Example browser tests (skipped)
```

## Running Tests

### All tests
```bash
cd backend
uv run pytest
```

### With coverage report
```bash
uv run pytest --cov=app --cov-report=term
```

### Specific test file
```bash
uv run pytest tests/test_e2e.py -v
```

### Watch mode (auto-run on changes)
```bash
uv run pytest-watch
```

## GitHub Actions CI

**Location:** `.github/workflows/backend-ci.yml`

**Triggers:**
- Push to `main` branch (backend changes only)
- Pull requests to `main` (backend changes only)

**What it does:**
1. Sets up Python 3.12 and uv
2. Installs dependencies
3. Runs all tests with coverage
4. Uploads coverage to Codecov (optional)

**Status badge:**
```markdown
[![Backend CI](https://github.com/FredrikMeyer/codex/actions/workflows/backend-ci.yml/badge.svg)](https://github.com/FredrikMeyer/codex/actions/workflows/backend-ci.yml)
```

## Test Types

### Unit Tests (`test_app.py`, `test_login_flow.py`)
- Test individual endpoints in isolation
- Use Flask test client
- Fast, no external dependencies
- Mock database with temporary files

### E2E Tests (`test_e2e.py`)
- Test complete user flows
- Real HTTP requests to live server
- Server runs in background thread
- Tests API from "outside"

**Example flow:**
1. Generate code → 2. Login with code → 3. Save log entry

### Browser Tests (`test_playwright_example.py` - future)
- Currently skipped
- Ready for frontend E2E testing
- Would test actual browser interactions
- Requires Playwright browsers installed

## Adding New Tests

### Add a unit test
```python
# tests/test_my_feature.py
def test_my_new_endpoint(client):
    test_client, data_file = client
    response = test_client.post("/my-endpoint", json={"data": "value"})
    assert response.status_code == 200
```

### Add an E2E test
```python
# tests/test_e2e.py
def test_my_e2e_flow(server_url):
    response = requests.post(f"{server_url}/my-endpoint", json={"data": "value"})
    assert response.status_code == 200
```

## Future Enhancements

### Pre-commit hooks
Add `.pre-commit-config.yaml` to run tests before each commit.

### Browser-based E2E tests
1. Install browsers: `uv run playwright install`
2. Remove skip marker from `test_playwright_example.py`
3. Add frontend server to E2E fixtures
4. Write tests for UI interactions

### Coverage tracking
- Set up Codecov account
- Add `CODECOV_TOKEN` to GitHub secrets
- Track coverage over time
- Prevent coverage drops

### Frontend testing
- Add Vitest or Jest for JavaScript unit tests
- Add Playwright tests for UI flows
- Create separate frontend CI workflow

## Troubleshooting

### Tests fail locally but pass in CI
- Check Python version (`python --version` should be 3.12)
- Ensure dependencies are synced: `uv sync`
- Clear pytest cache: `rm -rf .pytest_cache`

### E2E tests timeout
- Check if port 5001 is already in use
- Increase timeout in `server_url` fixture
- Check firewall settings

### Playwright issues
- Ensure browsers are installed: `uv run playwright install`
- Check Playwright version compatibility
- Update Playwright: `uv add playwright@latest`

## Resources

- [Pytest documentation](https://docs.pytest.org/)
- [Playwright Python docs](https://playwright.dev/python/)
- [GitHub Actions docs](https://docs.github.com/en/actions)
- [uv documentation](https://docs.astral.sh/uv/)
