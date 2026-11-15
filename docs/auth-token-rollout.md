# Hashed token rollout

Goal: stop storing bearer tokens in plaintext while keeping existing devices signed in. Existing account codes and their associated data remain unchanged.

1. **Prepare token storage (done).** Add SQLite storage for multiple token digests per account and test persistence and lookup. This is not yet used for authentication or issuance.
2. **Choose an authoritative token store and implement compatibility (in progress).** SQLite-backed authentication accepts both hashed and legacy plaintext tokens and rejects conflicting ownership. SQLite-backed issuance creates independent tokens stored as digests; JSON-only authentication and issuance remain unchanged. Verify deployment and concurrent workers. Keep the API response compatible. Do not log tokens.
3. **Implement an idempotent migration (in progress).** SQLite-backed startup runs `migrate_legacy_token_hashes` after the existing JSON-to-SQLite migration. It copies tokens from both stores into SQLite digest storage, retaining different tokens for the same account and rejecting a token assigned to different accounts. Existing plaintext tokens remain available. Test the complete deployment path, including missing or inconsistent accounts and concurrent workers; JSON-only deployments still need a solution.
4. **Test the complete transition.** Use copies of representative data to test existing and offline devices, multiple devices per account, new sign-ins, account isolation, both event types, restarts, and concurrent requests. Verify new tokens are stored only as digests in every active storage path. Test upgrading an existing SQLite schema and running the migration twice.
5. **Prepare deployment and rollback.** Take a protected, restorable backup and verify it. Prevent old and new application versions from concurrently issuing tokens with incompatible storage rules. Define and rehearse a rollback that preserves tokens issued after migration; restoring an old backup alone would invalidate those sessions. Test on a production-data copy before deployment.
6. **Deploy and verify.** Run the migration and release in the tested order. Confirm existing devices can sync and a newly connected device does not disconnect them. Monitor authentication failures without recording credentials.
7. **Remove legacy plaintext storage.** Once verification and the rollback window are complete, remove plaintext token fields from active JSON and SQLite storage and prevent old migration or dual-write paths from restoring them. Account for SQLite WAL, backups, and other retained copies under the deployment's retention policy.
8. **Improve account recovery separately.** The six-character code can still be exchanged for a token. Design a stronger enrollment and recovery method, migrate users before retiring the old flow, and add revocation and rate limiting appropriate to the deployment.

Until plaintext storage is removed from all active paths, the new table alone does not provide the intended protection against a database or JSON file disclosure.

## Offline plaintext cleanup

`python -m app.cleanup_tokens --json /app/data/storage.json --db /app/data/codex.db --app-stopped` verifies that every plaintext token in both stores has a digest owned by the same account, then clears the JSON and SQLite fields. It can be rerun after an interruption. The flag is an operator assertion, not a lock: stop **all** app workers and other writers before the check and keep them stopped until cleanup completes. Otherwise JSON updates can be lost.

Before running it, make and verify a protected backup of both files, including a consistent SQLite backup. Rehearse on copies using the exact deployment image. Run the command in a separate container with the data volume mounted while the app container is stopped, then restart the app and check existing and new sessions. If it fails, leave the app stopped and investigate or rerun; do not restore a pre-cleanup database over later writes or newly issued tokens. The previous compatible release can read hashed tokens, but may write plaintext credentials again, so recheck both stores after a rollback.

Clearing fields removes values from active records, not necessarily old bytes in SQLite pages, WAL files, snapshots, or backups. Handle those copies according to the deployment's retention and secure disposal policy; this command does not scrub them.
