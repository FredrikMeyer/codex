#!/usr/bin/env bash

# Test runner for the entire project
# Run from project root

set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

show_help() {
    echo "Usage: ./test.sh [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  (no args)     Run all backend tests with coverage + type checking"
    echo "  --ci          Run tests for CI (includes XML coverage for codecov)"
    echo "  --fast        Run tests without coverage (faster)"
    echo "  --typecheck   Run only type checking with ty"
    echo "  --e2e         Run only backend E2E tests"
    echo "  --frontend    Run only frontend E2E tests (Playwright)"
    echo "  --unit        Run only unit tests (exclude E2E)"
    echo "  --watch       Run tests in watch mode (auto-rerun on changes)"
    echo "  --help        Show this help message"
    echo ""
    echo "Examples:"
    echo "  ./test.sh                 # All tests with coverage + type checking"
    echo "  ./test.sh --ci            # CI mode with XML coverage"
    echo "  ./test.sh --fast          # Quick test run"
    echo "  ./test.sh --typecheck     # Just type checking"
    echo "  ./test.sh --e2e           # Just E2E tests"
    echo "  ./test.sh tests/test_app.py  # Specific test file"
}

if [ "$1" = "--help" ] || [ "$1" = "-h" ]; then
    show_help
    exit 0
fi

echo -e "${BLUE}╔════════════════════════════════════╗${NC}"
echo -e "${BLUE}║     Codex Test Suite              ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════╝${NC}"
echo ""

echo -e "${YELLOW}🧪 Running JS unit tests${NC}"
echo ""
deno test --allow-read frontend/test/*.test.js
JS_EXIT_CODE=$?
if [ $JS_EXIT_CODE -eq 0 ]; then
    echo ""
    echo -e "${GREEN}✓ JS unit tests passed!${NC}"
else
    echo ""
    echo -e "${RED}✗ JS unit tests failed${NC}"
    exit $JS_EXIT_CODE
fi
echo ""

cd backend

case "$1" in
    --ci)
        echo -e "${YELLOW}🔍 Running type checking with ty${NC}"
        echo ""
        uv run ty check app tests
        TYPE_EXIT_CODE=$?

        if [ $TYPE_EXIT_CODE -eq 0 ]; then
            echo ""
            echo -e "${GREEN}✓ Type checking passed!${NC}"
        else
            echo ""
            echo -e "${RED}✗ Type checking failed${NC}"
            exit $TYPE_EXIT_CODE
        fi

        echo ""
        echo -e "${YELLOW}🧪 Running all tests with coverage (CI mode)${NC}"
        echo ""
        uv run pytest --cov=app --cov-report=term --cov-report=xml -v

        TEST_EXIT_CODE=$?

        if [ $TEST_EXIT_CODE -eq 0 ]; then
            echo ""
            echo -e "${GREEN}✓ All tests passed!${NC}"
            echo -e "${BLUE}📊 XML coverage report: backend/coverage.xml${NC}"
        else
            echo ""
            echo -e "${RED}✗ Tests failed${NC}"
            exit $TEST_EXIT_CODE
        fi
        ;;
    --fast)
        echo -e "${YELLOW}⚡ Fast mode: running tests without coverage${NC}"
        echo ""
        uv run pytest -v
        ;;
    --typecheck)
        echo -e "${YELLOW}🔍 Running type checking with ty${NC}"
        echo ""
        uv run ty check app tests
        EXIT_CODE=$?

        if [ $EXIT_CODE -eq 0 ]; then
            echo ""
            echo -e "${GREEN}✓ Type checking passed!${NC}"
        else
            echo ""
            echo -e "${RED}✗ Type checking failed${NC}"
            exit $EXIT_CODE
        fi
        ;;
    --e2e)
        echo -e "${YELLOW}🌐 Running backend E2E tests only${NC}"
        echo ""
        uv run pytest tests/test_e2e.py -v
        ;;
    --frontend)
        echo -e "${YELLOW}🎭 Running frontend E2E tests (Playwright)${NC}"
        echo ""
        uv run pytest tests/test_frontend_e2e.py -v
        ;;
    --unit)
        echo -e "${YELLOW}🔬 Running unit tests only${NC}"
        echo ""
        uv run pytest --ignore=tests/test_e2e.py --ignore=tests/test_playwright_example.py --ignore=tests/test_frontend_e2e.py -v
        ;;
    --watch)
        echo -e "${YELLOW}👀 Watch mode: tests will re-run on file changes${NC}"
        echo -e "${BLUE}Press Ctrl+C to stop${NC}"
        echo ""
        if ! command -v pytest-watch &> /dev/null; then
            echo -e "${RED}pytest-watch not installed. Installing...${NC}"
            uv add --dev pytest-watch
        fi
        uv run pytest-watch
        ;;
    "")
        echo -e "${YELLOW}🔍 Running type checking with ty${NC}"
        echo ""
        uv run ty check app tests
        TYPE_EXIT_CODE=$?

        if [ $TYPE_EXIT_CODE -eq 0 ]; then
            echo ""
            echo -e "${GREEN}✓ Type checking passed!${NC}"
        else
            echo ""
            echo -e "${RED}✗ Type checking failed${NC}"
            exit $TYPE_EXIT_CODE
        fi

        echo ""
        echo -e "${YELLOW}🧪 Running all tests with coverage${NC}"
        echo ""
        uv run pytest --cov=app --cov-report=term-missing --cov-report=html -v

        TEST_EXIT_CODE=$?

        if [ $TEST_EXIT_CODE -eq 0 ]; then
            echo ""
            echo -e "${GREEN}✓ All tests passed!${NC}"
            echo -e "${BLUE}📊 HTML coverage report: backend/htmlcov/index.html${NC}"
        else
            echo ""
            echo -e "${RED}✗ Tests failed${NC}"
            exit $TEST_EXIT_CODE
        fi
        ;;
    *)
        echo -e "${YELLOW}Running: pytest $@${NC}"
        echo ""
        uv run pytest "$@"
        ;;
esac

echo ""
echo -e "${BLUE}════════════════════════════════════${NC}"
