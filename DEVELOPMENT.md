# Local Development Guide

## Quick Start

Start both backend and frontend servers with a single command:

```bash
./dev.sh
```

This will start:
- **Backend (Flask)**: http://localhost:5001
- **Frontend (Static Server)**: http://localhost:8000

**Note**: We use port 5001 for the backend because macOS uses port 5000 for AirPlay Receiver.

Press `Ctrl+C` to stop both services.

## What the dev script does

1. Starts Flask backend on port 5000 with debug mode
2. Starts Python HTTP server for frontend on port 8000
3. Waits for backend to be ready (health check)
4. Shows you both URLs
5. Logs output to `/tmp/codex-backend.log` and `/tmp/codex-frontend.log`
6. Cleanly shuts down both services when you press Ctrl+C

## Viewing logs

While the servers are running, you can view logs in separate terminals:

```bash
# Backend logs
tail -f /tmp/codex-backend.log

# Frontend logs
tail -f /tmp/codex-frontend.log
```

## Manual setup (if you prefer)

### Backend only

```bash
cd backend
uv sync                              # Install dependencies
export ALLOWED_ORIGINS="http://localhost:8000"  # Enable CORS for local frontend
uv run flask --app app.main run --debug --port 5001
```

### Frontend only

```bash
cd frontend
python3 -m http.server 8000
```

Then open http://localhost:8000 in your browser.

## Testing

Run the complete test suite:

```bash
./test.sh
```

This runs:
- Type checking with Pyright
- Backend unit tests
- Frontend E2E tests with Playwright
- Coverage report

## Configuration

### Backend

The frontend automatically detects localhost and uses `http://localhost:5001` as the backend URL.

For production, the backend URL is configured in `frontend/app.js`:
```javascript
const backendUrl = window.backendUrl || (window.location.hostname === 'localhost'
  ? 'http://localhost:5001'
  : 'https://asthma.fredrikmeyer.net');
```

### Environment Variables

Backend supports these environment variables (all optional for development):

- `ALLOWED_ORIGINS` - CORS allowed origins (default: `*` in dev mode)
- `DATA_FILE` - Path to data file (default: `./data.json`)
- `PRODUCTION` - Enable production mode (default: `false`)

Create `backend/.env` file for custom configuration:
```bash
ALLOWED_ORIGINS=http://localhost:8000
DATA_FILE=/tmp/codex-data.json
```

## Troubleshooting

### Port already in use

If you get "Address already in use" errors:

```bash
# Find process using port 5001 (backend)
lsof -i :5001

# Find process using port 8000 (frontend)
lsof -i :8000

# Kill specific process
kill -9 <PID>

# Or kill all Flask processes
pkill -f "flask --app app.main"

# Or kill all Python HTTP servers
pkill -f "python3 -m http.server"
```

**Note**: macOS uses port 5000 for AirPlay Receiver. If you see "AirTunes" errors, make sure you're using port 5001 for the backend.

### Frontend can't reach backend

1. Check backend is running: `curl http://localhost:5001/health`
2. Check browser console for CORS errors
3. Verify `backendUrl` in frontend/app.js
4. Check CORS configuration:
   ```bash
   # Test CORS headers
   curl -i -H "Origin: http://localhost:8000" http://localhost:5001/health | grep Access-Control

   # Should show:
   # Access-Control-Allow-Origin: http://localhost:8000
   # Access-Control-Allow-Credentials: true
   ```
5. Ensure `ALLOWED_ORIGINS` is set correctly (dev.sh does this automatically)

### uv not found

Install uv (Python package manager):
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

## Development Workflow

Typical development cycle:

1. Start servers: `./dev.sh`
2. Make changes to code
3. Frontend: Reload browser (changes are immediate)
4. Backend: Flask auto-reloads on file changes
5. Run tests: `./test.sh`
6. Commit changes

## Hot Reload

- **Frontend**: Changes to HTML/CSS/JS are immediate - just refresh browser
- **Backend**: Flask debug mode auto-reloads on Python file changes

## API Documentation

See [README.md](README.md#api-endpoints) for API endpoint documentation.

Test endpoints with curl:

```bash
# Generate code
curl -X POST http://localhost:5001/generate-code

# Health check
curl http://localhost:5001/health

# Save log (requires authentication)
curl -X POST http://localhost:5001/logs \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{"log": {"date": "2026-02-12", "spray": 2, "ventoline": 1}}'

# Get logs (requires authentication)
curl http://localhost:5001/logs \
  -H "Authorization: Bearer YOUR_TOKEN"
```
