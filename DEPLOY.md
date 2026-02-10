# Production Deployment Guide

Deploy the asthma tracker backend using pre-built Docker images from GitHub Container Registry.

## Overview

```
GitHub Actions (CI/CD)
   ↓ (builds & pushes on every commit to main)
GitHub Container Registry (ghcr.io)
   ↓ (you pull the image)
Your Server
   ↓ (runs with docker-compose)
nginx → Docker Container → Flask API
```

**Workflow:**
1. Push code to GitHub main branch
2. GitHub Actions builds Docker image automatically
3. Image published to `ghcr.io/fredrikmeyer/codex/backend:latest`
4. Pull and run on your server

## Prerequisites

- Ubuntu/Debian server with Docker installed
- nginx installed (you'll configure separately)
- Domain name pointing to server
- GitHub account (to pull images)

## Step 1: Install Docker (if not already)

```bash
# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Add your user to docker group
sudo usermod -aG docker $USER

# Install Docker Compose
sudo apt install docker-compose-plugin -y

# Logout and login for group to take effect
# Or use: newgrp docker

# Verify
docker --version
docker compose version
```

## Step 2: Authenticate with GitHub Container Registry

The image is public, but for better rate limits, authenticate:

```bash
# Create GitHub Personal Access Token
# Go to: https://github.com/settings/tokens
# Click: Generate new token (classic)
# Scopes: read:packages
# Copy the token

# Login to ghcr.io
echo "YOUR_GITHUB_TOKEN" | docker login ghcr.io -u YOUR_GITHUB_USERNAME --password-stdin

# Or login interactively
docker login ghcr.io
```

## Step 3: Set Up Application Directory

```bash
# Create app directory
sudo mkdir -p /var/www/codex/backend
sudo chown -R $USER:$USER /var/www/codex

# Navigate to directory
cd /var/www/codex/backend

# Download production docker-compose file
curl -O https://raw.githubusercontent.com/FredrikMeyer/codex/main/backend/docker-compose.prod.yml

# Or clone the repo and copy it
git clone https://github.com/FredrikMeyer/codex.git /tmp/codex
cp /tmp/codex/backend/docker-compose.prod.yml .

# Create data directory
mkdir -p data

# Create environment file
cat > .env << 'EOF'
# Frontend domain (required)
ALLOWED_ORIGINS=https://fredrikmeyer.github.io

# Production mode (already set in docker-compose.prod.yml)
# PRODUCTION=true
EOF
```

## Step 4: Pull and Start Container

```bash
# Pull latest image
docker compose -f docker-compose.prod.yml pull

# Start container
docker compose -f docker-compose.prod.yml up -d

# Check logs
docker compose -f docker-compose.prod.yml logs -f

# Verify container is running
docker compose -f docker-compose.prod.yml ps
```

**Expected output:**
```
NAME              IMAGE                                    STATUS        PORTS
asthma-backend    ghcr.io/fredrikmeyer/codex/backend:latest Up (healthy)  127.0.0.1:5000->5000/tcp
```

## Step 5: Test API

```bash
# Test from server (localhost)
curl -X POST http://localhost:5000/generate-code
# Should return: {"code":"XXXX"}

# Test health check
curl http://localhost:5000/test-protected
# Should return: {"error":"Authorization header required"}
```

## Step 6: Configure nginx

You'll configure nginx separately. Here's what you need to know:

**Backend is listening on:** `127.0.0.1:5000`

**Required proxy headers:**
```nginx
proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
proxy_set_header X-Forwarded-Proto $scheme;
proxy_set_header X-Forwarded-Host $host;
proxy_set_header Host $host;
```

**Example minimal nginx config:**
```nginx
server {
    listen 443 ssl http2;
    server_name asthma.fredrikmeyer.net;

    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Forwarded-Host $host;
        proxy_set_header Host $host;
    }
}
```

## Updating the Application

When you push new code to GitHub main, a new image is automatically built.

**To update on your server:**

```bash
cd /var/www/codex/backend

# Pull latest image
docker compose -f docker-compose.prod.yml pull

# Restart with new image
docker compose -f docker-compose.prod.yml up -d

# Check logs
docker compose -f docker-compose.prod.yml logs --tail=50 -f
```

**Or one command:**
```bash
docker compose -f docker-compose.prod.yml pull && \
docker compose -f docker-compose.prod.yml up -d && \
docker compose -f docker-compose.prod.yml logs --tail=50 -f
```

## Rollback to Previous Version

If something breaks, rollback to a previous image:

```bash
# List available image tags
# Visit: https://github.com/FredrikMeyer/codex/pkgs/container/codex%2Fbackend

# Pull specific version (by commit SHA)
docker pull ghcr.io/fredrikmeyer/codex/backend:main-abc1234

# Update docker-compose.prod.yml temporarily
# Change: image: ghcr.io/fredrikmeyer/codex/backend:latest
# To:     image: ghcr.io/fredrikmeyer/codex/backend:main-abc1234

# Restart
docker compose -f docker-compose.prod.yml up -d
```

## Container Management

### View Logs
```bash
# Follow logs
docker compose -f docker-compose.prod.yml logs -f

# Last 100 lines
docker compose -f docker-compose.prod.yml logs --tail=100

# Only errors
docker compose -f docker-compose.prod.yml logs | grep -i error
```

### Check Status
```bash
# Container status
docker compose -f docker-compose.prod.yml ps

# Resource usage
docker stats asthma-backend

# Health check status
docker inspect asthma-backend --format='{{.State.Health.Status}}'
```

### Restart Container
```bash
# Restart
docker compose -f docker-compose.prod.yml restart

# Or stop and start
docker compose -f docker-compose.prod.yml down
docker compose -f docker-compose.prod.yml up -d
```

### Access Container Shell
```bash
# Open shell
docker compose -f docker-compose.prod.yml exec asthma-backend /bin/bash

# Run one-off command
docker compose -f docker-compose.prod.yml exec asthma-backend python -c "print('Hello')"
```

## Data Backup

Data is stored in `./data/storage.json`:

```bash
# Manual backup
cp /var/www/codex/backend/data/storage.json \
   /var/backups/asthma-$(date +%Y%m%d).json

# Automated daily backup (add to crontab)
echo "0 2 * * * cp /var/www/codex/backend/data/storage.json /var/backups/asthma-\$(date +\%Y\%m\%d).json" | crontab -

# Restore from backup
docker compose -f docker-compose.prod.yml down
cp /var/backups/asthma-20260209.json \
   /var/www/codex/backend/data/storage.json
docker compose -f docker-compose.prod.yml up -d
```

## Monitoring

### Check if Image Was Updated

```bash
# View image info
docker images ghcr.io/fredrikmeyer/codex/backend

# Check when image was created
docker inspect ghcr.io/fredrikmeyer/codex/backend:latest | grep Created
```

### GitHub Actions Status

Check build status:
- https://github.com/FredrikMeyer/codex/actions

### Container Health

```bash
# Health check
docker compose -f docker-compose.prod.yml ps
# Should show: Up (healthy)

# Detailed health
docker inspect asthma-backend | grep -A 10 Health
```

## Environment Variables

Set in `.env` file in `/var/www/codex/backend/`:

```bash
# Required: Frontend domain for CORS
ALLOWED_ORIGINS=https://fredrikmeyer.github.io

# Multiple origins (comma-separated)
ALLOWED_ORIGINS=https://fredrikmeyer.github.io,https://asthma.example.com
```

**To update:**
1. Edit `/var/www/codex/backend/.env`
2. Restart: `docker compose -f docker-compose.prod.yml restart`

## Troubleshooting

### Container won't start

```bash
# Check logs
docker compose -f docker-compose.prod.yml logs

# Check if port 5000 is in use
sudo lsof -i :5000

# Try pulling again
docker compose -f docker-compose.prod.yml pull
docker compose -f docker-compose.prod.yml up -d
```

### Can't pull image

```bash
# Check you're logged in
docker login ghcr.io

# Pull manually
docker pull ghcr.io/fredrikmeyer/codex/backend:latest

# Check image exists
# Visit: https://github.com/FredrikMeyer/codex/pkgs/container/codex%2Fbackend
```

### Rate limiting not working per-client

```bash
# Verify PRODUCTION=true in logs
docker compose -f docker-compose.prod.yml logs | grep PRODUCTION

# Check nginx is sending X-Forwarded-For
# Logs should show real client IPs, not 127.0.0.1
docker compose -f docker-compose.prod.yml logs | grep "POST /generate-code"
```

### 502 Bad Gateway

```bash
# Check container is running
docker compose -f docker-compose.prod.yml ps

# Check nginx can reach container
curl http://127.0.0.1:5000/generate-code

# Check nginx config
sudo nginx -t
```

### Data permission issues

```bash
# Container runs as UID 1000
# Check data directory ownership
ls -la /var/www/codex/backend/data

# Fix ownership
sudo chown -R 1000:1000 /var/www/codex/backend/data

# Restart
docker compose -f docker-compose.prod.yml restart
```

## CI/CD Pipeline

### How It Works

1. **Trigger**: Push to main branch (or manual trigger)
2. **Build**: GitHub Actions builds Docker image
3. **Test**: Image is built successfully (tests in image)
4. **Push**: Image pushed to `ghcr.io/fredrikmeyer/codex/backend`
5. **Tags**: Image tagged with:
   - `latest` (always latest main)
   - `main-<sha>` (specific commit, e.g., `main-abc1234`)

### Manual Trigger

```bash
# Go to GitHub Actions page
# https://github.com/FredrikMeyer/codex/actions

# Click "Build and Publish Docker Image"
# Click "Run workflow"
```

### View Build Logs

```bash
# GitHub Actions page
# https://github.com/FredrikMeyer/codex/actions

# Click on latest workflow run
# View build logs
```

## Image Tags

- **`latest`**: Always latest from main branch (recommended)
- **`main-<sha>`**: Specific commit (for rollback)

**Examples:**
```bash
# Use latest (recommended)
image: ghcr.io/fredrikmeyer/codex/backend:latest

# Use specific commit (for rollback)
image: ghcr.io/fredrikmeyer/codex/backend:main-abc1234
```

## Security

### Image is Public

The image is public by default (anyone can pull). To make it private:

1. Go to: https://github.com/FredrikMeyer/codex/pkgs/container/codex%2Fbackend
2. Click "Package settings"
3. Change visibility to "Private"

### Only Localhost Exposed

Container only listens on `127.0.0.1:5000`:
- Not accessible from internet
- Must go through nginx
- nginx handles SSL and security headers

### Non-root User

Container runs as non-root user (UID 1000):
- Limited privileges
- Can't modify system files

## Production Checklist

Before going live:

- [ ] Docker installed on server
- [ ] Logged in to ghcr.io (`docker login ghcr.io`)
- [ ] Application directory created (`/var/www/codex/backend`)
- [ ] `docker-compose.prod.yml` downloaded
- [ ] `.env` file created with `ALLOWED_ORIGINS`
- [ ] Data directory created (`./data`)
- [ ] Image pulled (`docker compose -f docker-compose.prod.yml pull`)
- [ ] Container running (`docker compose -f docker-compose.prod.yml ps`)
- [ ] API responds (`curl http://localhost:5000/generate-code`)
- [ ] nginx configured and proxying to localhost:5000
- [ ] SSL certificate configured in nginx
- [ ] HTTPS working
- [ ] Rate limiting tested (6 requests = 429)
- [ ] CORS tested with frontend domain
- [ ] Backup strategy in place

## Quick Command Reference

```bash
# Pull latest image and restart
docker compose -f docker-compose.prod.yml pull && \
docker compose -f docker-compose.prod.yml up -d

# View logs
docker compose -f docker-compose.prod.yml logs -f

# Restart container
docker compose -f docker-compose.prod.yml restart

# Stop container
docker compose -f docker-compose.prod.yml down

# Check status
docker compose -f docker-compose.prod.yml ps

# Resource usage
docker stats asthma-backend

# Backup data
cp data/storage.json /var/backups/asthma-$(date +%Y%m%d).json
```

## Summary

**Deploy workflow:**
1. Push code to GitHub main → Image auto-builds
2. On server: `docker compose -f docker-compose.prod.yml pull`
3. On server: `docker compose -f docker-compose.prod.yml up -d`
4. Configure nginx to proxy to localhost:5000

**Update workflow:**
1. Push code to GitHub main → Image auto-builds (2-3 min)
2. On server: Pull and restart (one command)

**Simple, automated, production-ready!** 🚀
