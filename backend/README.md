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

## Running Tests

### Quick Start

Use the test script from project root:
```bash
# Run all tests with coverage (recommended)
./test.sh

# Fast mode (no coverage)
./test.sh --fast

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
