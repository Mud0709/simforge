Last updated: d9209ef 2026-11-02
Working branch: claude/laughing-brahmagupta-50jkiy
<!-- Overwrite after each meaningful task (skill simforge-status). Keep these headings: the
start hook prints "Next action" and "Open decisions"; the fresh-session autopilot reads
"Working branch" from this file on main. Mark an open decision "(blocks: <unit>)" only if
it stops that unit; answer one by adding a line starting "Answer:" under it. -->

# SimForge handoff

## Next action
Re-enable your GitHub ruleset aimed at `main` (not this branch), then read
`docs/plans/ROADMAP_2_3_PLAN.md` (it blocks the autopilot's slice 1).

## Open decisions
- 2.3 plan unverified by content (blocks: 2.3 slice 1): the planner (Opus) wrote D1-D17; the run checked only its structure. Read it, or ask for a content review; then add `Answer: plan accepted` (or your changes) here.
- Ruleset 26367084 is disabled. It targeted this working branch, where "require a pull request" blocks every direct push (the autopilot's too). Re-enable it targeting `main` only, with "Require status checks". Not blocking.
- GitHub email privacy: tick Settings → Emails → "Keep my email addresses private", so GitHub web merges use your noreply address, not your personal one. Not blocking.
- Second identity layer: add to the cloud environment's environment variables `GIT_AUTHOR_NAME=Mud0709`, `GIT_AUTHOR_EMAIL=324319297+Mud0709@users.noreply.github.com`, `GIT_COMMITTER_NAME=Mud0709`, `GIT_COMMITTER_EMAIL=324319297+Mud0709@users.noreply.github.com`. Do not add `GIT_CONFIG_*` variables (they switch off the proxy's git set-up). Not blocking.
- Backup branches `backup/main-before-rewrite`, `backup/branch-before-rewrite`: keep, or delete once you are happy. Not blocking.
- Signing: commits are now unsigned (no "Verified" badge). To get the badge back, add your own SSH signing key to GitHub; not possible from cloud sessions. Not blocking.
- Autopilot: weekly cap 0.76 (test) or back to 0.70? Used only when a run can read usage (rarely).
- Roadmap: "best angle against drag strength" and "drag-law comparison" are in the capability map but no Phase 2 step (recommend: schedule them; nothing built).
- Deployment risk: no rate limit or concurrency cap on sweeps (~11 s each); matters only if SimForge is ever public.
- Replay: should differing step counts be informational rather than "differs"?
- Not blocking: five optional clean-ups from the 2.1 review (PR #13 description).

## Last task: history rewritten; commits are the author's
- **Rewrite (2026-11-02):** all 110 commits on `main` and this branch now have author and
  committer `Mud0709 <324319297+Mud0709@users.noreply.github.com>` (94 were Claude's, 16 were
  GitHub merges with your personal email) and a `Co-Authored-By: Claude` trailer (18 added).
  Verified per commit: same tree, dates and message (only the trailer added); tip trees
  unchanged (`main` 28c16964, branch 55ed109b); counts 101 / 110; `Autopilot-run` trailer kept.
  Force-pushed with leases: `main` 3908bac → 8e7596e, branch ef2fa93 → 1b6194e. Old→new map:
  `docs/history-rewrite-map.txt`. Hashes before today in the journal, learning log and old PR
  pages are the old ones.
- **Future commits:** the start hook sets your identity (repository config overrides the
  session's global "Claude"), turns signing off (the platform key is Claude's, so signed
  commits would show "Unverified") and enables `.githooks/commit-msg`, which adds the Claude
  trailer with the blank line git needs. Rules in `CLAUDE.md` (Git) and the autopilot skill.
- **Files:** `.githooks/commit-msg`, `.claude/hooks/session-start.sh`, `CLAUDE.md`,
  `.claude/skills/autopilot/SKILL.md`, `.claude/autopilot/STATE.md` (`work limit from:`
  8e7596e), `docs/AUTOPILOT_JOURNAL.md`, `docs/LEARNING_LOG.md`, `docs/history-rewrite-map.txt`.
- **Checks run:** the per-commit comparison (110 commits, 0 problems); remote trees after the
  push; shellcheck on both hooks (exit 0); the hook run (exit 0, `git var` shows your identity);
  commit-msg on five message shapes, all parsed as trailers; `d9209ef` authored as you,
  unsigned, Claude co-author. Not run: `scripts/check.sh` (no code changed). CI: not run (no PR).
- **State:** pushed to `main` (rewrite) and this branch; no PR open. Autopilot re-enabled
  (daily, 02:59 UTC).

## Learning handoff
- **What it does:** the history now says you wrote every commit, with Claude credited as
  co-author, and every future commit is set up the same way automatically.
- **Why it matters:** a commit's hash covers its author, so changing authors gives every
  commit a new hash; that is why the map and the backup branches exist.
- **Key concept:** a commit hash is a fingerprint of the content *and* its metadata (tree,
  parents, author, committer, message), so editing one commit changes every later hash.
- **Trade-off:** clean authorship costs the old hashes (old PR pages and notes still cite
  them) and the "Verified" signature badge.
- **You should be able to explain:** why the file trees stayed identical while every hash
  changed, and why `--force-with-lease` was safer than `--force`.
