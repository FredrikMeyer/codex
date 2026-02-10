# Docker Deployment Setup Complete ✅

Successfully created production-ready Docker deployment configuration for the asthma tracker backend!

## What Was Created

### 1. Dockerfile (Multi-stage build)
```dockerfile
# Builder stage - install dependencies
FROM python:3.12-slim as builder
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
RUN uv sync --frozen --no-dev

# Final stage - minimal production image
FROM python:3.12-slim
RUN useradd -m -u 1000 appuser  # Non-root user
COPY --from=builder /app/.venv /app/.venv
CMD ["gunicorn", "--workers", "2", ...]
```

**Features:**
- ✅ Multi-stage build (smaller final image)
- ✅ Non-root user (security)
- ✅ Health check endpoint
- ✅ Production WSGI server (gunicorn)
- ✅ Security updates included

### 2. docker-compose.yml
```yaml
services:
  asthma-backend:
    build: .
    ports:
      - "127.0.0.1:5000:5000"  # Only localhost
    environment:
      - PRODUCTION=true
      - ALLOWED_ORIGINS=${ALLOWED_ORIGINS}
    volumes:
      - ./data:/app/data  # Persistent storage
    restart: unless-stopped
```

**Features:**
- ✅ Auto-restart on failure
- ✅ Persistent data volume
- ✅ Resource limits
- ✅ Log rotation
- ✅ Health checks

### 3. .dockerignore
Excludes unnecessary files from build context:
- Python cache files
- Virtual environments
- Test files and coverage
- Git files
- Documentation

### 4. .env.docker.example
Template for environment variables:
```bash
ALLOWED_ORIGINS=https://fredrikmeyer.github.io
```

### 5. DEPLOYMENT_DOCKER.md
Comprehensive deployment guide covering:
- Docker installation
- nginx configuration with SSL
- Container management
- Monitoring and logs
- Troubleshooting
- Production checklist

## File Structure

```
backend/
├── Dockerfile                  # Multi-stage production image
├── docker-compose.yml          # Orchestration configuration
├── .dockerignore              # Build context exclusions
├── .env.docker.example        # Environment template
├── app/                       # Application code
│   └── main.py
├── data/                      # Persistent data (volume)
│   └── storage.json
├── pyproject.toml            # Dependencies (includes gunicorn)
└── uv.lock                   # Locked dependencies
```

## Dependencies Added

- ✅ **gunicorn==25.0.3** - Production WSGI server

## Build Verification

```bash
# Build successful ✅
docker build -t asthma-backend-test .

# Container runs successfully ✅
docker run -d -p 5001:5000 asthma-backend-test

# API responds correctly ✅
curl -X POST http://localhost:5001/generate-code
# → {"code":"VVOR"}
```

## Deployment Workflow

### First-Time Setup

```bash
# 1. Clone repository
git clone https://github.com/FredrikMeyer/codex.git
cd codex/backend

# 2. Create environment file
cp .env.docker.example .env.docker
nano .env.docker  # Set ALLOWED_ORIGINS

# 3. Build and start
docker compose up -d

# 4. Configure nginx (see DEPLOYMENT_DOCKER.md)

# 5. Obtain SSL certificate
sudo certbot certonly --nginx -d asthma.fredrikmeyer.net
```

### Updates

```bash
# Pull latest code
git pull

# Rebuild and restart
docker compose up -d --build

# Or explicitly
docker compose build
docker compose down
docker compose up -d
```

### Rollback

```bash
# Go to previous git commit
git checkout <previous-commit>

# Rebuild
docker compose up -d --build
```

## nginx Configuration

```nginx
server {
    listen 443 ssl;
    server_name asthma.fredrikmeyer.net;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Forwarded-Host $host;
    }
}
```

**Key points:**
- nginx handles SSL termination
- Container only exposed to localhost (127.0.0.1:5000)
- ProxyFix middleware trusts X-Forwarded-* headers
- Rate limiting works correctly per-client

## Data Persistence

Data is stored in `./data/storage.json` on the host and mounted into the container:

```yaml
volumes:
  - ./data:/app/data  # Host:Container
```

**Benefits:**
- ✅ Data survives container restarts
- ✅ Data survives container rebuilds
- ✅ Easy to backup (just copy ./data/)
- ✅ Easy to restore (replace ./data/)

## Security Features

### 1. Non-root User
```dockerfile
USER appuser  # UID 1000, not root
```

### 2. Only Localhost Exposure
```yaml
ports:
  - "127.0.0.1:5000:5000"  # Not 0.0.0.0:5000:5000
```
Container not accessible from internet, must go through nginx.

### 3. Security Updates
```dockerfile
RUN apt-get update && apt-get upgrade -y
```

### 4. Resource Limits
```yaml
deploy:
  resources:
    limits:
      cpus: '0.5'
      memory: 512M
```
Prevents container from consuming all server resources.

### 5. Log Rotation
```yaml
logging:
  options:
    max-size: "10m"
    max-file: "3"
```
Prevents disk fill from logs.

## Resource Requirements

**Minimum:**
- 1 CPU core
- 512MB RAM
- 1GB disk space

**Recommended:**
- 2 CPU cores
- 1GB RAM
- 5GB disk space (for logs and images)

**Container limits:**
- CPU: 0.5 core (50% of one core)
- Memory: 512MB max, 256MB guaranteed

## Container Management Commands

```bash
# Start
docker compose up -d

# Stop
docker compose down

# Restart
docker compose restart

# View logs (follow)
docker compose logs -f

# View logs (last 100 lines)
docker compose logs --tail=100

# Check status
docker compose ps

# Check resource usage
docker stats asthma-backend

# Access container shell
docker compose exec asthma-backend /bin/bash

# Remove everything (including volumes)
docker compose down -v
```

## Monitoring

### Container Health

```bash
# Check health status
docker compose ps
# Should show: Up (healthy)

# Detailed health info
docker inspect asthma-backend --format='{{.State.Health}}'
```

### Logs

```bash
# Container logs
docker compose logs -f

# nginx logs
sudo tail -f /var/log/nginx/asthma.access.log

# Only errors
docker compose logs | grep -i error
```

### Resources

```bash
# CPU and memory usage
docker stats asthma-backend

# Disk usage
docker system df
```

## Advantages Over Direct Deployment

| Feature | Direct (systemd) | Docker |
|---------|------------------|--------|
| **Isolation** | Shared system | Isolated environment |
| **Updates** | Complex | `docker compose up -d --build` |
| **Rollback** | Manual | Change git commit + rebuild |
| **Cleanup** | Manual uninstall | `docker compose down` |
| **Consistency** | OS-dependent | Same everywhere |
| **Resource limits** | No built-in limits | CPU/memory limits |
| **Multiple versions** | Complex | Multiple containers |
| **Dependencies** | System packages | Self-contained |

## Testing the Deployment

```bash
# 1. Container is running
docker compose ps
# Should show: Up (healthy)

# 2. API is accessible
curl -X POST http://localhost:5000/generate-code
# Should return: {"code":"XXXX"}

# 3. nginx is proxying
curl -X POST https://asthma.fredrikmeyer.net/generate-code
# Should return: {"code":"XXXX"}

# 4. Rate limiting works
for i in {1..6}; do
  curl -X POST https://asthma.fredrikmeyer.net/generate-code
done
# 6th should return: 429

# 5. CORS works
curl -X OPTIONS https://asthma.fredrikmeyer.net/generate-code \
  -H "Origin: https://fredrikmeyer.github.io" \
  -I
# Should include: Access-Control-Allow-Origin
```

## Production Checklist

Before deploying:

- [ ] Docker and Docker Compose installed
- [ ] Repository cloned
- [ ] `.env.docker` created with ALLOWED_ORIGINS
- [ ] Container builds successfully
- [ ] Container runs and API responds
- [ ] Data directory exists and is writable
- [ ] nginx installed and configured
- [ ] SSL certificate obtained
- [ ] nginx proxying to container
- [ ] HTTPS working
- [ ] HTTP redirects to HTTPS
- [ ] Rate limiting tested per-client
- [ ] CORS tested with frontend domain
- [ ] Container auto-restarts on failure
- [ ] Logs accessible
- [ ] Backup strategy in place

## Backup Strategy

### Manual Backup

```bash
# Backup data file
cp /var/www/codex/backend/data/storage.json \
   /var/backups/asthma-$(date +%Y%m%d).json
```

### Automated Daily Backup

```bash
# Add to crontab
echo "0 2 * * * cp /var/www/codex/backend/data/storage.json /var/backups/asthma-\$(date +\%Y\%m\%d).json" | crontab -
```

### Restore

```bash
# Stop container
docker compose down

# Restore backup
cp /var/backups/asthma-20260209.json \
   /var/www/codex/backend/data/storage.json

# Start container
docker compose up -d
```

## Common Issues and Solutions

### Container won't start

```bash
# Check logs for error
docker compose logs

# Check port not in use
sudo lsof -i :5000

# Try starting in foreground
docker compose up
```

### 502 Bad Gateway

```bash
# Check container is running
docker compose ps

# Check nginx can reach container
curl http://127.0.0.1:5000/generate-code

# Check nginx config
sudo nginx -t
```

### Data not persisting

```bash
# Check volume mount
docker compose config | grep volumes

# Check data directory ownership
ls -la /var/www/codex/backend/data

# Fix ownership (container runs as UID 1000)
sudo chown -R 1000:1000 /var/www/codex/backend/data
```

## Next Steps

1. **Deploy to server** - Follow DEPLOYMENT_DOCKER.md
2. **Configure monitoring** - Set up uptime monitoring
3. **Set up backups** - Automate daily data backups
4. **Phase 3** - Build frontend and connect to backend

## Summary

✅ **Dockerfile**: Multi-stage build, non-root user, health checks
✅ **docker-compose.yml**: Easy orchestration, volumes, auto-restart
✅ **.dockerignore**: Optimized build context
✅ **gunicorn**: Production WSGI server added
✅ **DEPLOYMENT_DOCKER.md**: Comprehensive deployment guide
✅ **Tested**: Build succeeds, container runs, API responds
✅ **Production-ready**: Security, monitoring, backup considerations

**Docker deployment is ready!** 🐳

Deploy with:
```bash
docker compose up -d
```

Update with:
```bash
git pull && docker compose up -d --build
```
