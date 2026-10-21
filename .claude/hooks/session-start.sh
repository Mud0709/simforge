#!/bin/bash
# Install SimForge's dependencies at the start of a Claude Code cloud session, so the
# checks in scripts/check.sh (ruff, mypy, pytest, ESLint, tsc, Vitest, build, Playwright)
# can run straight away. Local machines use scripts/setup.sh instead.
#
# Install output goes to stderr: a SessionStart hook's stdout is added to Claude's context.
# Each step runs even if an earlier one failed; failures are listed at the end.
set -uo pipefail

if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

cd "${CLAUDE_PROJECT_DIR:-$(dirname "$0")/../..}" || exit 1
failed=()

# Backend: exact versions from uv.lock, as in CI. --locked fails instead of updating the lock.
(cd backend && uv sync --locked) >&2 || failed+=("backend: uv sync --locked")

# Frontend: npm ci, as in CI and scripts/setup.sh. It installs exactly package-lock.json and
# never rewrites it. Because npm ci deletes and reinstalls node_modules, skip it when
# node_modules was already installed from this exact lockfile with this Node version.
stamp=frontend/node_modules/.simforge-install-stamp
want="$(sha256sum frontend/package-lock.json | cut -d' ' -f1) node-$(node -v)"
if [ "$(cat "$stamp" 2>/dev/null || true)" != "$want" ]; then
  if (cd frontend && npm ci --no-audit --no-fund) >&2; then
    echo "$want" > "$stamp"
  else
    failed+=("frontend: npm ci")
  fi
fi

# Cloud sessions provide browsers in $PLAYWRIGHT_BROWSERS_PATH and must not download them.
# Check every build the pinned @playwright/test needs for Chromium (the full browser, the
# headless shell used by headless runs, and ffmpeg) and warn about any that is missing.
missing=$(cd frontend && npx playwright install --dry-run chromium 2>/dev/null \
  | awk '/Install location/ {print $3}' | while read -r dir; do
      [ -d "$dir" ] || echo "$dir"
    done)
if [ -n "$missing" ]; then
  echo "warning: Playwright builds not installed (end-to-end tests will fail):" $missing >&2
fi

if [ ${#failed[@]} -gt 0 ]; then
  printf 'SimForge setup failed: %s\n' "${failed[@]}" >&2
  exit 1
fi
