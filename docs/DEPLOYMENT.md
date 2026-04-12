# Deployment Guide

This guide covers deploying the asthma tracker backend to a production server with nginx and SSL.

## Architecture Overview

```
Internet
   ↓
nginx (443/SSL) → Flask app (localhost:5000)
   ↓
Let's Encrypt SSL
```

**Components:**
- **nginx**: Reverse proxy, SSL termination, HTTP→HTTPS redirect
- **Flask app**: Backend API running on localhost:5000
- **Let's Encrypt**: Free SSL certificates
- **systemd**: Process management for Flask app

## Prerequisites

- Ubuntu/Debian server with root access
- Domain name pointing to server (e.g., `asthma.fredrikmeyer.net`)
- Port 80 and 443 open in firewall

## Step 1: Install Dependencies

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install nginx
sudo apt install nginx -y

# Install certbot for Let's Encrypt
sudo apt install certbot python3-certbot-nginx -y

# Install uv (Python package manager)
curl -LsSf https://astral.sh/uv/install.sh | sh
source $HOME/.cargo/env
```

## Step 2: Deploy Application

```bash
# Clone repository
cd /var/www
sudo git clone https://github.com/FredrikMeyer/codex.git
sudo chown -R $USER:$USER codex

# Setup backend
cd codex/backend
uv sync

# Create production .env file
cp .env.example .env
nano .env
```

**Production `.env` configuration:**
```bash
# CORS - restrict to your frontend domain
ALLOWED_ORIGINS=https://fredrikmeyer.github.io

# Data storage - absolute path for production
DATA_FILE=/var/www/codex/backend/data/storage.json

# Production mode - enables ProxyFix for nginx
PRODUCTION=true
```

## Step 3: Obtain SSL Certificate

```bash
# Get certificate (replace with your domain)
sudo certbot certonly --nginx -d asthma.fredrikmeyer.net

# Certificate will be saved to:
# /etc/letsencrypt/live/asthma.fredrikmeyer.net/fullchain.pem
# /etc/letsencrypt/live/asthma.fredrikmeyer.net/privkey.pem
```

**Note:** Certbot will automatically renew certificates via cron.

## Step 4: Configure Nginx

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

# HTTPS server - reverse proxy to Flask app
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

    # Reverse proxy to Flask app
    location / {
        proxy_pass http://localhost:5000;

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

        # Disable buffering for better performance
        proxy_buffering off;
    }

    # Health check endpoint (optional)
    location /health {
        access_log off;
        proxy_pass http://localhost:5000/health;
    }
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

## Step 5: Create Systemd Service

Create `/etc/systemd/system/asthma-backend.service`:

```ini
[Unit]
Description=Asthma Tracker Backend API
After=network.target

[Service]
Type=simple
User=www-data
Group=www-data
WorkingDirectory=/var/www/codex/backend
Environment="PATH=/var/www/codex/backend/.venv/bin:/usr/local/bin:/usr/bin:/bin"

# Load environment variables from .env file
EnvironmentFile=/var/www/codex/backend/.env

# Run Flask app with gunicorn (production WSGI server)
ExecStart=/var/www/codex/backend/.venv/bin/gunicorn \
    --workers 2 \
    --bind 127.0.0.1:5000 \
    --access-logfile /var/log/asthma-backend/access.log \
    --error-logfile /var/log/asthma-backend/error.log \
    --log-level info \
    "app.main:app"

# Restart on failure
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

**Setup and start service:**
```bash
# Create log directory
sudo mkdir -p /var/log/asthma-backend
sudo chown www-data:www-data /var/log/asthma-backend

# Install gunicorn
cd /var/www/codex/backend
uv add gunicorn

# Enable and start service
sudo systemctl daemon-reload
sudo systemctl enable asthma-backend
sudo systemctl start asthma-backend

# Check status
sudo systemctl status asthma-backend
```

## Step 6: Verify Deployment

```bash
# Check nginx is running
sudo systemctl status nginx

# Check Flask app is running
sudo systemctl status asthma-backend

# Check logs
sudo journalctl -u asthma-backend -f

# Test HTTPS endpoint
curl -I https://asthma.fredrikmeyer.net/generate-code
# Should return: HTTP/2 405 (Method Not Allowed - GET not allowed)

# Test actual endpoint
curl -X POST https://asthma.fredrikmeyer.net/generate-code
# Should return: {"code":"XXXX"}
```

## Why ProxyFix is Critical

**Without ProxyFix** (PRODUCTION=false):
```
Client (203.0.113.1) → nginx → Flask
                                ↓
                         sees 127.0.0.1 (nginx IP)
                                ↓
                         rate limit: 127.0.0.1
```
❌ **Result**: All clients share the same rate limit (nginx's IP)

**With ProxyFix** (PRODUCTION=true):
```
Client (203.0.113.1) → nginx → Flask (with ProxyFix)
                         ↓             ↓
                   X-Forwarded-For: 203.0.113.1
                                     ↓
                         rate limit: 203.0.113.1
```
✅ **Result**: Each client has separate rate limit (real client IP)

## Nginx Proxy Headers Explained

```nginx
proxy_set_header Host $host;
# → Original hostname (asthma.fredrikmeyer.net)

proxy_set_header X-Real-IP $remote_addr;
# → Direct client IP (may be proxy if behind CDN)

proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
# → Chain of IPs (client → proxy → proxy → nginx)
# → ProxyFix uses this to get real client IP

proxy_set_header X-Forwarded-Proto $scheme;
# → Original protocol (https)
# → Flask knows request was HTTPS even though nginx→Flask is HTTP

proxy_set_header X-Forwarded-Host $host;
# → Original host header
```

## ProxyFix Configuration

In `app/main.py`:
```python
if app.config["PRODUCTION"]:
    app.wsgi_app = ProxyFix(
        app.wsgi_app,
        x_for=1,    # Trust 1 proxy for X-Forwarded-For
        x_proto=1,  # Trust 1 proxy for X-Forwarded-Proto
        x_host=1,   # Trust 1 proxy for X-Forwarded-Host
        x_prefix=1  # Trust 1 proxy for X-Forwarded-Prefix
    )
```

**The numbers mean**: "Trust the last N proxies in the chain"
- `x_for=1`: Trust the last proxy (nginx) for client IP
- `x_proto=1`: Trust the last proxy for protocol (http/https)
- `x_host=1`: Trust the last proxy for hostname
- `x_prefix=1`: Trust the last proxy for URL prefix

**Why 1?** We have exactly 1 proxy (nginx) between client and Flask.

**If behind CDN** (e.g., Cloudflare → nginx → Flask): Use `x_for=2`

## Security Headers

Nginx adds security headers:
```nginx
# Force HTTPS for 1 year (including subdomains)
add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;

# Prevent clickjacking
add_header X-Frame-Options "SAMEORIGIN" always;

# Prevent MIME sniffing
add_header X-Content-Type-Options "nosniff" always;
```

## Running Multiple Apps

Since you're running multiple apps on the same server, assign different ports:

```nginx
# App 1: Links app on port 3002
server {
    listen 443 ssl;
    server_name links.fredrikmeyer.net;
    location / {
        proxy_pass http://localhost:3002;
        # ... proxy headers ...
    }
}

# App 2: Asthma tracker on port 5000
server {
    listen 443 ssl;
    server_name asthma.fredrikmeyer.net;
    location / {
        proxy_pass http://localhost:5000;
        # ... proxy headers ...
    }
}
```

**Each app needs**:
- Own systemd service
- Own port number
- Own nginx server block
- Own SSL certificate (or wildcard cert)

## Monitoring and Logs

```bash
# View Flask app logs
sudo journalctl -u asthma-backend -f

# View nginx access logs
sudo tail -f /var/log/nginx/access.log

# View nginx error logs
sudo tail -f /var/log/nginx/error.log

# View Flask app-specific logs
sudo tail -f /var/log/asthma-backend/access.log
sudo tail -f /var/log/asthma-backend/error.log
```

## Common Issues

### 1. Rate limiting not working per-client

**Symptom**: All clients share the same rate limit

**Cause**: ProxyFix not enabled or PRODUCTION=false

**Fix**:
```bash
# Check .env file
cat /var/www/codex/backend/.env
# Should have: PRODUCTION=true

# Restart service
sudo systemctl restart asthma-backend
```

### 2. CORS errors from frontend

**Symptom**: Browser shows CORS error

**Cause**: ALLOWED_ORIGINS doesn't include frontend domain

**Fix**:
```bash
# Edit .env
nano /var/www/codex/backend/.env
# Set: ALLOWED_ORIGINS=https://fredrikmeyer.github.io

# Restart service
sudo systemctl restart asthma-backend
```

### 3. 502 Bad Gateway

**Symptom**: nginx returns 502 error

**Cause**: Flask app not running or wrong port

**Fix**:
```bash
# Check if Flask app is running
sudo systemctl status asthma-backend

# Check what's listening on port 5000
sudo lsof -i :5000

# Start Flask app
sudo systemctl start asthma-backend
```

### 4. SSL certificate errors

**Symptom**: Browser shows SSL warning

**Cause**: Certificate expired or not found

**Fix**:
```bash
# Check certificate expiry
sudo certbot certificates

# Renew certificates manually
sudo certbot renew

# Certificates auto-renew via cron
sudo systemctl status certbot.timer
```

## Updating the Application

```bash
# Pull latest code
cd /var/www/codex
git pull

# Update dependencies
cd backend
uv sync

# Run tests
uv run pytest

# Restart service
sudo systemctl restart asthma-backend

# Check logs
sudo journalctl -u asthma-backend -f
```

## Backup and Data

The data file is stored at: `/var/www/codex/backend/data/storage.json`

**Backup strategy:**
```bash
# Create backup
sudo cp /var/www/codex/backend/data/storage.json \
       /var/backups/asthma-$(date +%Y%m%d).json

# Or backup via cron (daily at 2 AM)
echo "0 2 * * * cp /var/www/codex/backend/data/storage.json /var/backups/asthma-\$(date +\%Y\%m\%d).json" | sudo crontab -
```

## Performance Tuning

### Gunicorn Workers

**Formula**: `workers = (2 × CPU_cores) + 1`

For 2-core server:
```ini
ExecStart=... --workers 5 ...
```

For 1-core server:
```ini
ExecStart=... --workers 3 ...
```

### Nginx Rate Limiting

Add nginx-level rate limiting for additional protection:

```nginx
# In /etc/nginx/nginx.conf
http {
    # Limit requests to 10 per second from each IP
    limit_req_zone $binary_remote_addr zone=api:10m rate=10r/s;
}

# In /etc/nginx/sites-available/asthma
server {
    location / {
        limit_req zone=api burst=20;
        proxy_pass http://localhost:5000;
        # ...
    }
}
```

## Environment Variables

All configuration via environment variables in `.env`:

```bash
# CORS configuration
ALLOWED_ORIGINS=https://fredrikmeyer.github.io

# Data storage
DATA_FILE=/var/www/codex/backend/data/storage.json

# Production mode (enables ProxyFix)
PRODUCTION=true
```

**To update**:
1. Edit `/var/www/codex/backend/.env`
2. Restart service: `sudo systemctl restart asthma-backend`

## Health Check

Add health check endpoint to Flask app (optional):

```python
@app.get("/health")
def health():
    return jsonify({"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat()})
```

Then monitor with:
```bash
curl https://asthma.fredrikmeyer.net/health
```

## Testing the Deployment

1. **Test SSL**:
   ```bash
   curl -I https://asthma.fredrikmeyer.net
   # Should return: HTTP/2 200
   ```

2. **Test HTTP redirect**:
   ```bash
   curl -I http://asthma.fredrikmeyer.net
   # Should return: 301 redirect to https://
   ```

3. **Test API endpoints**:
   ```bash
   # Generate code
   curl -X POST https://asthma.fredrikmeyer.net/generate-code

   # Login
   curl -X POST https://asthma.fredrikmeyer.net/login \
     -H "Content-Type: application/json" \
     -d '{"code":"XXXX"}'
   ```

4. **Test rate limiting**:
   ```bash
   # Make 6 requests quickly
   for i in {1..6}; do
     curl -X POST https://asthma.fredrikmeyer.net/generate-code
   done
   # 6th should return 429 Too Many Requests
   ```

5. **Test CORS**:
   ```bash
   curl -X OPTIONS https://asthma.fredrikmeyer.net/generate-code \
     -H "Origin: https://fredrikmeyer.github.io" \
     -H "Access-Control-Request-Method: POST" \
     -I
   # Should return: Access-Control-Allow-Origin header
   ```

## Production Checklist

Before going live:

- [ ] `.env` file created with PRODUCTION=true
- [ ] ALLOWED_ORIGINS set to frontend domain
- [ ] SSL certificate obtained and configured
- [ ] nginx configuration tested (`sudo nginx -t`)
- [ ] systemd service enabled and running
- [ ] Health check endpoint returns 200
- [ ] All API endpoints tested via HTTPS
- [ ] Rate limiting tested and working
- [ ] CORS tested with frontend domain
- [ ] Logs accessible and readable
- [ ] Backup strategy in place
- [ ] Firewall allows ports 80 and 443
- [ ] DNS points to server IP

## Summary

✅ **nginx**: Handles SSL, HTTP→HTTPS redirect, reverse proxy
✅ **ProxyFix**: Ensures rate limiting works correctly per-client
✅ **systemd**: Keeps Flask app running, auto-restart on failure
✅ **gunicorn**: Production WSGI server for Flask
✅ **Let's Encrypt**: Free SSL certificates with auto-renewal
✅ **Environment variables**: All configuration via `.env` file

**Key insight**: PRODUCTION=true is critical for rate limiting to work correctly behind nginx!
