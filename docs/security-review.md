# Security Review

## How Auth Works

```
1. POST /generate-code  → 6-char alphanumeric code (stored in JSON)
2. POST /generate-token → exchanges code for 64-char hex token
3. All data endpoints   → require Authorization: Bearer <token>
```

The `code` acts as both user ID and one-time setup credential. Once a token is issued, the code is essentially frozen as a user identifier — every event in the database is tagged with its owner's code.

---

## Per-User Data Isolation

**This part is solid.** Every data endpoint:
1. Extracts the token from the `Authorization` header
2. Looks up the associated `code` (user ID)
3. Passes `code` to the repository, which filters on `code == entry.code`

There is a test for exactly this:

```python
def test_get_events_excludes_other_users(auth_token):
    # user1 and user2 each save an event
    # user1 only sees their own event — verified
```

Cross-user access would require stealing another user's token.

---

## Protected vs Unprotected Endpoints

| Endpoint               | Protected | Rate limit |
|------------------------|-----------|------------|
| `POST /generate-code`  | No        | 5/hour     |
| `POST /generate-token` | No        | 10/min     |
| `POST /login`          | No        | 10/min     |
| `GET /events`          | **Yes**   | 100/min    |
| `POST /events`         | **Yes**   | 100/min    |
| `GET /ritalin-events`  | **Yes**   | 100/min    |
| `POST /ritalin-events` | **Yes**   | 100/min    |
| `GET /code`            | **Yes**   | 10/min     |

The unprotected auth endpoints are intentional (public registration flow) and rate-limited.

---

## Issues

### 1. Code generation uses non-cryptographic randomness

`_generate_code()` uses `random.choices()` (Python's Mersenne Twister), not `secrets.choice()`. For a setup flow that's rate-limited to 5/hour this is low risk in practice, but it's the wrong function.

**Fix:** `secrets.choice(string.ascii_uppercase + string.digits)` in a loop.

### 2. Tokens stored in plain text

The SQLite database (`codex.db`) stores tokens verbatim. If the file is read by an attacker, all tokens are immediately usable. The tokens themselves are strong (256-bit entropy via `secrets.token_hex(32)`), but their storage provides no defence-in-depth.

**Fix for single-user:** Ensure the database file has mode `600` on disk. That's probably sufficient.
**Fix for multi-user:** Store `sha256(token)` in the DB and compare hashes on each request.

### 3. Tokens never expire and cannot be revoked

A token issued today is valid forever. There is no logout, no rotation, and no way to invalidate a token without directly editing the JSON file.

**For personal use:** Acceptable.
**For multi-user:** Needs expiry timestamps and a revocation mechanism.

### 4. Rate limiting resets on restart

Limits are held in memory (`storage_uri="memory://"`). A process restart resets all counters. An attacker who can trigger restarts (e.g. crash the process) gets a free counter reset.

**Fix:** Use Redis or a persistent store for rate limit state.

### 5. CORS defaults to `*` in development

The default `ALLOWED_ORIGINS=*` means any website can make credentialed requests. This should always be locked to the known frontend origin in production (it appears it is — `.env.docker.example` sets `https://fredrikmeyer.github.io`).

---

## Is It Safe to Add More Users?

**The data isolation logic is correct** — users cannot read each other's events. The architecture supports multiple users today without any code changes.

However, a few things become more important with more users:

| Concern                         | Single user                     | Multi-user                                                                                                   |
|---------------------------------|---------------------------------|--------------------------------------------------------------------------------------------------------------|
| Plain-text tokens in SQLite DB  | Low risk (it's your own server) | Higher risk (compromise exposes all users)                                                                   |
| No token expiry                 | Inconvenient at worst           | Dormant accounts accumulate valid tokens indefinitely                                                        |
| `random.choices()` for codes    | Negligible at 5/hour            | Still negligible, but worth fixing for correctness                                                           |
| Rate limiting resets on restart | Your own nuisance               | Affects all users simultaneously                                                                             |
| SQLite write contention         | No contention                   | Concurrent writes are serialised by a threading lock — fine for small N, becomes a bottleneck at higher load |

**Short answer:** Adding a handful of trusted users (family, friends) is safe with the current model. The isolation is sound. The main practical risk is the plain-text token storage — if the server is compromised, all users' tokens are exposed at once.

**Not appropriate for:** Public sign-up, untrusted users, or any scenario where you can't vet who has access.

---

## Recommendations

**Minimum before adding any users:**
- [ ] Restrict `ALLOWED_ORIGINS` to the exact frontend domain (already done in prod config)
- [ ] Confirm data file is `chmod 600` on the server
- [ ] Replace `random.choices()` with `secrets.choice()` in `_generate_code()`

**Nice-to-have:**
- [ ] Store `sha256(token)` instead of raw token
- [ ] Add `token_expires_at` column (e.g. 1 year from issue)
- [ ] Use a persistent store for rate limit state (Redis or SQLite)

**Only needed for public/untrusted multi-user:**
- Replace JSON file storage with a proper database
- Full token lifecycle management (refresh, revocation)
- Audit logging
