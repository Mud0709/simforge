#!/usr/bin/env bash
# Install all dependencies from lockfiles. Safe to re-run.
set -euo pipefail
cd "$(dirname "$0")/.."

need() { command -v "$1" >/dev/null 2>&1 || { echo "Missing '$1'. $2" >&2; exit 1; }; }
need uv   "Install: brew install uv   (or: curl -LsSf https://astral.sh/uv/install.sh | sh)"
need node "Install Node.js 20.9+ (e.g. brew install node@22, or nvm use with .nvmrc)"
need npm  "npm ships with Node.js"

node_major=$(node -p 'process.versions.node.split(".")[0]')
if [ "$node_major" -lt 20 ]; then echo "Node.js 20.9+ required, found $(node -v)" >&2; exit 1; fi

echo "==> Backend: uv sync (uv fetches the Python in backend/.python-version if needed)"
(cd backend && uv sync --locked)

echo "==> Frontend: npm ci"
(cd frontend && npm ci)

if [ "${SKIP_PLAYWRIGHT:-0}" != "1" ]; then
  echo "==> Playwright Chromium for end-to-end tests (SKIP_PLAYWRIGHT=1 to skip)"
  (cd frontend && npx playwright install chromium) || echo "    (skipped: could not install browser)"
fi

echo "Done. Start the app with: make dev   (or ./scripts/dev.sh)"
