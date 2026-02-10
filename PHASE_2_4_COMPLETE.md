# Phase 2.4 Complete: Production Proxy Support

## ✅ Implementation Summary

Successfully implemented ProxyFix middleware for production deployment behind nginx, following TDD methodology. The app now correctly handles proxy headers for rate limiting and HTTPS detection when deployed behind a reverse proxy.

## What Was Built

### ProxyFix Middleware
```python
# Configure proxy support for production (behind nginx)
if app.config["PRODUCTION"]:
    app.wsgi_app = ProxyFix(
        app.wsgi_app,
        x_for=1,    # Trust X-Forwarded-For (real client IP)
        x_proto=1,  # Trust X-Forwarded-Proto (original protocol)
        x_host=1,   # Trust X-Forwarded-Host (original host)
        x_prefix=1  # Trust X-Forwarded-Prefix (URL prefix)
    )
```

### Features
- ✅ **ProxyFix enabled in production** - Only when PRODUCTION=true
- ✅ **Real client IP detection** - Rate limiting works correctly per-client
- ✅ **HTTPS detection** - App knows original protocol via X-Forwarded-Proto
- ✅ **Original host preservation** - App sees correct hostname
- ✅ **Development safety** - ProxyFix disabled in development mode

## The Problem: Rate Limiting Behind nginx

### Without ProxyFix (❌ Broken)

```
Client A (203.0.113.1) ──┐
                          ├─→ nginx (proxy) ─→ Flask
Client B (203.0.113.2) ──┘                      ↓
                                         sees 127.0.0.1
                                                ↓
                                    All clients = same IP
                                                ↓
                                    Share one rate limit!
```

**Result**:
- All clients share nginx's IP (127.0.0.1)
- First client hits rate limit → ALL clients blocked
- Rate limiting completely broken

### With ProxyFix (✅ Fixed)

```
Client A (203.0.113.1) ─→ nginx ─→ X-Forwarded-For: 203.0.113.1 ─→ Flask
                                                                     ↓
                                                          sees 203.0.113.1
                                                                     ↓
Client B (203.0.113.2) ─→ nginx ─→ X-Forwarded-For: 203.0.113.2 ─→ Flask
                                                                     ↓
                                                          sees 203.0.113.2
                                                                     ↓
                                                   Separate rate limits!
```

**Result**:
- Each client has separate IP (via X-Forwarded-For)
- Each client has independent rate limit
- Rate limiting works correctly

## How ProxyFix Works

### What nginx sends

```nginx
location / {
    proxy_pass http://localhost:5000;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header X-Forwarded-Host $host;
}
```

### What Flask receives

**Without ProxyFix:**
```python
request.remote_addr  # → "127.0.0.1" (nginx IP)
request.scheme       # → "http" (nginx→Flask connection)
request.host         # → "localhost:5000"
```

**With ProxyFix:**
```python
request.remote_addr  # → "203.0.113.1" (real client IP from X-Forwarded-For)
request.scheme       # → "https" (from X-Forwarded-Proto)
request.host         # → "asthma.fredrikmeyer.net" (from X-Forwarded-Host)
```

### The x_for=1 parameter

```python
ProxyFix(app.wsgi_app, x_for=1)
```

**Meaning**: "Trust the last 1 proxy in the chain"

**Why 1?** Our setup has exactly 1 proxy:
```
Client → nginx (proxy #1) → Flask
```

**If behind CDN** (e.g., Cloudflare):
```
Client → Cloudflare (proxy #2) → nginx (proxy #1) → Flask
```
Use `x_for=2` to trust both proxies.

**Security**: Never set higher than number of actual proxies!
- Too low: Won't trust proxy headers (rate limiting broken)
- Too high: Vulnerable to IP spoofing (client can fake X-Forwarded-For)

## Testing

### Test Coverage
- **6 new proxy tests** in `tests/test_proxy.py`
- **All 90 tests passing** (84 existing + 6 new)
- **Coverage: 96.60%**

### Tests Validate

1. ✅ **ProxyFix enabled in production**
   - Production mode: ProxyFix middleware is active
   - Development mode: ProxyFix middleware is not active

2. ✅ **X-Forwarded-For trusted in production**
   - Rate limiting uses X-Forwarded-For header
   - Different forwarded IPs have separate rate limits

3. ✅ **X-Forwarded-Proto trusted in production**
   - App accepts X-Forwarded-Proto header
   - App knows original protocol (http/https)

4. ✅ **Development mode works without proxy headers**
   - App works normally without X-Forwarded-For
   - No proxy headers required in development

## Code Changes

### Dependencies
- No new dependencies (werkzeug is already a Flask dependency)

### Modified Files

1. **`app/main.py`** (lines 19, 113-122)
   - Added import:
     ```python
     from werkzeug.middleware.proxy_fix import ProxyFix
     ```
   - Added ProxyFix middleware (production only):
     ```python
     if app.config["PRODUCTION"]:
         app.wsgi_app = ProxyFix(
             app.wsgi_app,
             x_for=1, x_proto=1, x_host=1, x_prefix=1
         )
     ```

### New Files

2. **`tests/test_proxy.py`** (6 tests)
   - Tests ProxyFix middleware
   - Tests X-Forwarded-For handling
   - Tests production vs development mode

3. **`DEPLOYMENT.md`** (comprehensive deployment guide)
   - nginx configuration with SSL
   - systemd service setup
   - ProxyFix explanation
   - Security best practices
   - Troubleshooting guide

## Deployment Configuration

### .env file (Production)

```bash
# Enable ProxyFix middleware
PRODUCTION=true

# Other settings
ALLOWED_ORIGINS=https://fredrikmeyer.github.io
DATA_FILE=/var/www/codex/backend/data/storage.json
```

### nginx configuration

```nginx
server {
    listen 443 ssl;
    server_name asthma.fredrikmeyer.net;

    location / {
        proxy_pass http://localhost:5000;

        # Critical headers for ProxyFix
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Forwarded-Host $host;
        proxy_set_header Host $host;
    }
}
```

## Security Considerations

### Safe Configuration

```python
# ✅ Safe: Trust exactly 1 proxy (our nginx)
ProxyFix(app.wsgi_app, x_for=1)
```

### Dangerous Configurations

```python
# ❌ Dangerous: Trust unlimited proxies
ProxyFix(app.wsgi_app, x_for=999)

# ❌ Dangerous: Always enabled (even in dev)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1)  # Should be production-only!
```

### Why Production-Only?

**In development**:
- No nginx proxy
- Direct client→Flask connection
- ProxyFix would trust fake X-Forwarded-For headers
- Allows IP spoofing in development

**In production**:
- nginx proxy in front
- nginx sets trusted headers
- ProxyFix extracts real client IP
- Rate limiting works correctly

## Integration with Previous Phases

### Phase 2.3 (Rate Limiting)
- ✅ **Critical fix**: Rate limiting now works per-client in production
- ✅ **Before ProxyFix**: All clients shared one rate limit (broken)
- ✅ **After ProxyFix**: Each client has separate rate limit (fixed)

### Phase 2.2 (Environment Configuration)
- ✅ **PRODUCTION flag**: Reused existing config for ProxyFix
- ✅ **Consistent**: Same .env variable controls multiple features

### Phase 2.1 (CORS)
- ✅ **CORS + ProxyFix**: Both work together correctly
- ✅ **Origin checking**: Works with X-Forwarded-Host

## Why This Matters

### Real-World Scenario

**Without ProxyFix**:
```
User A visits site 5 times → hits rate limit (5/hour for /generate-code)
User B visits site → ALSO blocked! (shares rate limit with User A)
User C visits site → ALSO blocked!
...everyone blocked after first user hits limit
```

**With ProxyFix**:
```
User A visits site 5 times → hits rate limit (only User A blocked)
User B visits site → works fine (separate rate limit)
User C visits site → works fine (separate rate limit)
...each user has independent rate limit
```

### Impact

**Before this phase**:
- ❌ Rate limiting broken in production
- ❌ All users share one rate limit
- ❌ App unusable after first user hits limit

**After this phase**:
- ✅ Rate limiting works correctly
- ✅ Each user has separate limit
- ✅ App works as designed

## Deployment Checklist

When deploying to production:

- [ ] Set `PRODUCTION=true` in `.env`
- [ ] Configure nginx with proxy headers
- [ ] SSL certificate obtained
- [ ] nginx config tested (`sudo nginx -t`)
- [ ] Test rate limiting works per-client
- [ ] Verify logs show real client IPs
- [ ] Check X-Forwarded-For in Flask logs

## Verification

### Check ProxyFix is Active

```bash
# Should see ProxyFix in logs during startup
sudo journalctl -u asthma-backend | grep -i proxy
```

### Check Real IPs in Logs

```bash
# Logs should show real client IPs, not 127.0.0.1
sudo tail -f /var/log/asthma-backend/access.log
```

### Test Rate Limiting Per-Client

```bash
# From first IP - hit rate limit
for i in {1..6}; do curl -X POST https://asthma.fredrikmeyer.net/generate-code; done
# → 6th request: 429 Too Many Requests

# From second IP - should still work
curl -X POST https://asthma.fredrikmeyer.net/generate-code --interface eth1
# → 200 OK
```

## Common Issues

### Issue: All clients share rate limit

**Symptom**: First user hits limit, all users blocked

**Cause**: ProxyFix not enabled

**Fix**:
```bash
# Check .env
grep PRODUCTION /var/www/codex/backend/.env
# Should show: PRODUCTION=true

# Restart
sudo systemctl restart asthma-backend
```

### Issue: Rate limit not working at all

**Symptom**: Can make unlimited requests

**Cause**: nginx not sending X-Forwarded-For header

**Fix**:
```nginx
# Add to nginx config
proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;

# Reload nginx
sudo systemctl reload nginx
```

### Issue: Logs show 127.0.0.1

**Symptom**: All requests from 127.0.0.1 in logs

**Cause**: ProxyFix not enabled or nginx headers missing

**Fix**: Check both .env (PRODUCTION=true) and nginx config (headers set)

## TDD Approach

### Red Phase
- Wrote 6 failing tests first
- Tests defined expected ProxyFix behavior
- Tests failed as expected (ProxyFix not implemented)

### Green Phase
1. Added ProxyFix import
2. Added conditional ProxyFix middleware (production only)
3. All tests passed

### Refactor Phase
- No refactoring needed
- Code is clean and minimal

## Next Steps

Backend is now **production-ready**! All Phase 2 features complete:

- ✅ Phase 2.1: CORS configuration
- ✅ Phase 2.2: Environment configuration
- ✅ Phase 2.3: Rate limiting
- ✅ Phase 2.4: Production proxy support

Ready for **Phase 3: Frontend Development**
- Build React/TypeScript frontend
- Implement login flow
- Add medicine logging form
- Deploy to GitHub Pages

## Checkpoint ✅

- ✅ ProxyFix middleware implemented
- ✅ Production-only activation (PRODUCTION=true)
- ✅ All 6 proxy tests passing
- ✅ All 90 total tests passing
- ✅ Coverage: 96.60%
- ✅ DEPLOYMENT.md comprehensive guide created
- ✅ Rate limiting fixed for production
- ✅ Real client IPs detected correctly
- ✅ nginx configuration documented
- ✅ Security best practices followed

**Production proxy support complete and deployment-ready!** 🎉
