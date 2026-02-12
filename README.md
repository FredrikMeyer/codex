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

A Flask backend with token authentication, rate limiting, and CORS support.

See [backend/README.md](backend/README.md) for details and [DEPLOY.md](DEPLOY.md) for production deployment.

### Features
- ✅ Token-based authentication
- ✅ Rate limiting per IP (prevents abuse)
- ✅ CORS configuration
- ✅ Docker support with automated builds
- ✅ 90 tests with 96.60% coverage

### Quick Start (Local Development)

**Option 1: Run both frontend and backend together** (recommended)
```bash
./dev.sh
```
This starts:
- Backend at http://localhost:5000
- Frontend at http://localhost:8000

Press `Ctrl+C` to stop both services.

**Option 2: Run backend only**
```bash
cd backend
uv sync
uv run flask --app app.main run --debug
```

### Production Deployment

**Automated deployment with Docker and GitHub Container Registry:**

1. **Push code to GitHub** → Image builds automatically
2. **Deploy on server:**

```bash
# Install Docker (if needed)
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER
# Logout/login for group to take effect

# Create application directory
sudo mkdir -p /var/www/codex/backend
sudo chown -R $USER:$USER /var/www/codex
cd /var/www/codex/backend

# Download production compose file
curl -O https://raw.githubusercontent.com/FredrikMeyer/codex/main/backend/docker-compose.prod.yml

# Create environment file
cat > .env << 'EOF'
ALLOWED_ORIGINS=https://fredrikmeyer.github.io
EOF

# Create data directory with correct permissions
mkdir -p data
sudo chown -R 1000:1000 data

# Pull and start container
docker compose -f docker-compose.prod.yml pull
docker compose -f docker-compose.prod.yml up -d

# Verify it's running
docker compose -f docker-compose.prod.yml ps
curl -X POST http://localhost:5000/generate-code
```

3. **Configure nginx** to proxy to `localhost:5000`:

```nginx
server {
    listen 443 ssl http2;
    server_name api.yourdomain.com;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Forwarded-Host $host;
        proxy_set_header Host $host;
    }

    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;
}
```

**Updates:**
```bash
# When you push new code, update with:
cd /var/www/codex/backend
docker compose -f docker-compose.prod.yml pull
docker compose -f docker-compose.prod.yml up -d
```

See [DEPLOY.md](DEPLOY.md) for complete deployment guide with troubleshooting.

### API Endpoints
- `POST /generate-code` → Generate access code (5/hour limit)
- `POST /login` → Validate code (10/minute limit)
- `POST /generate-token` → Exchange code for token (10/minute limit)
- `POST /logs` → Store log entry (100/minute limit, requires auth)
- `GET /test-protected` → Test token authentication
