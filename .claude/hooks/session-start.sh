#!/bin/bash
# Install SimForge's dependencies at the start of a Claude Code cloud session, so the
# checks in scripts/check.sh (ruff, mypy, pytest, ESLint, tsc, Vitest, build, Playwright)
# can run straight away. Local machines use scripts/setup.sh instead.
set -euo pipefail

if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

cd "${CLAUDE_PROJECT_DIR:-$(dirname "$0")/../..}"

# Backend: exact versions from uv.lock, as in CI. --locked fails instead of updating the lock.
(cd backend && uv sync --locked)

# Frontend: npm ci, as in CI and scripts/setup.sh. It installs exactly package-lock.json and
# never rewrites it. Because npm ci deletes and reinstalls node_modules, skip it when
# node_modules was already installed from this exact lockfile (recorded by its SHA-256).
stamp=frontend/node_modules/.simforge-lock-sha256
lock_sha=$(sha256sum frontend/package-lock.json | cut -d' ' -f1)
if [ "$(cat "$stamp" 2>/dev/null || true)" != "$lock_sha" ]; then
  (cd frontend && npm ci --no-audit --no-fund)
  echo "$lock_sha" > "$stamp"
fi

# Cloud sessions provide Chromium in $PLAYWRIGHT_BROWSERS_PATH and must not download one.
# Check that it is the revision the pinned @playwright/test needs, and say so if not.
needed=$(cd frontend && npx playwright install --dry-run chromium 2>/dev/null \
  | awk '/Install location/ {print $3; exit}' || true)
if [ -n "$needed" ] && [ ! -d "$needed" ]; then
  echo "warning: Playwright needs $needed, which is not installed;" \
    "end-to-end tests will fail until the environment provides it." >&2
fi
