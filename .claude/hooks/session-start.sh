#!/bin/bash
# Install SimForge's dependencies at the start of a Claude Code cloud session, so the
# checks in scripts/check.sh (ruff, mypy, pytest, ESLint, tsc, Vitest, build, Playwright)
# can run straight away. Local machines use scripts/setup.sh instead.
set -euo pipefail

if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

cd "${CLAUDE_PROJECT_DIR:-$(dirname "$0")/../..}"

# Backend: exact versions from uv.lock (uv reuses its cache across sessions).
(cd backend && uv sync --locked)

# Frontend: npm install (not ci) so the cached node_modules is reused when the lockfile
# has not changed. Cloud sessions provide Chromium in $PLAYWRIGHT_BROWSERS_PATH, so no
# browser download is needed.
(cd frontend && npm install --no-audit --no-fund)
