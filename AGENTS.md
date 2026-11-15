# Agent Instructions

## Dependency Lockfiles

Always keep `uv.lock` changes when they result from dependency sync, test, lint, or type-check commands. Treat these lockfile updates as part of keeping the repository consistent with `pyproject.toml`, not as incidental churn to revert.

## PWA updates

When changing frontend assets, increment the cache version in `frontend/service-worker.js` so installed PWAs receive the update.
