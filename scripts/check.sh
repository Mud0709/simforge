#!/usr/bin/env bash
# Run every check CI runs. Pass --e2e to include the Playwright end-to-end tests.
set -euo pipefail
cd "$(dirname "$0")/.."

step() { printf '\n==> %s\n' "$*"; }

step "Backend: lint, format, types, tests"
(cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy && uv run pytest --cov)

step "API contract: OpenAPI schema and generated TypeScript types are up to date"
(cd backend && uv run python scripts/export_openapi.py >/dev/null)
(cd frontend && npm run --silent gen:api >/dev/null)
git diff --exit-code -- frontend/src/lib/api/ || {
  echo "API contract changed: commit the regenerated files in frontend/src/lib/api/" >&2; exit 1; }

step "Frontend: lint, format, types, unit tests, build"
(cd frontend && npm run lint && npm run format:check && npm run typecheck && npm test && npm run build)

if [ "${1:-}" = "--e2e" ]; then
  step "End-to-end (Playwright)"
  (cd frontend && CI=1 npx playwright test)
fi

printf '\nAll checks passed.\n'
