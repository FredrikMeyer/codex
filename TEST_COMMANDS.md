# Test Commands Quick Reference

## 🚀 Quick Start

From project root:
```bash
./test.sh              # All tests with coverage
```

## 📋 Available Commands

### Using test.sh (Recommended)

```bash
./test.sh                    # All tests + coverage + HTML report
./test.sh --fast             # All tests without coverage (faster)
./test.sh --e2e              # Only E2E tests
./test.sh --unit             # Only unit tests
./test.sh --watch            # Auto-rerun on file changes
./test.sh tests/test_app.py  # Specific test file
./test.sh --help             # Show all options
```

### Using pytest directly

From `backend/` directory:
```bash
uv run pytest                              # All tests
uv run pytest -v                           # Verbose output
uv run pytest --cov=app                    # With coverage
uv run pytest --cov=app --cov-report=html  # Coverage + HTML report
uv run pytest tests/test_e2e.py           # Specific file
uv run pytest tests/test_app.py::test_generate_code_creates_and_persists_code  # Specific test
uv run pytest -k "login"                   # Tests matching pattern
uv run pytest -x                           # Stop on first failure
uv run pytest --lf                         # Run last failed tests
```

### Backend-specific script

From `backend/` directory:
```bash
./run_tests.sh                # All tests with coverage
./run_tests.sh -v             # Pass custom pytest args
```

## 📊 Coverage Reports

After running tests with coverage:
- **Terminal**: Shows summary and missing lines
- **HTML**: Open `backend/htmlcov/index.html` in browser

## 🔍 Useful Flags

```bash
-v, --verbose              # Verbose output
-s                         # Show print statements
-x                         # Stop on first failure
--lf                       # Run last failed
--ff                       # Run failures first, then others
-k "pattern"               # Run tests matching pattern
--maxfail=2               # Stop after N failures
--tb=short                # Shorter traceback
--collect-only            # Show what tests would run
```

## 🎯 Common Workflows

### Before commit
```bash
./test.sh --fast  # Quick validation
```

### Debugging a failing test
```bash
./test.sh tests/test_app.py -v -s  # Verbose + show prints
```

### Check coverage
```bash
./test.sh  # Generates HTML report
open backend/htmlcov/index.html  # View in browser
```

### Development loop
```bash
./test.sh --watch  # Auto-rerun on changes
```

### CI simulation
```bash
cd backend
uv run pytest --cov=app --cov-report=term --cov-report=xml
```

## 📝 Test File Locations

```
backend/tests/
├── test_app.py           # Unit tests for endpoints
├── test_login_flow.py    # Auth flow integration tests
├── test_e2e.py           # End-to-end API tests
└── test_playwright_example.py  # Browser tests (skipped)
```

## ✅ Expected Output

```
9 passed, 1 skipped in 0.63s
Coverage: 97%
```

## 🐛 Troubleshooting

### Tests not found
```bash
cd /Users/fredrikmeyer/code/codex
./test.sh  # Run from project root
```

### Permission denied
```bash
chmod +x test.sh
chmod +x backend/run_tests.sh
```

### Port already in use (E2E tests)
```bash
lsof -ti:5001 | xargs kill  # Kill process on port 5001
```

### Dependencies out of sync
```bash
cd backend
uv sync
```
