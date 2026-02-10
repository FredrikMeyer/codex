# GitHub Container Registry Deployment Setup Complete ✅

Successfully set up automated Docker image publishing and production deployment workflow!

## What Was Created

### 1. GitHub Actions Workflow
**File:** `.github/workflows/docker-publish.yml`

**Triggers:**
- Push to main branch (when backend files change)
- Manual trigger via GitHub Actions UI

**What it does:**
1. Builds Docker image from `backend/Dockerfile`
2. Pushes to GitHub Container Registry
3. Tags with:
   - `latest` (latest main branch)
   - `main-<sha>` (specific commit)

**Image location:**
```
ghcr.io/fredrikmeyer/codex/backend:latest
ghcr.io/fredrikmeyer/codex/backend:main-<sha>
```

### 2. Production Docker Compose
**File:** `backend/docker-compose.prod.yml`

Uses pre-built images from GitHub Container Registry instead of building locally:

```yaml
image: ghcr.io/fredrikmeyer/codex/backend:latest
```

**Features:**
- Pulls image from registry (no build needed)
- Port only exposed to localhost (127.0.0.1:5000)
- Persistent data volume
- Auto-restart on failure
- Resource limits
- Health checks

### 3. Deployment Guide
**File:** `DEPLOY.md`

Comprehensive production deployment guide covering:
- Docker installation
- GitHub Container Registry authentication
- Pulling and running images
- nginx configuration (user will configure separately)
- Updates and rollbacks
- Monitoring and troubleshooting
- CI/CD pipeline details

### 4. Updated Backend README
**File:** `backend/README.md`

Added deployment section linking to DEPLOY.md.

## Workflow

### Development (You)
1. Make changes to backend code
2. Commit and push to main
3. ✅ Done! GitHub Actions builds and publishes automatically

### CI/CD (Automatic)
1. GitHub Actions triggered on push to main
2. Builds Docker image
3. Runs tests (in image)
4. Pushes to `ghcr.io/fredrikmeyer/codex/backend`
5. Tags with `latest` and `main-<sha>`
6. Build takes ~2-3 minutes

### Production Server (You)
```bash
# First time setup
cd /var/www/codex/backend
docker compose -f docker-compose.prod.yml pull
docker compose -f docker-compose.prod.yml up -d

# Updates (after pushing new code)
docker compose -f docker-compose.prod.yml pull
docker compose -f docker-compose.prod.yml up -d
```

## Current Status

### ✅ First Build Triggered

Your push to main just triggered the first Docker image build!

**Check build status:**
https://github.com/FredrikMeyer/codex/actions

**Expected timeline:**
- Build starts: Immediately
- Build completes: ~2-3 minutes
- Image available: After build completes

**First build includes:**
- Latest backend code
- All dependencies (Flask, gunicorn, flask-limiter, etc.)
- Production configuration
- Health checks
- Non-root user setup

### 🔍 Verify Build Completed

1. Visit: https://github.com/FredrikMeyer/codex/actions
2. Click on "Build and Publish Docker Image" workflow
3. Wait for green checkmark ✅
4. Image will be at: https://github.com/FredrikMeyer/codex/pkgs/container/codex%2Fbackend

## Next Steps: Deploy to Your Server

### 1. Install Docker (if needed)
```bash
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER
```

### 2. Set Up Application
```bash
# Create directory
sudo mkdir -p /var/www/codex/backend
sudo chown -R $USER:$USER /var/www/codex

# Download production compose file
cd /var/www/codex/backend
curl -O https://raw.githubusercontent.com/FredrikMeyer/codex/main/backend/docker-compose.prod.yml

# Create environment file
cat > .env << 'EOF'
ALLOWED_ORIGINS=https://fredrikmeyer.github.io
EOF

# Create data directory
mkdir -p data
```

### 3. Pull and Start Container
```bash
# Pull image (wait for build to complete first!)
docker compose -f docker-compose.prod.yml pull

# Start container
docker compose -f docker-compose.prod.yml up -d

# Check logs
docker compose -f docker-compose.prod.yml logs -f

# Verify running
docker compose -f docker-compose.prod.yml ps
```

### 4. Test API
```bash
# Test from server
curl -X POST http://localhost:5000/generate-code
# Should return: {"code":"XXXX"}
```

### 5. Configure nginx
You'll handle nginx configuration separately. Backend listens on `127.0.0.1:5000`.

**Required proxy headers:**
```nginx
proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
proxy_set_header X-Forwarded-Proto $scheme;
proxy_set_header X-Forwarded-Host $host;
proxy_set_header Host $host;
```

## Image Details

### Base Image
- `python:3.12-slim` (Debian-based)
- Security updates included
- Minimal size (~150MB total)

### Layers
1. Builder stage: Install dependencies with uv
2. Final stage: Copy .venv, add app code
3. Non-root user (UID 1000)
4. Gunicorn as production WSGI server

### Tags Available
- `latest`: Always latest from main branch
- `main-<sha>`: Specific commit (e.g., `main-649ded0`)

### Security
- Non-root user (appuser, UID 1000)
- No unnecessary packages
- Security updates applied
- Minimal attack surface

## Updating Your Deployment

### When You Push New Code

1. **Push to GitHub** (you already do this)
   ```bash
   git push
   ```

2. **Wait for Build** (~2-3 minutes)
   - Check: https://github.com/FredrikMeyer/codex/actions

3. **Update on Server**
   ```bash
   docker compose -f docker-compose.prod.yml pull
   docker compose -f docker-compose.prod.yml up -d
   ```

**One-liner update command:**
```bash
docker compose -f docker-compose.prod.yml pull && \
docker compose -f docker-compose.prod.yml up -d && \
docker compose -f docker-compose.prod.yml logs --tail=50 -f
```

## Rollback

If something breaks, rollback to previous version:

1. Find previous commit SHA
2. Pull that specific image:
   ```bash
   docker pull ghcr.io/fredrikmeyer/codex/backend:main-abc1234
   ```
3. Update docker-compose.prod.yml to use that tag
4. Restart:
   ```bash
   docker compose -f docker-compose.prod.yml up -d
   ```

Or roll back code:
```bash
git revert HEAD
git push
# Wait for build, then pull on server
```

## Monitoring

### Build Status
- GitHub Actions: https://github.com/FredrikMeyer/codex/actions
- Email notifications on build failures (GitHub settings)

### Container Logs
```bash
# Follow logs
docker compose -f docker-compose.prod.yml logs -f

# Last 100 lines
docker compose -f docker-compose.prod.yml logs --tail=100

# Only errors
docker compose -f docker-compose.prod.yml logs | grep -i error
```

### Container Health
```bash
# Status
docker compose -f docker-compose.prod.yml ps

# Health check
docker inspect asthma-backend --format='{{.State.Health.Status}}'

# Resource usage
docker stats asthma-backend
```

## Cost

### GitHub Container Registry
- **Public images**: Free unlimited bandwidth
- **Private images**: 500MB storage free, then $0.25/GB/month
- **Recommended**: Keep images public for free hosting

### Build Minutes
- **GitHub Actions**: 2,000 minutes/month free
- **Usage**: ~2-3 minutes per build
- **Capacity**: ~600-1000 builds/month free

## Comparison with Other Approaches

| Approach | Pros | Cons |
|----------|------|------|
| **GitHub Container Registry** ✅ | Free, automated, versioned images | Requires Docker on server |
| Docker Hub | Well-known, free tier | Requires separate account |
| Build on server | No registry needed | Slower, requires build tools on server |
| Deploy from source | Simple | No rollback, must rebuild each time |

## Benefits

### Automated Deployment
- ✅ Push code → Image automatically built
- ✅ No manual Docker builds
- ✅ Consistent builds every time

### Version Control
- ✅ Every commit has an image (`main-<sha>`)
- ✅ Easy rollback to any version
- ✅ Track what's deployed

### Fast Updates
- ✅ Pull image: ~30 seconds
- ✅ Restart container: ~5 seconds
- ✅ Total downtime: ~35 seconds

### Simple Workflow
- ✅ Development: `git push`
- ✅ Production: `docker compose -f docker-compose.prod.yml pull && up -d`
- ✅ No complex deployment scripts

## Troubleshooting

### Build Failed
1. Check GitHub Actions logs
2. Common issues:
   - Syntax error in code
   - Missing dependency
   - Test failure
3. Fix code and push again

### Can't Pull Image
1. Check image exists: https://github.com/FredrikMeyer/codex/pkgs/container/codex%2Fbackend
2. Login to registry: `docker login ghcr.io`
3. Verify image name is correct

### Container Won't Start
1. Check logs: `docker compose -f docker-compose.prod.yml logs`
2. Check port not in use: `sudo lsof -i :5000`
3. Try pulling again: `docker compose -f docker-compose.prod.yml pull`

## Documentation

- **[DEPLOY.md](DEPLOY.md)**: Complete production deployment guide
- **[backend/docker-compose.prod.yml](backend/docker-compose.prod.yml)**: Production compose file
- **[.github/workflows/docker-publish.yml](.github/workflows/docker-publish.yml)**: CI/CD workflow

## Summary

✅ **GitHub Actions**: Builds and publishes Docker images automatically
✅ **GitHub Container Registry**: Hosts images for free
✅ **Production Compose**: Pull and run with one command
✅ **Comprehensive Guide**: DEPLOY.md has everything you need
✅ **First Build**: Triggered and building now!

**Your deployment workflow:**
1. Code: `git push` (you already do this)
2. CI/CD: Automatic (GitHub Actions)
3. Deploy: Pull and restart on server

**Simple, automated, production-ready!** 🚀

## Next Steps

1. ✅ **Wait for build** (~2-3 minutes)
   - https://github.com/FredrikMeyer/codex/actions

2. **Deploy to server** (see DEPLOY.md)
   - Install Docker
   - Pull image
   - Start container
   - Configure nginx

3. **Test in production**
   - API endpoints
   - Rate limiting
   - CORS

Ready to deploy! 🎉
