Last updated: 485cfd6 2026-11-07
Working branch: claude/laughing-brahmagupta-50jkiy
<!-- Overwrite after each meaningful task (skill simforge-status). Keep these headings: the
start hook prints "Next action" and "Open decisions"; the fresh-session autopilot reads
"Working branch" from this file on main. Mark an open decision "(blocks: <unit>)" only if
it stops that unit; answer one by adding a line starting "Answer:" under it. A chat on any
other branch is warned by the start brief and shown this file from origin/<working branch>. -->

# SimForge handoff

## Next action
Review the autopilot protocol upgrade (on this branch; not merged). Then:
2.3 slice 2, whose first unit is now to add its Acceptance block. Autopilot paused.

## Open decisions
- Scheduled task prompt (blocks: resuming the autopilot): its step 2 "read only" list omits `.claude/autopilot/FINDINGS.md`, which the skill now reads and writes, and step 6 does not mention STATE-only and review-pending commits. Updating the stored prompt was outside this task's files; say "update the autopilot prompt" to align it.
- Ruleset on `main` (re-targeted by you): "Require status checks" has no checks selected, so it requires nothing. Add `Backend (ruff, mypy, pytest)`, `Frontend (eslint, prettier, tsc, vitest, build)`, `API contract in sync`, `End-to-end (Playwright)`. Not blocking.
- Branch clean-up (your clicks): delete `backup/main-before-rewrite`, `backup/branch-before-rewrite` and `claude/epic-sagan-30vpv3`. Keep `main` and the working branch. Not blocking.
- Autopilot: weekly cap 0.76 (test) or back to 0.70? Used only when a run can read usage (rarely).
- Roadmap: "best angle against drag strength" and "drag-law comparison" are in the capability map but no Phase 2 step (recommend: schedule them; nothing built).
- Deployment risk: no rate limit or concurrency cap on sweeps (~11 s each); matters only if SimForge is ever public.
- Replay: should differing step counts be informational rather than "differs"?
- Not blocking: five optional clean-ups from the 2.1 review (PR #13 description).

## Last task: autopilot protocol upgrade (author-authorised guard-rail edits, 2026-11-07)
- **Completed:** (1) executable Acceptance blocks per plan slice, run by the tick itself; a
  test writer writes the named tests first and the builder may not touch them; (2) plans
  checked by three fresh reviewers (science, numerics, scope/testability), must-fix only, one
  round, applied by the resumed planner; (3) the planner's four "Before deciding" questions;
  (4) a Sonnet-first effort ladder (unit effort, one effort higher, Opus high, then the
  failures counter), Opus kept for planning and risky reviews, cost per merged step in STATE
  ("Step costs", 2.2 seeded at about 0.30 of a week); (5) `.claude/autopilot/FINDINGS.md`
  (seeded with 11 lessons, 2 confirmed), printed by the start hook; (6) six plugins disabled;
  at most 4 subagents per tick. Old hard rules, budget gate and never-merge unchanged.
- **Files:** `.claude/skills/autopilot/SKILL.md` (260 → 272 lines), `.claude/autopilot/STATE.md`,
  `.claude/autopilot/FINDINGS.md` (new), `.claude/settings.json`,
  `.claude/hooks/session-start.sh`, `CLAUDE.md`, this file.
- **Checks run:** `bash -n` and shellcheck on the hook (exit 0); the hook on the working
  branch (exit 0, 20 lines, prints the 2 confirmed findings) and in a scratch clone on another
  branch, a detached HEAD, a missing `origin/<working branch>` and no handoff (all exit 0,
  9-20 lines); `settings.json` parses. One fresh-context review (Opus): 11 findings, all
  fixed (an exception for FINDINGS.md in the hard rule, review-pending as a half-finished
  unit rather than a blocking decision, review fixes and the security review restored, the
  planner resumed to apply must-fix, no cross-tick ladder, a mis-confirmed finding split).
  Not run: `scripts/check.sh` (no code changed). CI: not run (no PR).
- **State:** committed and pushed to the working branch; no PR open; not merged.

## Learning handoff
- **What it does:** "done" now means commands that a tick runs and that pass, not a model's
  report; plans are checked from three angles by reviewers who did not write them.
- **Why it matters:** a system that grades its own work drifts; independent checks and a
  fixed bar keep quality while cheaper models do the routine building.
- **Key concept:** separation of setter and solver: whoever writes the test is not allowed to
  be the one who changes it to pass.
- **Trade-off:** more subagents per slice (a test writer, possible retries), capped at four
  per tick, in exchange for cheaper first attempts on Sonnet.
- **You should be able to explain:** why the builder may not edit the acceptance tests, and
  why "review pending" is a half-finished unit rather than an open decision.
