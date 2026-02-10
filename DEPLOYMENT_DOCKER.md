# Docker Deployment Guide

This guide covers deploying the asthma tracker backend using Docker with nginx reverse proxy and SSL.

## Architecture Overview

```
Internet
   ↓
nginx (443/SSL) → Docker container (localhost:5000)
   ↓                      ↓
Let's Encrypt          Flask app
                          ↓
                    Volume: ./data
```

**Components:**
- **nginx**: Reverse proxy, SSL termination, HTTP→HTTPS redirect (host)
- **Docker container**: Flask app with gunicorn
- **Volume**: Persistent data storage
- **Let's Encrypt**: Free SSL certificates (host)

**Benefits of Docker:**
- ✅ Isolated environment
- ✅ Easy updates (rebuild + restart)
- ✅ Consistent deployment
- ✅ Easy rollback
- ✅ Resource limits
- ✅ No Python/dependency management on host

## Prerequisites

- Ubuntu/Debian server with root access
- Domain name pointing to server (e.g., `asthma.fredrikmeyer.net`)
- Port 80 and 443 open in firewall
- Docker and Docker Compose installed

## Step 1: Install Docker

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Add your user to docker group (logout/login required)
sudo usermod -aG docker $USER

# Install Docker Compose
sudo apt install docker-compose-plugin -y

# Verify installation
docker --version
docker compose version
```

## Step 2: Install nginx and Certbot

```bash
# Install nginx
sudo apt install nginx -y

# Install certbot for Let's Encrypt
sudo apt install certbot python3-certbot-nginx -y
```

## Step 3: Deploy Application

```bash
# Clone repository
cd /var/www
sudo git clone https://github.com/FredrikMeyer/codex.git
sudo chown -R $USER:$USER codex

# Go to backend directory
cd codex/backend

# Create environment file for Docker
cp .env.docker.example .env.docker
nano .env.docker
```

**Edit `.env.docker`:**
```bash
# Set your frontend domain
ALLOWED_ORIGINS=https://fredrikmeyer.github.io
```

## Step 4: Build and Start Container

```bash
# Build Docker image
docker compose build

# Start container
docker compose up -d

# Check logs
docker compose logs -f

# Verify container is running
docker compose ps
```

**Expected output:**
```
NAME              IMAGE                  STATUS        PORTS
asthma-backend    backend-asthma-backend Up 10 seconds 127.0.0.1:5000->5000/tcp
```

## Step 5: Obtain SSL Certificate

```bash
# Get certificate (replace with your domain)
sudo certbot certonly --nginx -d asthma.fredrikmeyer.net

# Certificate will be saved to:
# /etc/letsencrypt/live/asthma.fredrikmeyer.net/fullchain.pem
# /etc/letsencrypt/live/asthma.fredrikmeyer.net/privkey.pem
```

## Step 6: Configure Nginx

Create `/etc/nginx/sites-available/asthma`:

```nginx
# HTTP server - redirect all traffic to HTTPS
server {
    listen 80;
    listen [::]:80;
    server_name asthma.fredrikmeyer.net;

    # Redirect all HTTP traffic to HTTPS
    return 301 https://$host$request_uri;
}

# HTTPS server - reverse proxy to Docker container
server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name asthma.fredrikmeyer.net;

    # SSL configuration
    ssl_certificate /etc/letsencrypt/live/asthma.fredrikmeyer.net/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/asthma.fredrikmeyer.net/privkey.pem;
    include /etc/letsencrypt/options-ssl-nginx.conf;
    ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem;

    # Security headers
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;

    # Reverse proxy to Docker container
    location / {
        # Proxy to container on localhost:5000
        proxy_pass http://127.0.0.1:5000;

        # Preserve original request information
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Forwarded-Host $host;

        # Timeouts
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;

        # Disable buffering
        proxy_buffering off;

        # WebSocket support (if needed in future)
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }

    # Access logs
    access_log /var/log/nginx/asthma.access.log;
    error_log /var/log/nginx/asthma.error.log;
}
```

**Enable the site:**
```bash
# Create symlink
sudo ln -s /etc/nginx/sites-available/asthma /etc/nginx/sites-enabled/

# Test configuration
sudo nginx -t

# Reload nginx
sudo systemctl reload nginx
```

## Step 7: Verify Deployment

```bash
# Check container is running
docker compose ps

# Check container logs
docker compose logs --tail=50

# Check nginx is proxying correctly
curl -I https://asthma.fredrikmeyer.net

# Test API endpoint
curl -X POST https://asthma.fredrikmeyer.net/generate-code
# Should return: {"code":"XXXX"}

# Test rate limiting
for i in {1..6}; do
  curl -X POST https://asthma.fredrikmeyer.net/generate-code
done
# 6th request should return 429
```

## Container Management

### Start/Stop Container

```bash
# Start
docker compose up -d

# Stop
docker compose down

# Restart
docker compose restart

# View logs
docker compose logs -f

# View last 100 lines
docker compose logs --tail=100
```

### Update Application

```bash
cd /var/www/codex/backend

# Pull latest code
git pull

# Rebuild image
docker compose build

# Restart with new image
docker compose down
docker compose up -d

# Or in one command
docker compose up -d --build
```

### View Container Stats

```bash
# Resource usage
docker stats asthma-backend

# Processes inside container
docker compose top

# Inspect container
docker compose inspect
```

### Access Container Shell

```bash
# Open shell in running container
docker compose exec asthma-backend /bin/bash

# Or as root
docker compose exec -u root asthma-backend /bin/bash

# Run one-off command
docker compose exec asthma-backend python -c "print('Hello')"
```

## Data Persistence

Data is stored in `./data/storage.json` on the host, mounted into the container.

### Backup

```bash
# Backup data file
cp /var/www/codex/backend/data/storage.json \
   /var/backups/asthma-$(date +%Y%m%d).json

# Automated daily backup (add to crontab)
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

## Environment Variables

Set in `.env.docker`:

```bash
# Frontend domain (required)
ALLOWED_ORIGINS=https://fredrikmeyer.github.io

# Can also set multiple origins
ALLOWED_ORIGINS=https://fredrikmeyer.github.io,https://asthma.example.com
```

**To update**:
1. Edit `/var/www/codex/backend/.env.docker`
2. Restart container: `docker compose restart`

## Running Multiple Apps

Since you're running multiple apps, use different ports:

```yaml
# docker-compose.yml for App 1 (Links)
ports:
  - "127.0.0.1:3002:3002"

# docker-compose.yml for App 2 (Asthma)
ports:
  - "127.0.0.1:5000:5000"
```

**nginx config for multiple apps:**
```nginx
# App 1: Links
server {
    listen 443 ssl;
    server_name links.fredrikmeyer.net;
    location / {
        proxy_pass http://127.0.0.1:3002;
        # ... proxy headers ...
    }
}

# App 2: Asthma
server {
    listen 443 ssl;
    server_name asthma.fredrikmeyer.net;
    location / {
        proxy_pass http://127.0.0.1:5000;
        # ... proxy headers ...
    }
}
```

## Monitoring and Logs

### Container Logs

```bash
# Follow logs
docker compose logs -f

# Last 100 lines
docker compose logs --tail=100

# Logs since 10 minutes ago
docker compose logs --since=10m

# Only errors
docker compose logs | grep -i error
```

### nginx Logs

```bash
# Access logs
sudo tail -f /var/log/nginx/asthma.access.log

# Error logs
sudo tail -f /var/log/nginx/asthma.error.log
```

### Container Health

```bash
# Health status
docker compose ps

# Detailed health info
docker inspect asthma-backend --format='{{.State.Health}}'
```

## Resource Limits

Configured in `docker-compose.yml`:

```yaml
deploy:
  resources:
    limits:
      cpus: '0.5'      # Max 50% of one CPU core
      memory: 512M     # Max 512MB RAM
    reservations:
      cpus: '0.25'     # Guaranteed 25% CPU
      memory: 256M     # Guaranteed 256MB RAM
```

**Adjust for your server:**
- Small server (1 CPU, 1GB RAM): 0.5 CPU, 256M RAM
- Medium server (2 CPU, 2GB RAM): 1.0 CPU, 512M RAM

## Auto-Restart on Server Reboot

Docker containers with `restart: unless-stopped` automatically start on server reboot.

**Verify:**
```bash
# Reboot server
sudo reboot

# After reboot, check container is running
docker compose ps
```

## Security Best Practices

### 1. Container runs as non-root user

```dockerfile
USER appuser  # UID 1000
```

### 2. Only expose to localhost

```yaml
ports:
  - "127.0.0.1:5000:5000"  # Not 5000:5000
```

This prevents direct access to container, must go through nginx.

### 3. Security updates

```dockerfile
RUN apt-get update && apt-get upgrade -y
```

Rebuild image monthly for security patches:
```bash
docker compose build --no-cache
docker compose up -d
```

### 4. Resource limits

Prevents container from consuming all server resources.

### 5. Log rotation

```yaml
logging:
  options:
    max-size: "10m"
    max-file: "3"
```

Prevents disk fill from logs.

## Troubleshooting

### Container won't start

```bash
# Check logs
docker compose logs

# Check if port is already in use
sudo lsof -i :5000

# Try starting in foreground (see errors)
docker compose up
```

### 502 Bad Gateway from nginx

```bash
# Check container is running
docker compose ps

# Check container logs
docker compose logs --tail=50

# Check nginx can reach container
curl http://127.0.0.1:5000/generate-code

# Check nginx config
sudo nginx -t
```

### Container keeps restarting

```bash
# Check logs for crash reason
docker compose logs

# Check health check is passing
docker inspect asthma-backend --format='{{.State.Health}}'

# Disable health check temporarily (in docker-compose.yml)
# Comment out healthcheck section, rebuild
```

### Rate limiting not working

```bash
# Check PRODUCTION=true in logs
docker compose logs | grep PRODUCTION

# Check nginx is sending X-Forwarded-For
# Should see real client IPs in logs, not 127.0.0.1
docker compose logs | grep "POST /generate-code"
```

### Permission denied on data volume

```bash
# Check ownership
ls -la /var/www/codex/backend/data

# Fix ownership (container runs as UID 1000)
sudo chown -R 1000:1000 /var/www/codex/backend/data

# Restart container
docker compose restart
```

## Performance Tuning

### Gunicorn Workers

Edit `Dockerfile` CMD:

```dockerfile
# For 2-core server
CMD ["gunicorn", "--workers", "5", ...]

# For 1-core server
CMD ["gunicorn", "--workers", "3", ...]
```

**Formula**: workers = (2 × CPU_cores) + 1

After changing Dockerfile:
```bash
docker compose build
docker compose up -d
```

### Container Resources

Edit `docker-compose.yml`:

```yaml
deploy:
  resources:
    limits:
      cpus: '1.0'      # Increase if you have more CPU
      memory: 1G       # Increase if you have more RAM
```

After changing docker-compose.yml:
```bash
docker compose up -d
```

## Testing the Deployment

```bash
# 1. Test SSL
curl -I https://asthma.fredrikmeyer.net
# Should return: HTTP/2 200

# 2. Test HTTP redirect
curl -I http://asthma.fredrikmeyer.net
# Should return: 301 redirect to https://

# 3. Test API endpoints
curl -X POST https://asthma.fredrikmeyer.net/generate-code
# Should return: {"code":"XXXX"}

# 4. Test rate limiting
for i in {1..6}; do
  curl -X POST https://asthma.fredrikmeyer.net/generate-code
done
# 6th should return: 429 Too Many Requests

# 5. Test CORS
curl -X OPTIONS https://asthma.fredrikmeyer.net/generate-code \
  -H "Origin: https://fredrikmeyer.github.io" \
  -H "Access-Control-Request-Method: POST" \
  -I
# Should return: Access-Control-Allow-Origin header

# 6. Test container health
docker compose ps
# Should show: Up (healthy)
```

## Production Checklist

Before going live:

- [ ] Docker and Docker Compose installed
- [ ] Repository cloned to `/var/www/codex`
- [ ] `.env.docker` created with correct ALLOWED_ORIGINS
- [ ] Container built and running (`docker compose ps`)
- [ ] Data directory created and writable
- [ ] SSL certificate obtained
- [ ] nginx configured and tested (`sudo nginx -t`)
- [ ] nginx running and proxying to container
- [ ] All API endpoints tested via HTTPS
- [ ] Rate limiting tested and working per-client
- [ ] CORS tested with frontend domain
- [ ] Container auto-restarts on failure
- [ ] Logs accessible and readable
- [ ] Backup strategy in place
- [ ] Firewall allows ports 80 and 443
- [ ] DNS points to server IP

## Quick Command Reference

```bash
# Start container
docker compose up -d

# Stop container
docker compose down

# Restart container
docker compose restart

# View logs
docker compose logs -f

# Update application
git pull && docker compose up -d --build

# Backup data
cp data/storage.json /var/backups/asthma-$(date +%Y%m%d).json

# Check container status
docker compose ps

# Check container resources
docker stats asthma-backend

# Access container shell
docker compose exec asthma-backend /bin/bash

# Reload nginx
sudo systemctl reload nginx

# Check nginx logs
sudo tail -f /var/log/nginx/asthma.access.log
```

## Advantages Over Direct Deployment

| Aspect | Direct (systemd) | Docker |
|--------|------------------|--------|
| **Isolation** | Shares system Python | Isolated environment |
| **Updates** | Careful dependency management | Rebuild + restart |
| **Rollback** | Manual restore | Change image tag |
| **Resources** | No limits | CPU/memory limits |
| **Consistency** | Depends on OS version | Same everywhere |
| **Cleanup** | Manual uninstall | `docker compose down` |
| **Multiple versions** | Complex virtualenvs | Multiple containers |

## Summary

✅ **Docker**: Isolated container with Flask app
✅ **nginx**: Handles SSL, HTTP→HTTPS redirect, reverse proxy
✅ **ProxyFix**: Ensures rate limiting works correctly per-client
✅ **Volume**: Data persists across container restarts/rebuilds
✅ **Auto-restart**: Container starts on failure and server reboot
✅ **Let's Encrypt**: Free SSL certificates with auto-renewal
✅ **Environment variables**: Configuration via `.env.docker`

**Deploy workflow:**
1. Build image: `docker compose build`
2. Start container: `docker compose up -d`
3. Configure nginx
4. Test endpoints

**Update workflow:**
1. Pull code: `git pull`
2. Rebuild: `docker compose up -d --build`

Simple, reliable, production-ready! 🐳
