# Backend Integration Implementation Plan

## Overview

Add secure backend sync to the asthma tracker using a hybrid authentication approach:
- Initial setup via short code
- Long-lived API tokens for ongoing use
- Backend hosted on Digital Ocean
- Frontend hosted on GitHub Pages

## Architecture

```
[GitHub Pages]           [Digital Ocean Droplet]
frontend/                backend/
  ├── index.html          ├── nginx (reverse proxy)
  ├── app.js              ├── gunicorn (WSGI server)
  ├── styles.css          └── Flask app
  └── config.js               ├── data/storage.json
                              └── .env
```

## Implementation Phases

### Phase 1: Backend - Token System (Expand)

#### Step 1.1: Add token generation
- Add `POST /generate-token` endpoint (new, alongside existing code system)
- Generate long random token (32+ chars using `secrets` module)
- Store token with code in data file
- Write tests for token generation
- ✅ **Checkpoint**: Tests pass, existing endpoints unchanged

#### Step 1.2: Add token validation middleware
- Create `require_auth()` decorator
- Check for `Authorization: Bearer <token>` header
- Validate against stored tokens
- Write tests for token validation
- ✅ **Checkpoint**: Tests pass, decorator not yet applied to endpoints

#### Step 1.3: Add dual auth to /logs endpoint
- Update `/logs` to accept EITHER code OR token
- Keep backward compatibility (code still works)
- Add tests for both auth methods
- ✅ **Checkpoint**: Tests pass, both auth methods work

---

### Phase 2: Backend - Security & Config

#### Step 2.1: Add CORS support
- Add `flask-cors` dependency via `uv add flask-cors`
- Configure allowed origins (GitHub Pages URL)
- Support environment variable for allowed origins
- Write tests to verify CORS headers
- ✅ **Checkpoint**: Tests pass

#### Step 2.2: Add environment configuration
- Add `python-dotenv` dependency via `uv add python-dotenv`
- Create `.env.example` with:
  ```
  ALLOWED_ORIGINS=https://username.github.io
  DATA_FILE=backend/data/storage.json
  RATE_LIMIT_PER_MINUTE=60
  PRODUCTION=false
  ```
- Load config from environment in app
- ✅ **Checkpoint**: Tests pass, app uses config

#### Step 2.3: Add rate limiting
- Add `flask-limiter` dependency via `uv add flask-limiter`
- Apply rate limits to auth endpoints:
  - `/generate-code`: 5/hour
  - `/login`: 10/minute
  - `/generate-token`: 10/minute
  - `/logs`: 100/minute
- Write tests to verify rate limiting works
- ✅ **Checkpoint**: Tests pass

#### Step 2.4: Add HTTPS enforcement (production only)
- Add middleware to redirect HTTP → HTTPS
- Only active when `PRODUCTION=true` in environment
- Write tests to verify redirect in production mode
- ✅ **Checkpoint**: Tests pass (skipped in test mode)

---

### Phase 3: Frontend - Token Integration

#### Step 3.1: Add token storage
- Add `localStorage` key for token: `asthma-auth-token`
- Add helper functions: `getToken()`, `setToken()`, `hasToken()`
- Add backend URL configuration
- ✅ **Checkpoint**: No breaking changes, app still works

#### Step 3.2: Add login UI
- Add new "Sync Setup" section to UI
- Add "Generate Code" button (calls backend)
- Add "Enter Code" input field
- Add "Complete Setup" button (exchanges code for token)
- Store token in localStorage on success
- Show setup status (not configured / configured)
- ✅ **Checkpoint**: App still works offline without sync

#### Step 3.3: Add sync functionality
- Add "Sync to Cloud" button (replaces or alongside "Export CSV")
- Send entries to backend with token in Authorization header
- Handle success/error states with toast messages
- Handle network errors gracefully
- ✅ **Checkpoint**: Export CSV still works as fallback

#### Step 3.4: Add auto-sync option (optional)
- Add toggle for "Auto-sync on save"
- Store preference in localStorage: `asthma-auto-sync`
- Sync automatically after save when enabled
- ✅ **Checkpoint**: Manual sync still works

---

### Phase 4: Backend Deployment (Digital Ocean)

#### Step 4.1: Add production dependencies
- Add `gunicorn` via `uv add gunicorn`
- Ensure all dependencies in `pyproject.toml`
- Test production server locally
- ✅ **Checkpoint**: App runs with gunicorn

#### Step 4.2: Create deployment config
- Create `deploy/` directory
- Add systemd service file: `deploy/asthma-backend.service`
- Add nginx config template: `deploy/nginx.conf`
- Add `.env.production.example`
- Add deployment README with instructions
- ✅ **Checkpoint**: Config files ready

#### Step 4.3: Add health check endpoint
- Add `GET /health` endpoint
- Returns: `{"status": "ok", "version": "0.1.0"}`
- No authentication required
- Write tests for health check
- ✅ **Checkpoint**: Tests pass

#### Step 4.4: Digital Ocean setup
- Create droplet (Ubuntu 22.04 LTS)
- Install Python 3.12, nginx, uv
- Clone repository
- Set up systemd service
- Configure nginx as reverse proxy
- Set up SSL with Let's Encrypt (certbot)
- ✅ **Checkpoint**: Backend accessible via HTTPS

---

### Phase 5: Frontend Deployment (GitHub Pages)

#### Step 5.1: Add production config
- Create `frontend/config.js`:
  ```js
  const config = {
    backendUrl: window.location.hostname === 'localhost'
      ? 'http://localhost:5000'
      : 'https://api.yourdomain.com'
  };
  ```
- Update `app.js` to use `config.backendUrl`
- ✅ **Checkpoint**: App builds and runs locally

#### Step 5.2: Update GitHub Pages config
- Verify `BASE_PATH` in service worker
- Update manifest.webmanifest if needed
- Configure custom domain (optional)
- Enable HTTPS in GitHub Pages settings
- ✅ **Checkpoint**: App deploys to GitHub Pages

---

### Phase 6: Polish & Additional Features

#### Step 6.1: Add token refresh
- Add `POST /refresh-token` endpoint
- Accepts code, returns new token
- Invalidates old token
- Write tests for token refresh
- ✅ **Checkpoint**: Tests pass

#### Step 6.2: Add data retrieval
- Add `GET /logs` endpoint (requires token)
- Returns all log entries for authenticated user
- Supports date range filtering (optional)
- Enables multi-device sync
- Write tests for data retrieval
- ✅ **Checkpoint**: Tests pass

#### Step 6.3: Add sync down functionality (frontend)
- Add "Sync from Cloud" button
- Fetch entries from backend
- Merge with local entries (prefer newer)
- Handle conflicts gracefully
- ✅ **Checkpoint**: Two-way sync works

#### Step 6.4: Contract - Remove code auth from /logs (optional)
- After migration period, remove code-based auth from `/logs`
- Only accept tokens for data operations
- Keep code auth for initial setup only
- Update tests
- ✅ **Checkpoint**: Tests pass, cleaner auth model

---

## Testing Strategy

### Backend Tests
- Unit tests for each endpoint
- Integration tests for auth flow
- Rate limiting tests
- CORS tests
- Token expiry tests (if implemented)

### Frontend Tests (optional)
- Manual testing for now
- Future: Add E2E tests with Playwright/Cypress

### Security Checklist
- [ ] HTTPS enforced in production
- [ ] CORS properly configured
- [ ] Rate limiting active
- [ ] Tokens are cryptographically random (32+ chars)
- [ ] Tokens stored securely (not logged)
- [ ] Input validation on all endpoints
- [ ] Error messages don't leak information

---

## Deployment Checklist

### Backend (Digital Ocean)
- [ ] Droplet created and configured
- [ ] Python 3.12 installed
- [ ] Nginx configured as reverse proxy
- [ ] SSL certificate installed (Let's Encrypt)
- [ ] Systemd service running
- [ ] Firewall configured (UFW: allow 80, 443, 22)
- [ ] Data directory with correct permissions
- [ ] Environment variables configured
- [ ] Health check endpoint responding
- [ ] Logs being written correctly

### Frontend (GitHub Pages)
- [ ] Repository configured for GitHub Pages
- [ ] HTTPS enabled
- [ ] Custom domain configured (optional)
- [ ] Backend URL updated in config
- [ ] Service worker scope correct
- [ ] App loads and functions correctly
- [ ] Sync setup flow works end-to-end

---

## Rollback Plan

If issues occur:
1. **Backend issues**: Systemd allows easy rollback to previous version
2. **Frontend issues**: GitHub Pages history allows reverting commits
3. **Data loss**: JSON files are append-only, can restore from backups
4. **Auth issues**: Can regenerate codes and tokens via backend console

---

## Key Principles

Following CLAUDE.md guidelines:
- **Each step compiles and tests pass** - No broken intermediate states
- **Expand-Migrate-Contract** - Add new alongside old, migrate gradually, remove old last
- **Backward compatibility** - Existing offline functionality always works
- **Clear checkpoints** - Can stop and deploy at any checkpoint
- **Security first** - HTTPS, rate limiting, proper token handling
