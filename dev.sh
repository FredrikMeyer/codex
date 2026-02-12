#!/usr/bin/env bash
#
# Development script to run both backend and frontend locally.
#
# Usage: ./dev.sh
#
# This script starts:
# - Backend (Flask) on http://localhost:5000
# - Frontend (HTTP server) on http://localhost:8000
#
# Press Ctrl+C to stop both services.

set -e

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Cleanup function
cleanup() {
  echo ""
  echo -e "${YELLOW}Stopping services...${NC}"

  # Kill background processes
  if [ ! -z "$BACKEND_PID" ]; then
    kill $BACKEND_PID 2>/dev/null || true
  fi
  if [ ! -z "$FRONTEND_PID" ]; then
    kill $FRONTEND_PID 2>/dev/null || true
  fi

  echo -e "${GREEN}Services stopped.${NC}"
  exit 0
}

# Set up trap to cleanup on exit
trap cleanup SIGINT SIGTERM

echo -e "${BLUE}╔════════════════════════════════════╗${NC}"
echo -e "${BLUE}║     Codex Development Server      ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════╝${NC}"
echo ""

# Check if uv is installed
if ! command -v uv &> /dev/null; then
  echo -e "${RED}Error: uv is not installed.${NC}"
  echo "Install it with: curl -LsSf https://astral.sh/uv/install.sh | sh"
  exit 1
fi

# Start backend
echo -e "${YELLOW}Starting backend...${NC}"
cd backend

# Load local development environment variables if they exist
if [ -f .env.local ]; then
  export $(grep -v '^#' .env.local | xargs)
  echo -e "${YELLOW}Loaded .env.local${NC}"
else
  # Set default ALLOWED_ORIGINS for local development
  export ALLOWED_ORIGINS="http://localhost:8000"
fi

# Use port 5001 instead of 5000 (macOS uses 5000 for AirPlay)
uv run flask --app app.main run --debug --port 5001 > /tmp/codex-backend.log 2>&1 &
BACKEND_PID=$!
cd ..

# Wait for backend to start
echo -e "${YELLOW}Waiting for backend to be ready...${NC}"
for i in {1..30}; do
  if curl -s http://localhost:5001/health > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Backend ready!${NC}"
    break
  fi
  sleep 0.5
done

# Start frontend
echo -e "${YELLOW}Starting frontend...${NC}"
cd frontend
python3 -m http.server 8000 > /tmp/codex-frontend.log 2>&1 &
FRONTEND_PID=$!
cd ..

# Wait for frontend to start
sleep 1

echo ""
echo -e "${GREEN}════════════════════════════════════${NC}"
echo -e "${GREEN}✓ Development servers running!${NC}"
echo -e "${GREEN}════════════════════════════════════${NC}"
echo ""
echo -e "${BLUE}Frontend:${NC} http://localhost:8000"
echo -e "${BLUE}Backend:${NC}  http://localhost:5001"
echo ""
echo -e "${YELLOW}Note:${NC} Using port 5001 (macOS uses 5000 for AirPlay)"
echo ""
echo -e "${YELLOW}Logs:${NC}"
echo -e "  Backend:  tail -f /tmp/codex-backend.log"
echo -e "  Frontend: tail -f /tmp/codex-frontend.log"
echo ""
echo -e "${YELLOW}Press Ctrl+C to stop both servers${NC}"
echo ""

# Wait for processes to finish (they won't unless killed)
wait $BACKEND_PID $FRONTEND_PID
