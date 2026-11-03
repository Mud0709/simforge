#!/bin/bash
# SimForge SessionStart hook.
# 1. Prints the Session Start Brief (stdout, which Claude Code adds to Claude's context): git
#    facts, the 🔜 roadmap step and the handoff in docs/HANDOFF.md. Runs everywhere, uses no
#    network (origin refs are as last fetched) and never fails the hook. The working branch is
#    read from the "Working branch:" line of docs/HANDOFF.md on origin/main; a chat on any other
#    branch is warned and shown that branch's handoff (origin/<working branch>), because a new
#    chat starts on a fresh branch made from main, whose handoff lags until a PR is merged.
# 2. In Claude Code cloud sessions only, installs SimForge's dependencies so the checks in
#    scripts/check.sh can run straight away (local machines use scripts/setup.sh instead).
#    Install output goes to stderr; each step runs even if an earlier one failed. Failures
#    are reported on stdout as the brief's last line and the hook still exits 0, because
#    Claude Code adds a SessionStart hook's stdout to the context only on exit 0.
# 3. Sets this repository's commit identity to the author (the author's rule of 2026-11-02):
#    every commit is authored and committed by Mud0709 with the GitHub noreply address,
#    unsigned (the platform's signing key is Claude's, so signing would mark the author's
#    commits "Unverified"), and .githooks/commit-msg adds the Claude co-author trailer.
#    Repository-level config overrides the session's global "Claude" identity.
set -uo pipefail

if ! cd "${CLAUDE_PROJECT_DIR:-$(dirname "$0")/../..}"; then
  [ "${CLAUDE_CODE_REMOTE:-}" = "true" ] && exit 1
  exit 0
fi

# Prints at most $1 lines of the "## $2" section of the handoff file $3, then a pointer if
# longer. Tolerates CRLF and trailing spaces on the heading; says so when it is missing.
handoff_section() {
  awk -v want="## $2" -v max="$1" '
    { sub(/\r$/, "") }
    /^## / { h = $0; sub(/[ \t]+$/, "", h); inside = (h == want); if (inside) seen = 1; next }
    inside && NF { n++; if (n <= max) print "  " $0 }
    END {
      if (!seen) print "  (section missing from docs/HANDOFF.md)"
      else if (n == 0) print "  (none)"
      else if (n > max) printf "  (+%d more lines in docs/HANDOFF.md)\n", n - max
    }
  ' "$3"
}

brief() {
  local branch head base ahead behind dirty step merge sha since wb src ref from tmp=""
  branch=$(git rev-parse --abbrev-ref HEAD 2>/dev/null) || { echo "SimForge brief: not a git checkout"; return; }
  [ "$branch" = "HEAD" ] && branch="(detached HEAD)"
  head=$(git log -1 --format='%h %s' HEAD)
  # The working branch is named on main (docs/HANDOFF.md), so every new chat can find it.
  wb=$(git show origin/main:docs/HANDOFF.md 2>/dev/null | sed -n 's/^Working branch:[[:space:]]*\([^[:space:]]*\).*/\1/p' | head -1)
  echo "== SimForge session brief (git, no network; origin refs as last fetched) =="
  echo "Branch: $branch @ $head (working branch: ${wb:-unknown, no line on origin/main})"
  # Defaults: this checkout's handoff, staleness measured from HEAD.
  src=docs/HANDOFF.md; ref=HEAD; from="this checkout"
  if [ -n "$wb" ] && [ "$branch" != "$wb" ]; then
    echo "WARNING: This chat is on \`$branch\`; the latest work is on \`$wb\`. Switch with \`git switch $wb\` before working, and make sure no other chat or autopilot run is working on it."
    if git rev-parse --verify -q "origin/$wb" >/dev/null; then
      tmp=$(mktemp)
      if git show "origin/$wb:docs/HANDOFF.md" > "$tmp" 2>/dev/null; then
        src=$tmp; ref="origin/$wb"; from="origin/$wb"
      else
        rm -f "$tmp"; tmp=""; src=/nonexistent
        from="origin/$wb (it has no docs/HANDOFF.md)"
      fi
    else
      from="this checkout (origin/$wb not fetched)"
    fi
  fi
  if git rev-parse --verify -q origin/main >/dev/null; then
    base=origin/main
    merge=$(git log -1 --merges --format='%h %s (%cs)' "$base")
    echo "Latest merge on main: ${merge:-none}"
    ahead=$(git rev-list --count "$base".."$ref")
    behind=$(git rev-list --count "$ref".."$base")
    echo "Unmerged work ($ref): $ahead commit(s) ahead of main, $behind behind"
  else
    echo "Latest merge on main: unknown (no origin/main ref)"
  fi
  dirty=$(git --no-optional-locks status --porcelain | wc -l)
  [ "$dirty" -gt 0 ] && echo "Uncommitted: $dirty file(s) changed"
  step=$(grep -m1 '| 🔜 |' ROADMAP.md 2>/dev/null | cut -d'|' -f2-3 | sed 's/\*\*//g; s/|/ /; s/  */ /g; s/^ //; s/ $//')
  echo "Roadmap 🔜: ${step:-not found in ROADMAP.md}"

  if [ ! -f "$src" ]; then
    echo "Handoff ($from): no handoff yet (docs/HANDOFF.md is missing)"
    return
  fi
  sha=$(sed -n 's/^Last updated: \([0-9a-f]\{7,40\}\).*/\1/p' "$src" | head -1)
  if [ -z "$sha" ]; then
    echo "Handoff ($from): WARNING no 'Last updated: <sha> <date>' line in docs/HANDOFF.md"
  elif ! git cat-file -e "$sha^{commit}" 2>/dev/null; then
    echo "Handoff ($from): WARNING last updated at $sha, which is not in this checkout"
  else
    since=$(git rev-list --count "$sha".."$ref")
    if [ "$since" -gt 3 ]; then
      echo "Handoff ($from): WARNING stale, $ref is $since commits ahead of its sha $sha"
    else
      echo "Handoff ($from): covers $sha ($ref is $since commit(s) ahead)"
    fi
  fi
  echo "Next action:"
  handoff_section 3 "Next action" "$src"
  echo "Open decisions:"
  handoff_section 5 "Open decisions" "$src"
  [ -n "$tmp" ] && rm -f "$tmp"
  return 0
}

git config user.name "Mud0709" 2>/dev/null
git config user.email "324319297+Mud0709@users.noreply.github.com" 2>/dev/null
git config commit.gpgsign false 2>/dev/null
git config core.hooksPath .githooks 2>/dev/null

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
  printf 'WARNING setup failed (checks may not run): %s\n' "${failed[*]}"
fi
exit 0
