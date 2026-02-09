# Backend

## Project Structure

```
backend/
├── app/          # Application code
│   ├── __init__.py
│   └── main.py
└── tests/        # Test code
    ├── __init__.py
    └── test_login_flow.py
```

## Usage

- `uv run python -m app.main` - to run your Flask app
- `uv add <package>` - to add new dependencies
- `uv sync` - to sync dependencies from the lockfile

## API Endpoints

### Authentication
- **POST `/generate-code`** - Generate a new 4-character authentication code
  - Response: `{"code": "AB12"}`

- **POST `/login`** - Validate an authentication code
  - Request: `{"code": "AB12"}`
  - Response: `{"status": "ok"}`

- **POST `/generate-token`** - Exchange a code for a long-lived API token
  - Request: `{"code": "AB12"}`
  - Response: `{"token": "64-char-hex-string"}`
  - Note: Returns the same token if called multiple times with the same code

### Data
- **POST `/logs`** - Store an asthma log entry (supports dual authentication)
  - **Option 1 - Code auth** (backward compatible):
    - Request: `{"code": "AB12", "log": {"date": "2026-02-09", "spray": 2, "ventoline": 1}}`
    - Response: `{"status": "saved"}`
  - **Option 2 - Token auth** (recommended):
    - Headers: `Authorization: Bearer <64-char-token>`
    - Request: `{"log": {"date": "2026-02-09", "spray": 2, "ventoline": 1}}`
    - Response: `{"status": "saved"}`
  - Note: Token auth is preferred; code in body is not required when using token

## Running Tests

### Quick Start

Use the test script from project root:
```bash
# Run all tests with coverage + type checking (recommended)
./test.sh

# Fast mode (no coverage, no type checking)
./test.sh --fast

# Type checking only
./test.sh --typecheck

# Only E2E tests
./test.sh --e2e

# Only unit tests
./test.sh --unit

# Watch mode (auto-rerun on changes)
./test.sh --watch

# Specific test file
./test.sh tests/test_login_flow.py

# Show help
./test.sh --help
```

Or from the backend directory:
```bash
cd backend
./run_tests.sh
```

### Manual pytest commands

```bash
# All tests with coverage
uv run pytest --cov=app --cov-report=term-missing

# Verbose output
uv run pytest -v

# Specific test file
uv run pytest tests/test_login_flow.py

# E2E tests only
uv run pytest tests/test_e2e.py
```

### Type Checking

The project uses [ty](https://github.com/astral-sh/ty), an extremely fast Python type checker from Astral.

```bash
# Type check the codebase
uv run ty check app tests

# Type checking is automatically run with ./test.sh
./test.sh

# Run only type checking
./test.sh --typecheck
```

Type checking is also enforced in CI - all pull requests must pass type checking.
