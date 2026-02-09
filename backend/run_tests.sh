#!/usr/bin/env bash

set -e

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${BLUE}================================${NC}"
echo -e "${BLUE}  Running Backend Tests${NC}"
echo -e "${BLUE}================================${NC}"
echo ""

# Change to backend directory
cd "$(dirname "$0")"

# Default: run all tests with coverage
if [ $# -eq 0 ]; then
    echo -e "${YELLOW}Running all tests with coverage...${NC}"
    echo ""
    uv run pytest --cov=app --cov-report=term-missing --cov-report=html -v

    echo ""
    echo -e "${GREEN}✓ Tests complete!${NC}"
    echo -e "${BLUE}HTML coverage report: htmlcov/index.html${NC}"
else
    # Pass arguments to pytest
    echo -e "${YELLOW}Running: pytest $@${NC}"
    echo ""
    uv run pytest "$@"
fi

echo ""
echo -e "${BLUE}================================${NC}"
