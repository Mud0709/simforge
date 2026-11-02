#!/bin/bash
# SimForge SessionStart hook.
# 1. Prints the Session Start Brief (stdout, which Claude Code adds to Claude's context): git
#    facts, the 🔜 roadmap step and the handoff in docs/HANDOFF.md. Runs everywhere, uses no
#    network (origin/main is as last fetched) and never fails the hook.
# 2. In Claude Code cloud sessions only, installs SimForge's dependencies so the checks in
#    scripts/check.sh can run straight away (local machines use scripts/setup.sh instead).
#    Install output goes to stderr; each step runs even if an earlier one failed, and
#    failures are listed at the end.
set -uo pipefail

cd "${CLAUDE_PROJECT_DIR:-$(dirname "$0")/../..}" || exit 1

# Prints at most $1 lines of the "## $2" section of docs/HANDOFF.md, then a pointer if longer.
handoff_section() {
  awk -v want="## $2" -v max="$1" '
    /^## / { inside = ($0 == want); next }
    inside && NF { n++; if (n <= max) print "  " $0 }
    END { if (n > max) printf "  (+%d more lines in docs/HANDOFF.md)\n", n - max }
  ' docs/HANDOFF.md
}

brief() {
  local branch head base ahead behind dirty step merge sha since
  branch=$(git rev-parse --abbrev-ref HEAD 2>/dev/null) || { echo "SimForge brief: not a git checkout"; return; }
  head=$(git log -1 --format='%h %s' HEAD)
  echo "== SimForge session brief (git, no network; origin/main as last fetched) =="
  echo "Branch: $branch @ $head"
  if git rev-parse --verify -q origin/main >/dev/null; then
    base=origin/main
    merge=$(git log -1 --merges --format='%h %s (%cs)' "$base")
    echo "Latest merge on main: ${merge:-none}"
    ahead=$(git rev-list --count "$base"..HEAD)
    behind=$(git rev-list --count HEAD.."$base")
    echo "Unmerged work: $ahead commit(s) ahead of main, $behind behind"
  else
    echo "Latest merge on main: unknown (no origin/main ref)"
  fi
  dirty=$(git status --porcelain | wc -l)
  [ "$dirty" -gt 0 ] && echo "Uncommitted: $dirty file(s) changed"
  step=$(grep -m1 '| 🔜 |' ROADMAP.md 2>/dev/null | cut -d'|' -f2-3 | sed 's/\*\*//g; s/|/ /; s/  */ /g; s/^ //; s/ $//')
  echo "Roadmap 🔜: ${step:-not found in ROADMAP.md}"

  if [ ! -f docs/HANDOFF.md ]; then
    echo "Handoff: no handoff yet (docs/HANDOFF.md is missing)"
    return
  fi
  sha=$(sed -n 's/^Last updated: \([0-9a-f]\{7,40\}\).*/\1/p' docs/HANDOFF.md | head -1)
  if [ -z "$sha" ]; then
    echo "Handoff: WARNING no 'Last updated: <sha> <date>' line in docs/HANDOFF.md"
  elif ! git cat-file -e "$sha^{commit}" 2>/dev/null; then
    echo "Handoff: WARNING last updated at $sha, which is not in this checkout"
  else
    since=$(git rev-list --count "$sha"..HEAD)
    if [ "$since" -gt 3 ]; then
      echo "Handoff: WARNING stale, HEAD is $since commits ahead of its sha $sha"
    else
      echo "Handoff: covers $sha (HEAD is $since commit(s) ahead)"
    fi
  fi
  echo "Next action:"
  handoff_section 3 "Next action"
  echo "Open decisions:"
  handoff_section 6 "Open decisions"
}

brief 2>/dev/null || true

if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

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
  echo "warning: Playwright builds not installed (end-to-end tests will fail):" "$missing" >&2
fi

if [ ${#failed[@]} -gt 0 ]; then
  printf 'SimForge setup failed: %s\n' "${failed[@]}" >&2
  exit 1
fi
