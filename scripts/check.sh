#!/usr/bin/env bash
# Run every check CI runs. Pass --e2e to include the Playwright end-to-end tests.
set -euo pipefail
cd "$(dirname "$0")/.."

step() { printf '\n==> %s\n' "$*"; }

step "Docs: docs/INDEX.md is up to date (also checked by backend/tests/scripts in CI)"
python3 scripts/doc_index.py --check

step "Docs: learning-guide excerpts match their source lines"
python3 scripts/check_excerpts.py

step "Backend: lint, format, types, tests"
(cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy && uv run pytest --cov)

step "API contract: OpenAPI schema and generated TypeScript types are up to date"
# Compare regenerated files with the working tree (not the last commit), so the check
# passes for uncommitted-but-current files and fails only when they are stale.
api_dir=frontend/src/lib/api
snapshot=$(mktemp -d)
cp "$api_dir/openapi.json" "$api_dir/schema.d.ts" "$snapshot/"
(cd backend && uv run python scripts/export_openapi.py >/dev/null)
(cd frontend && npm run --silent gen:api >/dev/null)
if ! diff -q "$snapshot/openapi.json" "$api_dir/openapi.json" >/dev/null ||
   ! diff -q "$snapshot/schema.d.ts" "$api_dir/schema.d.ts" >/dev/null; then
  echo "API contract was stale and has been regenerated in $api_dir; review and commit it." >&2
  rm -rf "$snapshot"; exit 1
fi
rm -rf "$snapshot"

step "Frontend: lint, format, types, unit tests, build"
(cd frontend && npm run lint && npm run format:check && npm run typecheck && npm test && npm run build)

if [ "${1:-}" = "--e2e" ]; then
  step "End-to-end (Playwright)"
  (cd frontend && CI=1 npx playwright test)
fi

printf '\nAll checks passed.\n'
