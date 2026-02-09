# Asthma Medicine Tracker

[![Backend CI](https://github.com/FredrikMeyer/codex/actions/workflows/backend-ci.yml/badge.svg)](https://github.com/FredrikMeyer/codex/actions/workflows/backend-ci.yml)

Offline-friendly web app for logging daily asthma medication usage and exporting a CSV history.

## Project Structure

```
codex/
├── frontend/       # Web application
│   ├── index.html
│   ├── app.js
│   ├── styles.css
│   ├── service-worker.js
│   └── manifest.webmanifest
└── backend/        # Flask API
    ├── app/
    └── tests/
```

## Frontend

The web application allows users to track medication usage offline.

### Usage
- Open `frontend/index.html` (or deploy the contents) at `/codex/`.
- Pick a date, adjust the counter with the plus/minus buttons, and **Save count**.
- Use **Reset day** to clear a date and **Export CSV** to download your history.

Data is stored locally in the browser and works offline via the included service worker.

## Backend

A Flask backend for generating login codes, performing login, and accepting asthma log entries.

See [backend/README.md](backend/README.md) for details.

### Quick Start
```bash
cd backend
uv run python -m app.main
```

### Endpoints
- `POST /generate-code` → returns a new 4-character code.
- `POST /login` → body `{"code": "<CODE>"}` validates a generated code.
- `POST /logs` → body `{"code": "<CODE>", "log": {<your data>}}` stores an asthma log entry.
